import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app import config
from app.db import get_db, init_db
import app.main as main
from app.routes.api_backup import (
    get_backup,
    import_backup_payload,
    reset_backup_data,
)
from app.services.draft_service import (
    clear_active_workout_draft,
    get_active_workout_draft,
    start_active_workout_draft,
)


class BackupApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()
        clear_active_workout_draft()

    def tearDown(self) -> None:
        clear_active_workout_draft()
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

    def test_backup_routes_are_registered(self) -> None:
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in main.app.routes
            if hasattr(route, "methods")
        }

        self.assertIn(("/api/v1/backup", ("GET",)), routes)
        self.assertIn(("/api/v1/backup/import", ("POST",)), routes)
        self.assertIn(("/api/v1/backup/reset", ("POST",)), routes)

    def test_get_backup_returns_export_payload(self) -> None:
        self.insert_workout()

        response = get_backup()

        self.assertEqual(response["app"], "training-log")
        self.assertEqual(response["schema_version"], 2)
        self.assertEqual(len(response["tables"]["workouts"]), 1)
        self.assertEqual(len(response["tables"]["workout_exercises"]), 1)
        self.assertEqual(len(response["tables"]["set_entries"]), 1)

    def test_import_backup_payload_restores_data_and_clears_active_draft(self) -> None:
        workout_id = self.insert_workout()
        payload = get_backup()
        reset_backup_data()
        start_active_workout_draft()

        response = import_backup_payload(payload)

        with get_db() as conn:
            workout = conn.execute(
                """
                SELECT session_rpe, lower_back_pain, duration_seconds
                FROM workouts
                WHERE id = ?
                """,
                (workout_id,),
            ).fetchone()

        self.assertTrue(response["restored"])
        self.assertEqual(response["counts"]["workouts"], 1)
        self.assertEqual(response["counts"]["set_entries"], 1)
        self.assertEqual(workout["session_rpe"], 7)
        self.assertEqual(workout["lower_back_pain"], 2)
        self.assertEqual(workout["duration_seconds"], 3600)
        self.assertIsNone(get_active_workout_draft())

    def test_import_backup_payload_returns_400_for_invalid_payload(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            import_backup_payload({"schema_version": 999, "tables": {}})

        self.assertEqual(exc.exception.status_code, 400)
        self.assertIn("Unsupported backup schema version", exc.exception.detail)

    def test_reset_backup_data_clears_workouts_reseeds_defaults_and_clears_draft(
        self,
    ) -> None:
        self.insert_workout()
        start_active_workout_draft()

        response = reset_backup_data()

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]
            exercise_names = [
                row["name"]
                for row in conn.execute("SELECT name FROM exercises ORDER BY id ASC")
            ]

        self.assertTrue(response["reset"])
        self.assertEqual(response["counts"]["workouts"], 0)
        self.assertEqual(response["counts"]["exercises"], len(config.DEFAULT_EXERCISES))
        self.assertEqual(workout_count, 0)
        self.assertEqual(exercise_names, list(config.DEFAULT_EXERCISES))
        self.assertIsNone(get_active_workout_draft())


if __name__ == "__main__":
    unittest.main()
