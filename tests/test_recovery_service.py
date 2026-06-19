import math
import tempfile
import unittest
from pathlib import Path

from app import config
from app.db import get_db, init_db
from app.services.recovery_service import (
    build_recovery_context,
    format_time_gap,
    recovery_time_hint,
    rolling_load_label,
)


class RecoveryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def insert_workout(
        self,
        *,
        created_at: str,
        session_rpe: int | None,
        lower_back_pain: int | None,
        weight: float = 100.0,
        reps: int = 5,
    ) -> int:
        with get_db() as conn:
            exercise = conn.execute(
                "SELECT id FROM exercises WHERE name = ?",
                ("Deadlift",),
            ).fetchone()

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
                    created_at[:10],
                    created_at,
                    f"{created_at[:10]}T11:00:00",
                    session_rpe,
                    lower_back_pain,
                    3600,
                ),
            )
            workout_id = int(workout_cursor.lastrowid)

            workout_exercise_cursor = conn.execute(
                """
                INSERT INTO workout_exercises (workout_id, exercise_id, position)
                VALUES (?, ?, ?)
                """,
                (workout_id, int(exercise["id"]), 1),
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
                    weight,
                    reps,
                    created_at,
                ),
            )

        return workout_id

    def insert_empty_workout(self, created_at: str) -> int:
        with get_db() as conn:
            cursor = conn.execute(
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
                    created_at[:10],
                    created_at,
                    created_at,
                    None,
                    None,
                    0,
                ),
            )

        return int(cursor.lastrowid)

    def insert_workout_without_sets(self, created_at: str) -> int:
        workout_id = self.insert_empty_workout(created_at)

        with get_db() as conn:
            exercise = conn.execute(
                "SELECT id FROM exercises WHERE name = ?",
                ("Deadlift",),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO workout_exercises (workout_id, exercise_id, position)
                VALUES (?, ?, ?)
                """,
                (workout_id, int(exercise["id"]), 1),
            )

        return workout_id

    def test_format_time_gap_and_labels(self) -> None:
        self.assertEqual(format_time_gap(None), "—")
        self.assertEqual(format_time_gap(0.5), "<1h")
        self.assertEqual(format_time_gap(6), "6h")
        self.assertEqual(format_time_gap(36), "1.5d")
        self.assertEqual(format_time_gap(240), "10d")

        self.assertEqual(rolling_load_label(7.99), "Light")
        self.assertEqual(rolling_load_label(8), "Medium")
        self.assertEqual(rolling_load_label(18), "Hard")
        self.assertEqual(rolling_load_label(32), "Very hard")

        self.assertIn("No previous workout", recovery_time_hint(None))
        self.assertIn("Very short gap", recovery_time_hint(12))
        self.assertIn("Long gap", recovery_time_hint(14 * 24))

    def test_build_recovery_context_summarizes_recent_workouts(self) -> None:
        first_workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=5,
            lower_back_pain=2,
            weight=100,
            reps=5,
        )
        self.insert_workout(
            created_at="2026-06-05T10:00:00",
            session_rpe=7,
            lower_back_pain=4,
            weight=110,
            reps=5,
        )

        context = build_recovery_context(as_of="2026-06-06T10:00:00")

        self.assertTrue(context["has_history"])
        self.assertEqual(context["previous_gap_label"], "1.0d")
        self.assertEqual(context["hours_since_previous_workout"], 24)

        last_7d = context["last_7d"]
        self.assertEqual(last_7d["workout_count"], 2)
        self.assertEqual(last_7d["avg_rpe"], 6)
        self.assertEqual(last_7d["avg_back_pain"], 3)
        self.assertEqual(last_7d["load_label"], "Light")
        self.assertTrue(math.isclose(last_7d["load_score"], 5.3064))

        excluded = build_recovery_context(
            as_of="2026-06-06T10:00:00",
            exclude_workout_id=first_workout_id,
        )
        self.assertEqual(excluded["last_7d"]["workout_count"], 1)

    def test_build_recovery_context_has_low_confidence_without_history(self) -> None:
        context = build_recovery_context(as_of="2026-06-06T10:00:00")

        self.assertFalse(context["has_history"])
        self.assertEqual(context["last_7d"]["workout_count"], 0)
        self.assertEqual(context["previous_21d"]["workout_count"], 0)
        self.assertEqual(context["last_42d"]["workout_count"], 0)
        self.assertIsNone(context["relative_load"]["acute_to_baseline"])
        self.assertIsNone(context["relative_load"]["acute_back_to_baseline"])
        self.assertEqual(context["relative_load"]["baseline_confidence"], "low")

    def test_empty_workouts_are_ignored_by_recovery_context(self) -> None:
        real_workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=5,
            lower_back_pain=2,
        )
        self.insert_empty_workout("2026-06-05T10:00:00")
        self.insert_workout_without_sets("2026-06-06T10:00:00")

        context = build_recovery_context(as_of="2026-06-08T10:00:00")

        self.assertEqual(context["previous_workout_id"], real_workout_id)
        self.assertEqual(context["last_7d"]["workout_count"], 1)

    def test_build_recovery_context_returns_multi_window_baseline(self) -> None:
        for created_at in [
            "2026-05-20T10:00:00",
            "2026-05-27T10:00:00",
            "2026-06-02T10:00:00",
            "2026-06-09T10:00:00",
            "2026-06-16T10:00:00",
            "2026-06-23T10:00:00",
        ]:
            self.insert_workout(
                created_at=created_at,
                session_rpe=5,
                lower_back_pain=1,
            )

        context = build_recovery_context(as_of="2026-06-29T10:00:00")

        self.assertEqual(context["last_7d"]["days"], 7)
        self.assertEqual(context["previous_21d"]["days"], 21)
        self.assertEqual(context["last_42d"]["days"], 42)
        self.assertEqual(context["last_7d"]["workout_count"], 1)
        self.assertEqual(context["previous_21d"]["workout_count"], 3)
        self.assertEqual(context["last_42d"]["workout_count"], 6)
        self.assertTrue(
            math.isclose(
                context["relative_load"]["acute_to_baseline"],
                1.0,
            )
        )
        self.assertEqual(context["relative_load"]["baseline_confidence"], "medium")
        self.assertEqual(context["last_7d"]["load_label"], "Normal")

    def test_recovery_window_contains_reliability_metadata(self) -> None:
        for created_at in [
            "2026-05-01T10:00:00",
            "2026-05-08T10:00:00",
            "2026-05-15T10:00:00",
            "2026-05-22T10:00:00",
            "2026-05-29T10:00:00",
            "2026-06-05T10:00:00",
        ]:
            self.insert_workout(
                created_at=created_at,
                session_rpe=5,
                lower_back_pain=1,
            )

        context = build_recovery_context(as_of="2026-06-08T10:00:00")
        last_42d = context["last_42d"]

        self.assertEqual(last_42d["first_workout_at"], "2026-05-01T10:00:00")
        self.assertEqual(last_42d["last_workout_at"], "2026-06-05T10:00:00")
        self.assertEqual(last_42d["coverage_days"], 36)
        self.assertGreaterEqual(last_42d["active_week_count"], 6)
        self.assertGreater(last_42d["avg_load_per_workout"], 0)
        self.assertGreater(last_42d["avg_back_stress_per_workout"], 0)
        self.assertEqual(context["overall_interval"]["sample_count"], 5)
        self.assertEqual(context["overall_interval"]["confidence"], "high")


if __name__ == "__main__":
    unittest.main()
