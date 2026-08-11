import tempfile
import unittest
from pathlib import Path

from app import config
from app.db import get_db, init_db
from app.services.backup_service import (
    BACKUP_SCHEMA_VERSION,
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
                INSERT INTO workout_exercises (
                    workout_id,
                    exercise_id,
                    position,
                    measurement_type,
                    reps_unit
                )
                SELECT
                    ?,
                    e.id,
                    ?,
                    e.measurement_type,
                    e.reps_unit
                FROM exercises e
                WHERE e.id = ?
                """,
                (workout_id, 1, exercise_id),
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

    def insert_garmin_metric(self) -> None:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO garmin_daily_metrics (
                    date,
                    resting_heart_rate,
                    hrv_ms,
                    stress_avg,
                    body_battery_start,
                    body_battery_end,
                    steps,
                    synced_at,
                    raw_diagnostics
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-06-26",
                    52,
                    48.0,
                    30,
                    82,
                    37,
                    12345,
                    "2026-06-26T08:00:00",
                    '{"summary":{"ok":true}}',
                ),
            )

    def test_build_and_restore_backup_payload_round_trips_current_schema(self) -> None:
        workout_id = self.insert_workout()
        self.insert_garmin_metric()

        payload = build_backup_payload()
        self.assertEqual(payload["schema_version"], BACKUP_SCHEMA_VERSION)
        self.assertIn("exercise_weight_options", payload["tables"])
        self.assertIn("analysis_profiles", payload["tables"])
        profile_keys = {
            profile["key"]
            for profile in payload["tables"]["analysis_profiles"]
        }
        self.assertIn("back_rehab", profile_keys)
        self.assertIn("core_stability", profile_keys)
        self.assertIn("mobility", profile_keys)
        self.assertEqual(len(payload["tables"]["workouts"]), 1)
        self.assertEqual(len(payload["tables"]["workout_exercises"]), 1)
        self.assertEqual(len(payload["tables"]["set_entries"]), 1)
        self.assertEqual(payload["tables"]["exercises"][0]["is_active"], 1)
        self.assertIn("default_reps", payload["tables"]["exercises"][0])
        self.assertIn("max_reps", payload["tables"]["exercises"][0])
        self.assertIn("measurement_type", payload["tables"]["exercises"][0])
        self.assertIn("reps_unit", payload["tables"]["exercises"][0])
        self.assertIn(
            "measurement_type",
            payload["tables"]["workout_exercises"][0],
        )
        self.assertIn("reps_unit", payload["tables"]["workout_exercises"][0])
        self.assertEqual(len(payload["tables"]["garmin_daily_metrics"]), 1)
        self.assertNotIn(
            "raw_diagnostics",
            payload["tables"]["garmin_daily_metrics"][0],
        )
        self.assertNotIn("garmin_sync_settings", payload["tables"])

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
            weight_count = conn.execute(
                "SELECT COUNT(*) FROM exercise_weight_options"
            ).fetchone()[0]
            garmin_metric = conn.execute(
                """
                SELECT resting_heart_rate, steps, raw_diagnostics
                FROM garmin_daily_metrics
                WHERE date = ?
                """,
                ("2026-06-26",),
            ).fetchone()
            workout_exercise = conn.execute(
                """
                SELECT measurement_type, reps_unit
                FROM workout_exercises
                WHERE workout_id = ?
                """,
                (workout_id,),
            ).fetchone()

        self.assertEqual(workout["session_rpe"], 7)
        self.assertEqual(workout["lower_back_pain"], 2)
        self.assertEqual(workout["duration_seconds"], 3600)
        self.assertEqual(set_count, 1)
        self.assertGreater(weight_count, 0)
        self.assertEqual(garmin_metric["resting_heart_rate"], 52)
        self.assertEqual(garmin_metric["steps"], 12345)
        self.assertEqual(garmin_metric["raw_diagnostics"], "{}")
        self.assertEqual(workout_exercise["measurement_type"], "weighted_reps")
        self.assertEqual(workout_exercise["reps_unit"], "reps")

    def test_backup_restore_preserves_duration_only_exercise(self) -> None:
        with get_db() as conn:
            exercise_cursor = conn.execute(
                """
                INSERT INTO exercises (
                    name,
                    is_active,
                    sort_order,
                    profile_key,
                    measurement_type,
                    reps_unit,
                    default_weight,
                    min_weight,
                    max_weight,
                    weight_step,
                    default_reps,
                    min_reps,
                    max_reps,
                    reps_step
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Side Plank",
                    1,
                    999,
                    "accessory",
                    "duration_only",
                    "sec",
                    0,
                    0,
                    0,
                    1,
                    30,
                    5,
                    120,
                    5,
                ),
            )
            exercise_id = int(exercise_cursor.lastrowid)
            workout_cursor = conn.execute(
                """
                INSERT INTO workouts (
                    workout_date,
                    created_at,
                    finished_at,
                    duration_seconds
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    "2026-07-01",
                    "2026-07-01T10:00:00",
                    "2026-07-01T10:30:00",
                    1800,
                ),
            )
            workout_id = int(workout_cursor.lastrowid)
            workout_exercise_cursor = conn.execute(
                """
                INSERT INTO workout_exercises (
                    workout_id,
                    exercise_id,
                    position,
                    measurement_type,
                    reps_unit
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (workout_id, exercise_id, 1, "duration_only", "sec"),
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
                (workout_exercise_id, 1, 0, 45, "2026-07-01T10:05:00"),
            )

        payload = build_backup_payload()
        reset_database_data()
        restore_backup_payload(payload)

        with get_db() as conn:
            exercise = conn.execute(
                """
                SELECT measurement_type, reps_unit, default_weight, max_weight
                FROM exercises
                WHERE name = ?
                """,
                ("Side Plank",),
            ).fetchone()
            workout_exercise = conn.execute(
                """
                SELECT measurement_type, reps_unit
                FROM workout_exercises
                WHERE exercise_id = ?
                """,
                (exercise_id,),
            ).fetchone()

        self.assertEqual(exercise["measurement_type"], "duration_only")
        self.assertEqual(exercise["reps_unit"], "sec")
        self.assertEqual(exercise["default_weight"], 0)
        self.assertEqual(exercise["max_weight"], 0)
        self.assertEqual(workout_exercise["measurement_type"], "duration_only")
        self.assertEqual(workout_exercise["reps_unit"], "sec")

    def test_backup_restore_preserves_rehab_profiles(self) -> None:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO exercises (
                    name,
                    is_active,
                    sort_order,
                    profile_key,
                    measurement_type,
                    reps_unit,
                    default_weight,
                    min_weight,
                    max_weight,
                    weight_step,
                    default_reps,
                    min_reps,
                    max_reps,
                    reps_step
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Dead Bug",
                    1,
                    1001,
                    "core_stability",
                    "reps_only",
                    "reps",
                    0,
                    0,
                    0,
                    1,
                    10,
                    1,
                    50,
                    1,
                ),
            )
            conn.execute(
                """
                INSERT INTO exercises (
                    name,
                    is_active,
                    sort_order,
                    profile_key,
                    measurement_type,
                    reps_unit,
                    default_weight,
                    min_weight,
                    max_weight,
                    weight_step,
                    default_reps,
                    min_reps,
                    max_reps,
                    reps_step
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Cat-Cow",
                    1,
                    1002,
                    "mobility",
                    "reps_only",
                    "reps",
                    0,
                    0,
                    0,
                    1,
                    10,
                    1,
                    50,
                    1,
                ),
            )

        payload = build_backup_payload()
        reset_database_data()
        restore_backup_payload(payload)

        with get_db() as conn:
            exercise_profiles = {
                row["name"]: row["profile_key"]
                for row in conn.execute(
                    """
                    SELECT name, profile_key
                    FROM exercises
                    WHERE name IN ('Dead Bug', 'Cat-Cow')
                    """
                )
            }
            profile_keys = {
                row["key"]
                for row in conn.execute(
                    """
                    SELECT key
                    FROM analysis_profiles
                    WHERE key IN ('back_rehab', 'core_stability', 'mobility')
                    """
                )
            }

        self.assertEqual(exercise_profiles["Dead Bug"], "core_stability")
        self.assertEqual(exercise_profiles["Cat-Cow"], "mobility")
        self.assertEqual(
            profile_keys,
            {"back_rehab", "core_stability", "mobility"},
        )

    def test_current_backup_contains_no_garmin_raw_diagnostics(self) -> None:
        self.insert_garmin_metric()

        payload = build_backup_payload()
        garmin_metrics = payload["tables"]["garmin_daily_metrics"]

        self.assertEqual(len(garmin_metrics), 1)
        self.assertNotIn("raw_diagnostics", garmin_metrics[0])
        self.assertNotIn("garmin_sync_settings", payload["tables"])

    def test_schema_v6_restore_defaults_missing_exercise_measurement_fields(self) -> None:
        self.insert_workout()
        payload = build_backup_payload()
        payload["schema_version"] = 6
        for exercise in payload["tables"]["exercises"]:
            exercise.pop("measurement_type", None)
            exercise.pop("reps_unit", None)
            for option_field in (
                "default_weight",
                "min_weight",
                "max_weight",
                "weight_step",
                "default_reps",
                "min_reps",
                "max_reps",
                "reps_step",
            ):
                exercise.pop(option_field, None)

        reset_database_data()
        restore_backup_payload(payload)

        with get_db() as conn:
            rows = {
                row["name"]: row
                for row in conn.execute(
                    """
                    SELECT name, measurement_type, reps_unit
                    FROM exercises
                    """
                )
            }

        self.assertEqual(rows["Crunches"]["measurement_type"], "bodyweight_reps")
        self.assertEqual(rows["Crunches"]["reps_unit"], "reps")
        self.assertEqual(rows["Deadlift"]["measurement_type"], "weighted_reps")
        self.assertEqual(rows["Deadlift"]["reps_unit"], "reps")

    def test_schema_v7_restore_defaults_missing_exercise_measurement_fields(self) -> None:
        self.insert_workout()
        payload = build_backup_payload()
        payload["schema_version"] = 7
        for exercise in payload["tables"]["exercises"]:
            exercise.pop("measurement_type", None)
            exercise.pop("reps_unit", None)

        reset_database_data()
        restore_backup_payload(payload)

        with get_db() as conn:
            rows = {
                row["name"]: row
                for row in conn.execute(
                    """
                    SELECT name, measurement_type, reps_unit
                    FROM exercises
                    """
                )
            }

        self.assertEqual(rows["Crunches"]["measurement_type"], "bodyweight_reps")
        self.assertEqual(rows["Crunches"]["reps_unit"], "reps")
        self.assertEqual(rows["Deadlift"]["measurement_type"], "weighted_reps")
        self.assertEqual(rows["Deadlift"]["reps_unit"], "reps")

    def test_schema_v8_restore_defaults_workout_exercise_measurement_snapshot(self) -> None:
        self.insert_workout()
        payload = build_backup_payload()
        payload["schema_version"] = 8
        for workout_exercise in payload["tables"]["workout_exercises"]:
            workout_exercise.pop("measurement_type", None)
            workout_exercise.pop("reps_unit", None)

        reset_database_data()
        restore_backup_payload(payload)

        with get_db() as conn:
            row = conn.execute(
                """
                SELECT we.measurement_type, we.reps_unit
                FROM workout_exercises we
                JOIN exercises e ON e.id = we.exercise_id
                WHERE e.name = 'Deadlift'
                """
            ).fetchone()

        self.assertEqual(row["measurement_type"], "weighted_reps")
        self.assertEqual(row["reps_unit"], "reps")

    def test_schema_v5_restore_accepts_raw_diagnostics(self) -> None:
        self.insert_workout()
        self.insert_garmin_metric()
        payload = build_backup_payload()
        payload["schema_version"] = 5
        payload["tables"]["garmin_daily_metrics"][0]["raw_diagnostics"] = {
            "summary": {"ok": True}
        }

        reset_database_data()
        restore_backup_payload(payload)

        with get_db() as conn:
            garmin_metric = conn.execute(
                """
                SELECT raw_diagnostics
                FROM garmin_daily_metrics
                WHERE date = ?
                """,
                ("2026-06-26",),
            ).fetchone()

        self.assertEqual(
            garmin_metric["raw_diagnostics"],
            '{"summary":{"ok":true}}',
        )

    def test_schema_v4_restore_accepts_raw_diagnostics_without_profiles(self) -> None:
        self.insert_workout()
        self.insert_garmin_metric()
        payload = build_backup_payload()
        payload["schema_version"] = 4
        payload["tables"].pop("analysis_profiles")
        payload["tables"]["garmin_daily_metrics"][0]["raw_diagnostics"] = (
            '{"summary":{"ok":true}}'
        )

        reset_database_data()
        restore_backup_payload(payload)

        with get_db() as conn:
            garmin_metric = conn.execute(
                """
                SELECT raw_diagnostics
                FROM garmin_daily_metrics
                WHERE date = ?
                """,
                ("2026-06-26",),
            ).fetchone()
            profile_count = conn.execute(
                "SELECT COUNT(*) FROM analysis_profiles"
            ).fetchone()[0]
            profile_keys = {
                row["key"]
                for row in conn.execute(
                    "SELECT key FROM analysis_profiles"
                ).fetchall()
            }

        self.assertEqual(
            garmin_metric["raw_diagnostics"],
            '{"summary":{"ok":true}}',
        )
        self.assertGreater(profile_count, 0)
        self.assertIn("back_rehab", profile_keys)
        self.assertIn("core_stability", profile_keys)
        self.assertIn("mobility", profile_keys)

    def test_schema_v6_restore_rejects_missing_required_garmin_fields(self) -> None:
        self.insert_garmin_metric()
        payload = build_backup_payload()
        payload["tables"]["garmin_daily_metrics"][0].pop("synced_at")

        with self.assertRaises(ValueError):
            restore_backup_payload(payload)

    def test_schema_v3_restore_preserves_exact_inactive_empty_weights(self) -> None:
        self.insert_workout()
        with get_db() as conn:
            crunches_id = conn.execute(
                "SELECT id FROM exercises WHERE name = ?",
                ("Crunches",),
            ).fetchone()["id"]
            conn.execute(
                "UPDATE exercises SET is_active = 0 WHERE id = ?",
                (crunches_id,),
            )
            conn.execute(
                "DELETE FROM exercise_weight_options WHERE exercise_id = ?",
                (crunches_id,),
            )

        payload = build_backup_payload()
        payload["schema_version"] = 3
        payload["tables"].pop("garmin_daily_metrics")
        reset_database_data()
        restore_backup_payload(payload)

        with get_db() as conn:
            exercise = conn.execute(
                "SELECT is_active FROM exercises WHERE id = ?",
                (crunches_id,),
            ).fetchone()
            weight_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM exercise_weight_options
                WHERE exercise_id = ?
                """,
                (crunches_id,),
            ).fetchone()[0]

        self.assertEqual(exercise["is_active"], 0)
        self.assertEqual(weight_count, 0)

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
            weights = conn.execute(
                """
                SELECT weight
                FROM exercise_weight_options
                WHERE exercise_id = 1
                ORDER BY weight ASC
                """
            ).fetchall()

        self.assertEqual(workout["session_rpe"], 6)
        self.assertIsNone(workout["lower_back_pain"])
        self.assertIsNone(workout["duration_seconds"])
        self.assertIn(80.0, [row["weight"] for row in weights])

    def test_restore_backup_payload_accepts_schema_v2_and_derives_weights(self) -> None:
        payload = {
            "app": "training-log",
            "schema_version": 2,
            "exported_at": "2026-06-01T12:00:00",
            "tables": {
                "exercises": [{"id": 1, "name": "Squats"}],
                "workouts": [
                    {
                        "id": 1,
                        "workout_date": "2026-06-01",
                        "created_at": "2026-06-01T10:00:00",
                        "finished_at": "2026-06-01T11:00:00",
                        "session_rpe": 6,
                        "lower_back_pain": 1,
                        "duration_seconds": 3600,
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
                        "weight": 18.25,
                        "reps": 10,
                        "created_at": "2026-06-01T10:15:00",
                    }
                ],
            },
        }

        restore_backup_payload(payload)

        with get_db() as conn:
            weights = [
                row["weight"]
                for row in conn.execute(
                    """
                    SELECT weight
                    FROM exercise_weight_options
                    WHERE exercise_id = 1
                    ORDER BY weight ASC
                    """
                )
            ]

        self.assertIn(18.25, weights)
        self.assertIn(20.0, weights)

    def test_invalid_backup_validation_happens_before_destructive_restore(self) -> None:
        self.insert_workout()
        self.insert_garmin_metric()
        payload = build_backup_payload()
        payload["tables"]["workout_exercises"][0]["exercise_id"] = 9999

        with self.assertRaises(ValueError):
            restore_backup_payload(payload)

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]
            garmin_count = conn.execute("SELECT COUNT(*) FROM garmin_daily_metrics").fetchone()[0]
            set_count = conn.execute("SELECT COUNT(*) FROM set_entries").fetchone()[0]

        self.assertEqual(workout_count, 1)
        self.assertEqual(garmin_count, 1)
        self.assertEqual(set_count, 1)

    def test_reset_database_data_clears_workouts_and_reseeds_defaults(self) -> None:
        self.insert_workout()
        self.insert_garmin_metric()

        reset_database_data()

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]
            garmin_count = conn.execute("SELECT COUNT(*) FROM garmin_daily_metrics").fetchone()[0]
            exercise_names = [
                row["name"]
                for row in conn.execute("SELECT name FROM exercises ORDER BY id ASC")
            ]

        self.assertEqual(workout_count, 0)
        self.assertEqual(garmin_count, 0)
        self.assertEqual(exercise_names, list(config.DEFAULT_EXERCISES))


if __name__ == "__main__":
    unittest.main()
