import tempfile
import unittest
from pathlib import Path

from app import config
from app.db import get_db, init_db
from app.repositories.drafts import (
    clear_active_draft,
    get_active_draft,
    replace_active_draft,
)
from app.services.backup_service import reset_database_data


class DraftRepositoryTests(unittest.TestCase):
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

    def draft(self) -> dict:
        return {
            "started_at": "2026-06-01T10:00:00",
            "session_rpe": 6,
            "lower_back_pain": 2,
            "workout_exercises": [
                {
                    "id": 1,
                    "exercise_id": self.exercise_id("Deadlift"),
                    "exercise_name": "Deadlift",
                    "profile_key": "deadlift",
                    "position": 1,
                    "sets": [
                        {
                            "id": 1,
                            "set_number": 1,
                            "weight": 100.0,
                            "reps": 5,
                            "created_at": "2026-06-01T10:05:00",
                        },
                    ],
                }
            ],
            "next_workout_exercise_id": 2,
            "next_set_id": 2,
        }

    def test_init_db_creates_active_draft_tables(self) -> None:
        with get_db() as conn:
            table_names = {
                row["name"]
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                )
            }

        self.assertIn("active_workout_draft", table_names)
        self.assertIn("active_draft_exercises", table_names)
        self.assertIn("active_draft_sets", table_names)

    def test_replace_and_get_active_draft_round_trips_current_shape(self) -> None:
        draft = self.draft()

        replace_active_draft(draft)
        loaded = get_active_draft()

        self.assertEqual(loaded, draft)

    def test_clear_active_draft_removes_child_rows(self) -> None:
        replace_active_draft(self.draft())

        clear_active_draft()

        with get_db() as conn:
            counts = {
                "draft": conn.execute(
                    "SELECT COUNT(*) FROM active_workout_draft"
                ).fetchone()[0],
                "exercises": conn.execute(
                    "SELECT COUNT(*) FROM active_draft_exercises"
                ).fetchone()[0],
                "sets": conn.execute(
                    "SELECT COUNT(*) FROM active_draft_sets"
                ).fetchone()[0],
            }

        self.assertEqual(counts, {"draft": 0, "exercises": 0, "sets": 0})

    def test_reset_database_data_clears_active_draft(self) -> None:
        replace_active_draft(self.draft())

        reset_database_data()

        self.assertIsNone(get_active_draft())


if __name__ == "__main__":
    unittest.main()
