import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import config
from app.db import get_db, init_db
from app.services import draft_service
from app.services.draft_service import (
    add_exercise_to_active_draft,
    add_set_to_active_draft,
    clear_active_workout_draft,
    create_workout_draft,
    delete_active_draft_exercise,
    delete_active_draft_set,
    duplicate_active_draft_set,
    finish_active_workout,
    get_active_workout_draft,
    get_draft_set,
    get_draft_workout_details,
    get_draft_workout_exercise,
    renumber_draft_sets,
    save_workout_draft_to_db,
    start_active_workout_draft,
    update_active_draft_metadata,
)


class DraftServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_active_draft = draft_service.ACTIVE_WORKOUT_DRAFT
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()
        clear_active_workout_draft()

    def tearDown(self) -> None:
        draft_service.ACTIVE_WORKOUT_DRAFT = self.original_active_draft
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

    def draft_with_sets(self) -> dict:
        return {
            "started_at": "2026-06-01T10:00:00",
            "session_rpe": 6,
            "lower_back_pain": 2,
            "workout_exercises": [
                {
                    "id": 1,
                    "exercise_id": self.exercise_id("Deadlift"),
                    "exercise_name": "Deadlift",
                    "position": 1,
                    "sets": [
                        {
                            "id": 1,
                            "set_number": 1,
                            "weight": 100.0,
                            "reps": 5,
                            "created_at": "2026-06-01T10:05:00",
                        },
                        {
                            "id": 2,
                            "set_number": 2,
                            "weight": 90.0,
                            "reps": 8,
                            "created_at": "2026-06-01T10:10:00",
                        },
                    ],
                }
            ],
            "next_workout_exercise_id": 2,
            "next_set_id": 3,
        }

    def test_create_workout_draft_returns_empty_active_shape(self) -> None:
        draft = create_workout_draft()

        self.assertIsNone(draft["session_rpe"])
        self.assertIsNone(draft["lower_back_pain"])
        self.assertEqual(draft["workout_exercises"], [])
        self.assertEqual(draft["next_workout_exercise_id"], 1)
        self.assertEqual(draft["next_set_id"], 1)

    def test_draft_lookup_and_details_use_current_sets(self) -> None:
        draft = self.draft_with_sets()

        draft_exercise = get_draft_workout_exercise(draft, 1)
        found_set = get_draft_set(draft, 2)
        details = get_draft_workout_details(draft)

        self.assertIsNotNone(found_set)
        self.assertIs(draft_exercise, draft["workout_exercises"][0])
        self.assertIs(found_set[1], draft["workout_exercises"][0]["sets"][1])
        self.assertEqual(details[0]["total_volume"], 1220.0)
        self.assertEqual(details[0]["total_reps"], 13)
        self.assertEqual(details[0]["default_weight"], 90.0)
        self.assertEqual(details[0]["default_reps"], 8)

    def test_renumber_draft_sets_keeps_contiguous_order(self) -> None:
        draft_exercise = self.draft_with_sets()["workout_exercises"][0]
        draft_exercise["sets"] = [draft_exercise["sets"][1]]

        renumber_draft_sets(draft_exercise)

        self.assertEqual(draft_exercise["sets"][0]["set_number"], 1)

    def test_save_workout_draft_to_db_persists_completed_workout(self) -> None:
        workout_id = save_workout_draft_to_db(self.draft_with_sets())

        with get_db() as conn:
            workout = conn.execute(
                """
                SELECT workout_date, created_at, session_rpe, lower_back_pain
                FROM workouts
                WHERE id = ?
                """,
                (workout_id,),
            ).fetchone()
            workout_exercise = conn.execute(
                """
                SELECT exercise_id, position
                FROM workout_exercises
                WHERE workout_id = ?
                """,
                (workout_id,),
            ).fetchone()
            sets = conn.execute(
                """
                SELECT set_number, weight, reps
                FROM set_entries
                WHERE workout_exercise_id = (
                    SELECT id FROM workout_exercises WHERE workout_id = ?
                )
                ORDER BY set_number
                """,
                (workout_id,),
            ).fetchall()

        self.assertEqual(workout["workout_date"], "2026-06-01")
        self.assertEqual(workout["created_at"], "2026-06-01T10:00:00")
        self.assertEqual(workout["session_rpe"], 6)
        self.assertEqual(workout["lower_back_pain"], 2)
        self.assertEqual(workout_exercise["position"], 1)
        self.assertEqual(
            [(row["weight"], row["reps"]) for row in sets],
            [(100.0, 5), (90.0, 8)],
        )

    def test_active_draft_operations_manage_single_in_memory_draft(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        draft, created = start_active_workout_draft()
        same_draft, created_again = start_active_workout_draft()

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertIs(same_draft, draft)

        self.assertTrue(update_active_draft_metadata(session_rpe=7, lower_back_pain=3))
        draft_exercise = add_exercise_to_active_draft(
            exercise_id=deadlift_id,
            exercise_name="Deadlift",
        )
        first_set = add_set_to_active_draft(
            draft_exercise_id=int(draft_exercise["id"]),
            weight=100.0,
            reps=5,
        )
        duplicate_set = duplicate_active_draft_set(
            draft_exercise_id=int(draft_exercise["id"]),
        )

        self.assertEqual(get_active_workout_draft()["session_rpe"], 7)
        self.assertEqual(first_set["set_number"], 1)
        self.assertEqual(duplicate_set["weight"], 100.0)
        self.assertEqual(duplicate_set["reps"], 5)

        self.assertTrue(delete_active_draft_set(int(first_set["id"])))
        self.assertEqual(draft_exercise["sets"][0]["set_number"], 1)

        self.assertTrue(delete_active_draft_exercise(int(draft_exercise["id"])))
        self.assertEqual(get_active_workout_draft()["workout_exercises"], [])

    def test_finish_active_workout_persists_and_clears_draft(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        start_active_workout_draft()
        update_active_draft_metadata(session_rpe=6, lower_back_pain=2)
        draft_exercise = add_exercise_to_active_draft(
            exercise_id=deadlift_id,
            exercise_name="Deadlift",
        )
        add_set_to_active_draft(
            draft_exercise_id=int(draft_exercise["id"]),
            weight=100.0,
            reps=5,
        )

        workout_id = finish_active_workout()

        self.assertIsNotNone(workout_id)
        self.assertIsNone(get_active_workout_draft())

        with get_db() as conn:
            workout = conn.execute(
                """
                SELECT session_rpe, lower_back_pain
                FROM workouts
                WHERE id = ?
                """,
                (workout_id,),
            ).fetchone()
            set_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM set_entries se
                JOIN workout_exercises we ON we.id = se.workout_exercise_id
                WHERE we.workout_id = ?
                """,
                (workout_id,),
            ).fetchone()[0]

        self.assertEqual(workout["session_rpe"], 6)
        self.assertEqual(workout["lower_back_pain"], 2)
        self.assertEqual(set_count, 1)

    def test_finish_failure_keeps_draft_and_creates_no_workout(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        start_active_workout_draft()
        draft_exercise = add_exercise_to_active_draft(
            exercise_id=deadlift_id,
            exercise_name="Deadlift",
        )
        add_set_to_active_draft(
            draft_exercise_id=int(draft_exercise["id"]),
            weight=100.0,
            reps=5,
        )

        with patch(
            "app.repositories.drafts.insert_completed_exercises_and_sets",
            side_effect=RuntimeError("insertion failed"),
        ):
            with self.assertRaises(RuntimeError):
                finish_active_workout()

        self.assertIsNotNone(get_active_workout_draft())

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]
            set_count = conn.execute("SELECT COUNT(*) FROM set_entries").fetchone()[0]

        self.assertEqual(workout_count, 0)
        self.assertEqual(set_count, 0)

    def test_active_draft_recovers_from_persistent_storage(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        start_active_workout_draft()
        draft_exercise = add_exercise_to_active_draft(
            exercise_id=deadlift_id,
            exercise_name="Deadlift",
        )
        add_set_to_active_draft(
            draft_exercise_id=int(draft_exercise["id"]),
            weight=100.0,
            reps=5,
        )

        draft_service.ACTIVE_WORKOUT_DRAFT = None

        recovered = get_active_workout_draft()

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["workout_exercises"][0]["exercise_name"], "Deadlift")
        self.assertEqual(recovered["workout_exercises"][0]["sets"][0]["weight"], 100.0)


if __name__ == "__main__":
    unittest.main()
