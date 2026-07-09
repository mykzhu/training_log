import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import config
from app.db import get_db, init_db
from app.migrations import v010_exercise_measurement_type
from app.migrations import v011_snapshot_exercise_measurements
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
            crunches = conn.execute(
                """
                SELECT measurement_type, reps_unit
                FROM exercises
                WHERE name = 'Crunches'
                """
            ).fetchone()
            carry = conn.execute(
                """
                SELECT measurement_type, reps_unit
                FROM exercises
                WHERE name LIKE '%Carry%'
                LIMIT 1
                """
            ).fetchone()
            workout_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(workouts)")
            }
            workout_exercise_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(workout_exercises)")
            }
            active_draft_exercise_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(active_draft_exercises)")
            }
            garmin_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(garmin_daily_metrics)")
            }

        self.assertEqual(
            [int(row["version"]) for row in rows],
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        )
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
                "exercise_option_settings",
                "exercise_measurement_type",
                "snapshot_exercise_measurements",
            ],
        )
        self.assertGreater(exercise_count, 0)
        self.assertIsNotNone(crunches)
        self.assertEqual(crunches["measurement_type"], "bodyweight_reps")
        self.assertEqual(crunches["reps_unit"], "reps")
        if carry is not None:
            self.assertEqual(carry["measurement_type"], "loaded_carry_time")
            self.assertEqual(carry["reps_unit"], "sec")
        self.assertIn("session_rpe", workout_columns)
        self.assertIn("lower_back_pain", workout_columns)
        self.assertIn("duration_seconds", workout_columns)
        self.assertIn("measurement_type", workout_exercise_columns)
        self.assertIn("reps_unit", workout_exercise_columns)
        self.assertIn("measurement_type", active_draft_exercise_columns)
        self.assertIn("reps_unit", active_draft_exercise_columns)
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
                SELECT name, profile_key, is_active, measurement_type, reps_unit
                FROM exercises
                WHERE id = 1
                """
            ).fetchone()
            deadlift_count = conn.execute(
                "SELECT COUNT(*) FROM exercises WHERE name = ?",
                ("Deadlift",),
            ).fetchone()[0]

        self.assertEqual(versions, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
        self.assertEqual(exercise["name"], "Romanian Deadlift")
        self.assertEqual(exercise["profile_key"], "deadlift")
        self.assertEqual(exercise["is_active"], 1)
        self.assertEqual(exercise["measurement_type"], "weighted_reps")
        self.assertEqual(exercise["reps_unit"], "reps")
        self.assertEqual(deadlift_count, 0)

    def test_v010_seeds_existing_crunch_and_carry_measurement_types(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                """
                CREATE TABLE exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
                """
            )
            conn.executemany(
                "INSERT INTO exercises (name) VALUES (?)",
                [
                    ("Crunches",),
                    ("Suitcase carry",),
                    ("Bench Press",),
                ],
            )

            v010_exercise_measurement_type.up(conn)

            rows = {
                row["name"]: row
                for row in conn.execute(
                    """
                    SELECT name, measurement_type, reps_unit
                    FROM exercises
                    """
                ).fetchall()
            }
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(exercises)")
            }
        finally:
            conn.close()

        self.assertIn("measurement_type", columns)
        self.assertIn("reps_unit", columns)
        self.assertEqual(rows["Crunches"]["measurement_type"], "bodyweight_reps")
        self.assertEqual(rows["Crunches"]["reps_unit"], "reps")
        self.assertEqual(rows["Suitcase carry"]["measurement_type"], "loaded_carry_time")
        self.assertEqual(rows["Suitcase carry"]["reps_unit"], "sec")
        self.assertEqual(rows["Bench Press"]["measurement_type"], "weighted_reps")
        self.assertEqual(rows["Bench Press"]["reps_unit"], "reps")

    def test_v011_backfills_workout_and_active_draft_measurement_snapshots(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(
                """
                CREATE TABLE exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    measurement_type TEXT,
                    reps_unit TEXT
                );
                CREATE TABLE workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workout_date TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    finished_at TEXT
                );
                CREATE TABLE workout_exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workout_id INTEGER NOT NULL,
                    exercise_id INTEGER NOT NULL,
                    position INTEGER NOT NULL
                );
                CREATE TABLE active_workout_draft (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    started_at TEXT NOT NULL,
                    next_workout_exercise_id INTEGER NOT NULL,
                    next_set_id INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE active_draft_exercises (
                    id INTEGER PRIMARY KEY,
                    draft_id INTEGER NOT NULL DEFAULT 1,
                    exercise_id INTEGER NOT NULL,
                    position INTEGER NOT NULL
                );
                """
            )
            conn.execute(
                """
                INSERT INTO exercises (id, name, measurement_type, reps_unit)
                VALUES (1, 'Suitcase carry', 'loaded_carry_time', 'sec')
                """
            )
            conn.execute(
                """
                INSERT INTO workouts (id, workout_date, created_at, finished_at)
                VALUES (1, '2026-06-01', '2026-06-01T10:00:00', NULL)
                """
            )
            conn.execute(
                """
                INSERT INTO workout_exercises (id, workout_id, exercise_id, position)
                VALUES (1, 1, 1, 1)
                """
            )
            conn.execute(
                """
                INSERT INTO active_workout_draft (
                    id,
                    started_at,
                    next_workout_exercise_id,
                    next_set_id,
                    updated_at
                )
                VALUES (1, '2026-06-02T10:00:00', 2, 1, '2026-06-02T10:00:00')
                """
            )
            conn.execute(
                """
                INSERT INTO active_draft_exercises (id, draft_id, exercise_id, position)
                VALUES (1, 1, 1, 1)
                """
            )

            v011_snapshot_exercise_measurements.up(conn)

            workout_snapshot = conn.execute(
                """
                SELECT measurement_type, reps_unit
                FROM workout_exercises
                WHERE id = 1
                """
            ).fetchone()
            draft_snapshot = conn.execute(
                """
                SELECT measurement_type, reps_unit
                FROM active_draft_exercises
                WHERE id = 1
                """
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(workout_snapshot["measurement_type"], "loaded_carry_time")
        self.assertEqual(workout_snapshot["reps_unit"], "sec")
        self.assertEqual(draft_snapshot["measurement_type"], "loaded_carry_time")
        self.assertEqual(draft_snapshot["reps_unit"], "sec")

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
