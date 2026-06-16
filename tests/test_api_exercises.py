import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app import config
from app.db import get_db, init_db
import app.main as main
from app.routes.api_exercises import (
    create_exercise_endpoint,
    get_exercises,
    reorder_exercises_endpoint,
    replace_exercise_weights_endpoint,
    update_exercise_endpoint,
)
from app.schemas import (
    ExerciseCreateRequest,
    ExerciseOrderUpdateRequest,
    ExerciseUpdateRequest,
    ExerciseWeightsUpdateRequest,
)


class ExercisesApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()

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

    def test_exercise_routes_are_registered(self) -> None:
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in main.app.routes
            if hasattr(route, "methods")
        }

        self.assertIn(("/api/v1/exercises", ("GET",)), routes)
        self.assertIn(("/api/v1/exercises", ("POST",)), routes)
        self.assertIn(("/api/v1/exercises/{exercise_id}", ("PATCH",)), routes)
        self.assertIn(("/api/v1/exercises/{exercise_id}/weights", ("PUT",)), routes)
        self.assertIn(("/api/v1/exercises/order", ("PUT",)), routes)

    def test_get_exercises_returns_seeded_exercises_by_settings_order(self) -> None:
        response = get_exercises()
        names = [exercise["name"] for exercise in response["exercises"]]

        self.assertEqual(names, list(config.DEFAULT_EXERCISES))
        self.assertIn("Deadlift", names)
        self.assertEqual(response["exercises"][0]["profile_key"], "deadlift")
        self.assertTrue(response["exercises"][0]["is_active"])
        self.assertIn(100.0, response["exercises"][0]["weights"])

    def test_create_exercise_strips_name_and_reports_created(self) -> None:
        response = create_exercise_endpoint(
            ExerciseCreateRequest(name="  Incline   Row  ", weights=[17.75, 15, 15])
        )

        self.assertTrue(response["created"])
        self.assertEqual(response["exercise"]["name"], "Incline Row")
        self.assertEqual(response["exercise"]["weights"], [15.0, 17.75])

        with self.assertRaises(HTTPException) as exc:
            create_exercise_endpoint(ExerciseCreateRequest(name="Incline Row"))

        self.assertEqual(exc.exception.status_code, 409)

    def test_create_exercise_rejects_blank_name_after_stripping(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            create_exercise_endpoint(ExerciseCreateRequest(name="   "))

        self.assertEqual(exc.exception.status_code, 400)

    def test_update_exercise_renames_existing_row(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        response = update_exercise_endpoint(
            deadlift_id,
            ExerciseUpdateRequest(name="  Trap Bar  Deadlift "),
        )

        self.assertEqual(response["exercise"]["id"], deadlift_id)
        self.assertEqual(response["exercise"]["name"], "Trap Bar Deadlift")

    def test_update_exercise_can_toggle_activity(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        response = update_exercise_endpoint(
            deadlift_id,
            ExerciseUpdateRequest(is_active=False),
        )

        self.assertFalse(response["exercise"]["is_active"])
        active_names = [exercise["name"] for exercise in get_exercises()["exercises"]]
        all_names = [
            exercise["name"]
            for exercise in get_exercises(include_inactive=True)["exercises"]
        ]
        self.assertNotIn("Deadlift", active_names)
        self.assertIn("Deadlift", all_names)

    def test_replace_exercise_weights_normalizes_values(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        response = replace_exercise_weights_endpoint(
            deadlift_id,
            ExerciseWeightsUpdateRequest(weights=[52.5, 50, 50, 0]),
        )

        self.assertEqual(response["weights"], [0.0, 50.0, 52.5])

    def test_replace_exercise_weights_rejects_negative_values(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            replace_exercise_weights_endpoint(
                self.exercise_id("Deadlift"),
                ExerciseWeightsUpdateRequest(weights=[-1]),
            )

        self.assertEqual(exc.exception.status_code, 400)

    def test_reorder_exercises_updates_sort_order(self) -> None:
        exercises = get_exercises(include_inactive=True)["exercises"]
        exercise_ids = [exercise["id"] for exercise in exercises]

        response = reorder_exercises_endpoint(
            ExerciseOrderUpdateRequest(exercise_ids=list(reversed(exercise_ids)))
        )

        self.assertEqual(
            [exercise["id"] for exercise in response["exercises"]],
            list(reversed(exercise_ids)),
        )

    def test_reorder_exercises_rejects_missing_ids(self) -> None:
        exercises = get_exercises(include_inactive=True)["exercises"]

        with self.assertRaises(HTTPException) as exc:
            reorder_exercises_endpoint(
                ExerciseOrderUpdateRequest(
                    exercise_ids=[exercise["id"] for exercise in exercises[:-1]]
                )
            )

        self.assertEqual(exc.exception.status_code, 400)

    def test_update_exercise_returns_404_for_missing_row(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            update_exercise_endpoint(
                9999,
                ExerciseUpdateRequest(name="Missing"),
            )

        self.assertEqual(exc.exception.status_code, 404)

    def test_update_exercise_returns_409_for_duplicate_name(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        with self.assertRaises(HTTPException) as exc:
            update_exercise_endpoint(
                deadlift_id,
                ExerciseUpdateRequest(name="Goblet Squat"),
            )

        self.assertEqual(exc.exception.status_code, 409)

    def test_exercise_request_models_validate_lengths(self) -> None:
        with self.assertRaises(Exception):
            ExerciseCreateRequest(name="")

        with self.assertRaises(Exception):
            ExerciseUpdateRequest(name="")


if __name__ == "__main__":
    unittest.main()
