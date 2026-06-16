import math
import tempfile
import unittest
from pathlib import Path

from app import config
from app.db import get_db, init_db
from app.services.recovery_service import build_recovery_context
from app.services.recommendation_service import (
    build_exercise_history_context,
    build_exercise_progression_trend,
    build_next_workout_recommendation,
    exercise_gap_label,
    exercise_gap_status,
    format_percent_change,
    format_training_target,
    get_recommendation_top_set,
)


class RecommendationServiceTests(unittest.TestCase):
    def test_format_helpers(self) -> None:
        self.assertEqual(format_training_target(0, 12), "12 reps")
        self.assertEqual(format_training_target(20, 8), "20 kg × 8")
        self.assertEqual(format_training_target(17.75, 10), "17.75 kg × 10")

        self.assertEqual(format_percent_change(None), "—")
        self.assertEqual(format_percent_change(2.345), "+2.3%")
        self.assertEqual(format_percent_change(-3.21), "-3.2%")

    def test_exercise_gap_status_and_label(self) -> None:
        self.assertEqual(exercise_gap_status(None, 7), "unknown")
        self.assertEqual(exercise_gap_status(0.5, None), "very_short")
        self.assertEqual(exercise_gap_status(10, None), "long")
        self.assertEqual(exercise_gap_status(3, 7), "shorter_than_usual")
        self.assertEqual(exercise_gap_status(7, 7), "normal")
        self.assertEqual(exercise_gap_status(14, 7), "longer_than_usual")
        self.assertEqual(exercise_gap_status(21, 7), "much_longer_than_usual")

        self.assertEqual(exercise_gap_label("normal"), "Normal")
        self.assertEqual(exercise_gap_label("surprise"), "Unknown")

    def test_get_recommendation_top_set_prefers_e1rm_then_volume_or_reps(self) -> None:
        top_set = get_recommendation_top_set(
            [
                {"weight": 100, "reps": 5},
                {"weight": 95, "reps": 8},
                {"weight": 0, "reps": 20},
            ]
        )

        self.assertEqual(top_set["weight"], 95.0)
        self.assertEqual(top_set["reps"], 8)
        self.assertTrue(math.isclose(top_set["e1rm"], 120.33333333333333))

        bodyweight_top_set = get_recommendation_top_set(
            [
                {"weight": 0, "reps": 10},
                {"weight": 0, "reps": 15},
            ]
        )
        self.assertEqual(bodyweight_top_set["reps"], 15)

    def test_build_exercise_progression_trend_classifies_recent_jump_and_regression(self) -> None:
        recent_jump = build_exercise_progression_trend(
            last_summary={
                "top_weight": 100,
                "top_reps": 8,
                "best_e1rm": 126.67,
                "total_volume": 1200,
            },
            previous_summary={
                "sets": [{"weight": 100, "reps": 5}],
                "best_e1rm": 116.67,
                "total_volume": 900,
            },
        )
        self.assertEqual(recent_jump["status"], "recent_jump")
        self.assertEqual(recent_jump["same_weight_rep_delta"], 3)

        regression = build_exercise_progression_trend(
            last_summary={
                "top_weight": 90,
                "top_reps": 5,
                "best_e1rm": 105.0,
                "total_volume": 600,
            },
            previous_summary={
                "sets": [{"weight": 90, "reps": 8}],
                "best_e1rm": 114.0,
                "total_volume": 900,
            },
        )
        self.assertEqual(regression["status"], "regression")


