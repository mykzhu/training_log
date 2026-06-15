import tempfile
import unittest
from pathlib import Path

from app import config
from app.db import get_db, init_db
from app.services.backup_service import (
    build_backup_payload,
    reset_database_data,
    restore_backup_payload,
)


class BackupServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def insert_workout(self) -> int:
        with get_db() as conn:
            exercise = conn.execute(
                "SELECT id FROM exercises WHERE name = ?",
                ("Deadlift",),
            ).fetchone()
            exercise_id = int(exercise["id"])

            workout_cursor = conn.execute(
                """
                INSERT INTO workouts (
                    workout_date,
                    created_at,
                    finished_at,
                    session_rpe,
                    lower_back_pain,
                    duration_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-06-01",
                    "2026-06-01T10:00:00",
                    "2026-06-01T11:00:00",
                    7,
                    2,
                    3600,
                ),
            )
            workout_id = int(workout_cursor.lastrowid)

            workout_exercise_cursor = conn.execute(
                """
                INSERT INTO workout_exercises (workout_id, exercise_id, position)
                VALUES (?, ?, ?)
                """,
                (workout_id, exercise_id, 1),
            )
            workout_exercise_id = int(workout_exercise_cursor.lastrowid)

            conn.execute(
                """
                INSERT INTO set_entries (
                    workout_exercise_id,
                    set_number,
                    weight,
                    reps,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    workout_exercise_id,
                    1,
                    100.0,
                    5,
                    "2026-06-01T10:10:00",
                ),
            )

        return workout_id

    def test_build_and_restore_backup_payload_round_trips_schema_v2(self) -> None:
        workout_id = self.insert_workout()

        payload = build_backup_payload()
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(len(payload["tables"]["workouts"]), 1)
        self.assertEqual(len(payload["tables"]["workout_exercises"]), 1)
        self.assertEqual(len(payload["tables"]["set_entries"]), 1)

        reset_database_data()
        restore_backup_payload(payload)

        with get_db() as conn:
            workout = conn.execute(
                """
                SELECT session_rpe, lower_back_pain, duration_seconds
                FROM workouts
                WHERE id = ?
                """,
                (workout_id,),
            ).fetchone()
            set_count = conn.execute("SELECT COUNT(*) FROM set_entries").fetchone()[0]

        self.assertEqual(workout["session_rpe"], 7)
        self.assertEqual(workout["lower_back_pain"], 2)
        self.assertEqual(workout["duration_seconds"], 3600)
        self.assertEqual(set_count, 1)

    def test_restore_backup_payload_accepts_schema_v1_without_duration(self) -> None:
        payload = {
            "app": "training-log",
            "schema_version": 1,
            "exported_at": "2026-06-01T12:00:00",
            "tables": {
                "exercises": [{"id": 1, "name": "Deadlift"}],
                "workouts": [
                    {
                        "id": 1,
                        "workout_date": "2026-06-01",
                        "created_at": "2026-06-01T10:00:00",
                        "finished_at": "2026-06-01T11:00:00",
                        "session_rpe": 6,
                        "lower_back_pain": None,
                    }
                ],
                "workout_exercises": [
                    {
                        "id": 1,
                        "workout_id": 1,
                        "exercise_id": 1,
                        "position": 1,
                    }
                ],
                "set_entries": [
                    {
                        "id": 1,
                        "workout_exercise_id": 1,
                        "set_number": 1,
                        "weight": 80.0,
                        "reps": 8,
                        "created_at": "2026-06-01T10:15:00",
                    }
                ],
            },
        }

        restore_backup_payload(payload)

        with get_db() as conn:
            workout = conn.execute(
                """
                SELECT session_rpe, lower_back_pain, duration_seconds
                FROM workouts
                WHERE id = 1
                """
            ).fetchone()

        self.assertEqual(workout["session_rpe"], 6)
        self.assertIsNone(workout["lower_back_pain"])
        self.assertIsNone(workout["duration_seconds"])

    def test_reset_database_data_clears_workouts_and_reseeds_defaults(self) -> None:
        self.insert_workout()

        reset_database_data()

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]
            exercise_names = [
                row["name"]
                for row in conn.execute("SELECT name FROM exercises ORDER BY id ASC")
            ]

        self.assertEqual(workout_count, 0)
        self.assertEqual(exercise_names, list(config.DEFAULT_EXERCISES))


if __name__ == "__main__":
    unittest.main()
