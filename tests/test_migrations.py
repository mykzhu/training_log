import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import config
from app.db import get_db, init_db
from app.migrations.runner import run_migrations


class FirstMigration:
    VERSION = 1
    NAME = "first"

    @staticmethod
    def up(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE first_migration (id INTEGER PRIMARY KEY)")


class BrokenMigration:
    VERSION = 2
    NAME = "broken"

    @staticmethod
    def up(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE rolled_back_migration (id INTEGER PRIMARY KEY)")
        raise RuntimeError("migration failed")


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_fresh_database_init_records_all_schema_migrations(self) -> None:
        init_db()

        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT version, name
                FROM schema_migrations
                ORDER BY version
                """
            ).fetchall()
            exercise_count = conn.execute(
                "SELECT COUNT(*) FROM exercises"
            ).fetchone()[0]
            workout_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(workouts)")
            }
            garmin_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(garmin_daily_metrics)")
            }

        self.assertEqual([int(row["version"]) for row in rows], [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(
            [row["name"] for row in rows],
            [
                "initial",
                "workout_metadata",
                "active_draft",
                "exercise_settings",
                "performance_indexes",
                "garmin_daily_metrics",
                "analysis_profiles",
                "garmin_auto_sync_settings",
            ],
        )
        self.assertGreater(exercise_count, 0)
        self.assertIn("session_rpe", workout_columns)
        self.assertIn("lower_back_pain", workout_columns)
        self.assertIn("duration_seconds", workout_columns)
        self.assertIn("date", garmin_columns)
        self.assertIn("resting_heart_rate", garmin_columns)
        self.assertIn("raw_diagnostics", garmin_columns)

    def test_existing_database_startup_establishes_safe_migration_baseline(self) -> None:
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
                """
            )
            conn.execute(
                "INSERT INTO exercises (id, name) VALUES (?, ?)",
                (1, "Romanian Deadlift"),
            )

        init_db()

        with get_db() as conn:
            versions = [
                int(row["version"])
                for row in conn.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
            ]
            exercise = conn.execute(
                """
                SELECT name, profile_key, is_active
                FROM exercises
                WHERE id = 1
                """
            ).fetchone()
            deadlift_count = conn.execute(
                "SELECT COUNT(*) FROM exercises WHERE name = ?",
                ("Deadlift",),
            ).fetchone()[0]

        self.assertEqual(versions, [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(exercise["name"], "Romanian Deadlift")
        self.assertEqual(exercise["profile_key"], "deadlift")
        self.assertEqual(exercise["is_active"], 1)
        self.assertEqual(deadlift_count, 0)

    def test_migration_runner_records_only_successful_migrations(self) -> None:
        conn = sqlite3.connect(":memory:")
        try:
            with self.assertRaises(RuntimeError):
                run_migrations(conn, migrations=(FirstMigration, BrokenMigration))

            recorded = conn.execute(
                """
                SELECT version, name
                FROM schema_migrations
                ORDER BY version
                """
            ).fetchall()
            rolled_back_table = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'rolled_back_migration'
                """
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(recorded, [(1, "first")])
        self.assertIsNone(rolled_back_table)


if __name__ == "__main__":
    unittest.main()