class RecommendationDatabaseTests(unittest.TestCase):
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

    def insert_deadlift_workout(
        self,
        created_at: str = "2026-06-01T10:00:00",
        *,
        sets: list[tuple[float, int]] | None = None,
        session_rpe: int | None = 6,
        lower_back_pain: int | None = 2,
    ) -> int:
        sets = sets or [(100.0, 5)]

        with get_db() as conn:
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
                (workout_id, self.exercise_id("Deadlift"), 1),
            )
            workout_exercise_id = int(workout_exercise_cursor.lastrowid)

            for set_number, (weight, reps) in enumerate(sets, start=1):
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
                        set_number,
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

    def insert_deadlift_workout_without_sets(self, created_at: str) -> int:
        with get_db() as conn:
            workout_id = self.insert_empty_workout(created_at)
            conn.execute(
                """
                INSERT INTO workout_exercises (workout_id, exercise_id, position)
                VALUES (?, ?, ?)
                """,
                (workout_id, self.exercise_id("Deadlift"), 1),
            )

        return workout_id

    def test_next_workout_recommendation_handles_empty_history(self) -> None:
        recommendation = build_next_workout_recommendation()

        self.assertEqual(recommendation["status"], "repeat")
        self.assertEqual(recommendation["title"], "Start baseline")
        self.assertIsNone(recommendation["last_workout_id"])
        self.assertEqual(recommendation["exercise_recommendations"], [])

    def test_next_workout_recommendation_uses_last_workout_and_recovery_context(self) -> None:
        workout_id = self.insert_deadlift_workout()
        recovery_context = build_recovery_context(as_of="2026-06-08T10:00:00")

        recommendation = build_next_workout_recommendation(
            recovery_context=recovery_context,
        )

        self.assertEqual(recommendation["last_workout_id"], workout_id)
        self.assertEqual(recommendation["status"], "progress")
        self.assertEqual(len(recommendation["exercise_recommendations"]), 1)

        exercise_recommendation = recommendation["exercise_recommendations"][0]
        self.assertEqual(exercise_recommendation["exercise_name"], "Deadlift")
        self.assertEqual(exercise_recommendation["action"], "add_reps")
        self.assertEqual(exercise_recommendation["target"], "100 kg × 6")

    def test_empty_workout_is_ignored_by_recovery_and_recommendation(self) -> None:
        real_workout_id = self.insert_deadlift_workout()
        empty_workout_id = self.insert_empty_workout("2026-06-08T08:00:00")

        recovery_context = build_recovery_context(as_of="2026-06-08T10:00:00")
        recommendation = build_next_workout_recommendation(
            recovery_context=recovery_context,
        )

        self.assertNotEqual(real_workout_id, empty_workout_id)
        self.assertEqual(recovery_context["previous_workout_id"], real_workout_id)
        self.assertEqual(recovery_context["last_7d"]["workout_count"], 1)
        self.assertEqual(recommendation["last_workout_id"], real_workout_id)

    def test_workout_with_exercise_but_without_sets_is_ignored(self) -> None:
        real_workout_id = self.insert_deadlift_workout()
        empty_workout_id = self.insert_deadlift_workout_without_sets(
            "2026-06-08T08:00:00",
        )

        recovery_context = build_recovery_context(as_of="2026-06-08T10:00:00")
        recommendation = build_next_workout_recommendation(
            recovery_context=recovery_context,
        )

        self.assertNotEqual(real_workout_id, empty_workout_id)
        self.assertEqual(recovery_context["previous_workout_id"], real_workout_id)
        self.assertEqual(recommendation["last_workout_id"], real_workout_id)

    def test_usual_exercise_interval_uses_median(self) -> None:
        for created_at in [
            "2026-01-01T10:00:00",
            "2026-01-04T10:00:00",
            "2026-01-07T10:00:00",
            "2026-01-11T10:00:00",
            "2026-01-31T10:00:00",
        ]:
            self.insert_deadlift_workout(created_at)

        context = build_exercise_history_context(
            exercise_id=self.exercise_id("Deadlift"),
            as_of="2026-02-05T10:00:00",
        )

        self.assertEqual(context["usual_interval_days"], 3.5)

    def test_acute_spike_uses_personal_baseline_in_readiness(self) -> None:
        for created_at in [
            "2026-05-20T10:00:00",
            "2026-05-27T10:00:00",
            "2026-06-02T10:00:00",
            "2026-06-09T10:00:00",
            "2026-06-16T10:00:00",
        ]:
            self.insert_deadlift_workout(
                created_at,
                session_rpe=5,
                lower_back_pain=1,
            )

        self.insert_deadlift_workout(
            "2026-06-23T10:00:00",
            sets=[(100.0, 5), (100.0, 5)],
            session_rpe=5,
            lower_back_pain=1,
        )

        recovery_context = build_recovery_context(as_of="2026-06-29T10:00:00")
        recommendation = build_next_workout_recommendation(
            recovery_context=recovery_context,
        )

        self.assertEqual(
            recovery_context["relative_load"]["baseline_confidence"],
            "medium",
        )
        self.assertGreater(
            recovery_context["relative_load"]["acute_to_baseline"],
            1.5,
        )
        self.assertTrue(
            any("recent baseline" in reason for reason in recommendation["reasons"])
        )


if __name__ == "__main__":
    unittest.main()
