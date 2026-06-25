import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app import config
from app.db import get_db, init_db
import app.main as main
from app.routes.api_current_workout import (
    add_current_workout_exercise,
    add_current_workout_set,
    clear_current_workout,
    delete_current_workout_exercise,
    delete_current_workout_set,
    duplicate_current_workout_set,
    finish_current_workout,
    get_current_workout,
    start_current_workout,
    update_current_workout_metadata,
    update_current_workout_set,
)
from app.routes.api_exercises import create_exercise_endpoint
from app.schemas import (
    AddExerciseRequest,
    AddSetRequest,
    ExerciseCreateRequest,
    UpdateSetRequest,
    WorkoutMetadataUpdate,
)
from app.services import draft_service


class CurrentWorkoutApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()
        draft_service.clear_active_workout_draft()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def exercise_id(self, exercise_name: str) -> int:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id FROM exercises WHERE name = ?",
                (exercise_name,),
            ).fetchone()

        if row is None:
            raise AssertionError(f"Seed exercise not found: {exercise_name}")

        return int(row["id"])

    def test_current_workout_routes_are_registered(self) -> None:
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in main.app.routes
            if hasattr(route, "methods")
        }

        self.assertIn(("/api/v1/current-workout", ("GET",)), routes)
        self.assertIn(("/api/v1/current-workout/start", ("POST",)), routes)
        self.assertIn(("/api/v1/current-workout/metadata", ("PATCH",)), routes)
        self.assertIn(("/api/v1/current-workout/exercises", ("POST",)), routes)
        self.assertIn(("/api/v1/current-workout/finish", ("POST",)), routes)

    def test_get_current_workout_returns_stable_inactive_response(self) -> None:
        response = get_current_workout()

        self.assertFalse(response["active"])
        self.assertIsNone(response["started_at"])
        self.assertEqual(response["total_sets"], 0)
        self.assertEqual(response["exercises"], [])
        self.assertFalse(response["recovery_context"]["has_history"])
        self.assertEqual(
            response["next_workout_recommendation"]["title"],
            "Start baseline",
        )

    def test_current_workout_mutation_flow_returns_updated_state(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        response = start_current_workout()
        self.assertTrue(response["active"])

        response = update_current_workout_metadata(
            WorkoutMetadataUpdate(session_rpe=7, lower_back_pain=2)
        )
        self.assertEqual(response["session_rpe"], 7)
        self.assertEqual(response["lower_back_pain"], 2)

        response = add_current_workout_exercise(
            AddExerciseRequest(exercise_id=deadlift_id)
        )
        draft_exercise_id = response["exercises"][0]["draft_exercise_id"]
        self.assertIn(100.0, response["exercises"][0]["configured_weights"])

        response = add_current_workout_set(
            draft_exercise_id,
            AddSetRequest(weight=100.0, reps=5),
        )
        draft_set_id = response["exercises"][0]["sets"][0]["id"]
        self.assertEqual(response["total_sets"], 1)
        self.assertEqual(response["total_reps"], 5)
        self.assertEqual(response["total_volume"], 500.0)

        response = update_current_workout_set(
            draft_set_id,
            UpdateSetRequest(weight=105.0, reps=6),
        )
        self.assertEqual(response["exercises"][0]["sets"][0]["weight"], 105.0)
        self.assertEqual(response["exercises"][0]["sets"][0]["reps"], 6)
        self.assertEqual(response["total_volume"], 630.0)

        response = delete_current_workout_set(draft_set_id)
        self.assertEqual(response["total_sets"], 0)

        response = delete_current_workout_exercise(draft_exercise_id)
        self.assertEqual(response["exercises"], [])

    def test_active_workout_inline_created_exercise_can_be_added_mutated_and_finished(self) -> None:
        start_current_workout()

        created = create_exercise_endpoint(
            ExerciseCreateRequest(name="Inline Curl", weights=[12.5])
        )
        exercise_id = int(created["exercise"]["id"])

        response = add_current_workout_exercise(
            AddExerciseRequest(exercise_id=exercise_id)
        )
        draft_exercise_id = response["exercises"][0]["draft_exercise_id"]
        self.assertEqual(response["exercises"][0]["exercise_name"], "Inline Curl")
        self.assertEqual(response["exercises"][0]["configured_weights"], [12.5])

        response = add_current_workout_set(
            draft_exercise_id,
            AddSetRequest(weight=12.5, reps=8),
        )
        first_set_id = response["exercises"][0]["sets"][0]["id"]

        response = duplicate_current_workout_set(draft_exercise_id)
        second_set_id = response["exercises"][0]["sets"][1]["id"]
        self.assertEqual(
            [set_entry["set_number"] for set_entry in response["exercises"][0]["sets"]],
            [1, 2],
        )

        response = update_current_workout_set(
            second_set_id,
            UpdateSetRequest(reps=9),
        )
        self.assertEqual(response["exercises"][0]["sets"][1]["reps"], 9)

        response = delete_current_workout_set(first_set_id)
        self.assertEqual(response["total_sets"], 1)
        self.assertEqual(response["exercises"][0]["sets"][0]["set_number"], 1)

        finish_response = finish_current_workout()

        self.assertEqual(finish_response["workout_id"], 1)
        self.assertFalse(finish_response["current_workout"]["active"])

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]
            set_count = conn.execute("SELECT COUNT(*) FROM set_entries").fetchone()[0]

        self.assertEqual(workout_count, 1)
        self.assertEqual(set_count, 1)

    def test_inactive_exercise_cannot_be_added_to_current_workout(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")
        with get_db() as conn:
            conn.execute(
                "UPDATE exercises SET is_active = 0 WHERE id = ?",
                (deadlift_id,),
            )

        start_current_workout()

        with self.assertRaises(HTTPException) as exc:
            add_current_workout_exercise(AddExerciseRequest(exercise_id=deadlift_id))

        self.assertEqual(exc.exception.status_code, 409)

    def test_deactivated_exercise_already_in_draft_remains_visible(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        start_current_workout()
        response = add_current_workout_exercise(
            AddExerciseRequest(exercise_id=deadlift_id)
        )
        self.assertEqual(response["exercises"][0]["exercise_name"], "Deadlift")

        with get_db() as conn:
            conn.execute(
                "UPDATE exercises SET is_active = 0 WHERE id = ?",
                (deadlift_id,),
            )

        response = get_current_workout()

        self.assertTrue(response["active"])
        self.assertEqual(response["exercises"][0]["exercise_name"], "Deadlift")

        draft_exercise_id = response["exercises"][0]["draft_exercise_id"]
        response = add_current_workout_set(
            draft_exercise_id,
            AddSetRequest(weight=100.0, reps=5),
        )

        self.assertEqual(response["total_sets"], 1)

    def test_profile_update_refreshes_current_workout_metrics(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        start_current_workout()
        add_current_workout_exercise(AddExerciseRequest(exercise_id=deadlift_id))
        add_current_workout_set(1, AddSetRequest(weight=100.0, reps=5))

        with get_db() as conn:
            conn.execute(
                "UPDATE exercises SET profile_key = ? WHERE id = ?",
                ("accessory", deadlift_id),
            )

        response = get_current_workout()

        self.assertEqual(response["exercises"][0]["profile_key"], "accessory")
        self.assertEqual(
            response["load_metrics"]["exercise_breakdown"][0]["category"],
            "accessory",
        )

    def test_finish_current_workout_persists_workout_and_clears_draft(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        start_current_workout()
        add_current_workout_exercise(AddExerciseRequest(exercise_id=deadlift_id))
        add_current_workout_set(1, AddSetRequest(weight=100.0, reps=5))

        response = finish_current_workout()

        self.assertEqual(response["workout_id"], 1)
        self.assertFalse(response["current_workout"]["active"])
        self.assertFalse(get_current_workout()["active"])

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]
            set_count = conn.execute("SELECT COUNT(*) FROM set_entries").fetchone()[0]

        self.assertEqual(workout_count, 1)
        self.assertEqual(set_count, 1)

    def test_finish_current_workout_rejects_empty_draft_and_preserves_it(self) -> None:
        start_current_workout()

        with self.assertRaises(HTTPException) as exc:
            finish_current_workout()

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(
            exc.exception.detail,
            "Cannot finish a workout without logged sets.",
        )
        self.assertTrue(get_current_workout()["active"])

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]

        self.assertEqual(workout_count, 0)

    def test_finish_current_workout_rejects_exercise_without_sets(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        start_current_workout()
        add_current_workout_exercise(AddExerciseRequest(exercise_id=deadlift_id))

        with self.assertRaises(HTTPException) as exc:
            finish_current_workout()

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(
            exc.exception.detail,
            "Cannot finish a workout without logged sets.",
        )
        self.assertTrue(get_current_workout()["active"])

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]

        self.assertEqual(workout_count, 0)

    def test_finish_current_workout_rejects_after_deleting_last_set(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        start_current_workout()
        add_current_workout_exercise(AddExerciseRequest(exercise_id=deadlift_id))
        response = add_current_workout_set(1, AddSetRequest(weight=100.0, reps=5))
        draft_set_id = response["exercises"][0]["sets"][0]["id"]
        delete_current_workout_set(draft_set_id)

        with self.assertRaises(HTTPException) as exc:
            finish_current_workout()

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(
            exc.exception.detail,
            "Cannot finish a workout without logged sets.",
        )
        self.assertTrue(get_current_workout()["active"])

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]

        self.assertEqual(workout_count, 0)

    def test_second_finish_current_workout_does_not_duplicate_workout(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        start_current_workout()
        add_current_workout_exercise(AddExerciseRequest(exercise_id=deadlift_id))
        add_current_workout_set(1, AddSetRequest(weight=100.0, reps=5))
        first_response = finish_current_workout()

        with self.assertRaises(HTTPException) as exc:
            finish_current_workout()

        self.assertEqual(first_response["workout_id"], 1)
        self.assertEqual(exc.exception.status_code, 409)

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]

        self.assertEqual(workout_count, 1)

    def test_current_workout_errors_are_json_api_friendly(self) -> None:
        with self.assertRaises(HTTPException) as no_draft:
            update_current_workout_metadata(WorkoutMetadataUpdate(session_rpe=5))

        self.assertEqual(no_draft.exception.status_code, 409)

        start_current_workout()

        with self.assertRaises(HTTPException) as missing_exercise:
            add_current_workout_exercise(AddExerciseRequest(exercise_id=9999))

        self.assertEqual(missing_exercise.exception.status_code, 404)

        with self.assertRaises(HTTPException) as empty_update:
            update_current_workout_set(1, UpdateSetRequest())

        self.assertEqual(empty_update.exception.status_code, 400)

    def test_current_workout_request_models_validate_ranges(self) -> None:
        with self.assertRaises(Exception):
            WorkoutMetadataUpdate(session_rpe=11)

        with self.assertRaises(Exception):
            WorkoutMetadataUpdate(lower_back_pain=-1)

        with self.assertRaises(Exception):
            AddSetRequest(weight=-1, reps=5)

        with self.assertRaises(Exception):
            AddSetRequest(weight=100, reps=0)

    def test_clear_current_workout_removes_active_draft(self) -> None:
        start_current_workout()

        response = clear_current_workout()

        self.assertFalse(response["active"])
        self.assertFalse(get_current_workout()["active"])


if __name__ == "__main__":
    unittest.main()
