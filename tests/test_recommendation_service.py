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
    calculate_readiness_status,
    exercise_gap_label,
    exercise_gap_status,
    format_percent_change,
    format_training_target,
    get_recommendation_top_set,
    suggested_sets_for_action,
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
        self.assertEqual(exercise_recommendation["target"], "Add 1 rep to the lowest-rep set")

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

    def test_recommendation_ignores_future_workouts_from_recovery_as_of(self) -> None:
        past_workout_id = self.insert_deadlift_workout(
            "2026-06-01T10:00:00",
            sets=[(100.0, 5)],
        )
        self.insert_deadlift_workout(
            "2026-06-20T10:00:00",
            sets=[(140.0, 5)],
        )

        recovery_context = build_recovery_context(as_of="2026-06-08T10:00:00")
        recommendation = build_next_workout_recommendation(
            recovery_context=recovery_context,
        )

        self.assertEqual(recommendation["last_workout_id"], past_workout_id)
        self.assertEqual(
            recommendation["exercise_recommendations"][0]["target"],
            "100 kg × 6",
        )

    def test_missing_latest_feedback_returns_needs_feedback(self) -> None:
        workout_id = self.insert_deadlift_workout(
            "2026-06-01T10:00:00",
            session_rpe=None,
            lower_back_pain=2,
        )
        recovery_context = build_recovery_context(as_of="2026-06-08T10:00:00")

        recommendation = build_next_workout_recommendation(
            recovery_context=recovery_context,
        )

        self.assertEqual(recommendation["status"], "needs_feedback")
        self.assertEqual(recommendation["last_workout_id"], workout_id)
        self.assertEqual(recommendation["exercise_recommendations"], [])

    def test_recovery_recommendation_has_no_exercise_targets(self) -> None:
        self.insert_deadlift_workout(
            "2026-06-01T10:00:00",
            session_rpe=7,
            lower_back_pain=3,
        )
        recovery_context = build_recovery_context(as_of="2026-06-01T12:00:00")

        recommendation = build_next_workout_recommendation(
            recovery_context=recovery_context,
        )

        self.assertEqual(recommendation["status"], "recovery")
        self.assertEqual(recommendation["exercise_recommendations"], [])

    def test_structured_suggested_sets_are_returned_for_progress(self) -> None:
        self.insert_deadlift_workout(
            "2026-06-01T10:00:00",
            sets=[(100.0, 5), (100.0, 4), (100.0, 5)],
            session_rpe=4,
            lower_back_pain=1,
        )
        recovery_context = build_recovery_context(as_of="2026-06-08T10:00:00")

        recommendation = build_next_workout_recommendation(
            recovery_context=recovery_context,
        )

        exercise = recommendation["exercise_recommendations"][0]
        self.assertEqual(exercise["target_strategy"], "add_rep_to_lowest_rep_set")
        self.assertEqual(
            [item["reps"] for item in exercise["suggested_sets"]],
            [5, 5, 5],
        )
        self.assertEqual(exercise["interval_confidence"], "low")

    def test_suggested_sets_cover_repeat_deload_careful_progress_and_bodyweight(self) -> None:
        sets = [
            {"weight": 100.0, "reps": 5},
            {"weight": 100.0, "reps": 4},
            {"weight": 100.0, "reps": 5},
        ]

        strategy, suggested_sets = suggested_sets_for_action(
            sets,
            "repeat",
            "repeat",
        )
        self.assertEqual(strategy, "repeat")
        self.assertEqual([item["reps"] for item in suggested_sets], [5, 4, 5])
        self.assertEqual([item["weight"] for item in suggested_sets], [100.0, 100.0, 100.0])

        strategy, suggested_sets = suggested_sets_for_action(
            sets,
            "deload",
            "deload",
        )
        self.assertEqual(strategy, "deload")
        self.assertEqual([item["weight"] for item in suggested_sets], [90.0, 90.0, 90.0])
        self.assertEqual([item["reps"] for item in suggested_sets], [5, 4, 5])

        strategy, suggested_sets = suggested_sets_for_action(
            sets,
            "add_reps",
            "progress_carefully",
        )
        self.assertEqual(strategy, "add_rep_to_last_set")
        self.assertEqual([item["reps"] for item in suggested_sets], [5, 4, 6])

        strategy, suggested_sets = suggested_sets_for_action(
            [
                {"weight": 0.0, "reps": 12},
                {"weight": 0.0, "reps": 10},
            ],
            "add_reps",
            "progress",
        )
        self.assertEqual(strategy, "add_rep_to_lowest_rep_set")
        self.assertEqual([item["reps"] for item in suggested_sets], [12, 11])

    def test_short_gap_penalty_uses_previous_session_relative_to_baseline(self) -> None:
        base_context = {
            "hours_since_previous_workout": 12,
            "last_7d": {
                "load_score": 10,
                "back_stress_score": 4,
            },
            "previous_21d": {
                "avg_load_per_workout": 5,
                "avg_back_stress_per_workout": 2,
            },
            "last_42d": {
                "avg_load_per_workout": 5,
                "avg_back_stress_per_workout": 2,
            },
            "relative_load": {
                "baseline_confidence": "medium",
                "acute_to_baseline": 1.0,
                "acute_back_to_baseline": 1.0,
            },
            "overall_interval": {
                "confidence": "low",
                "current_ratio": None,
            },
        }
        last_workout = {
            "session_rpe": 4,
            "lower_back_pain": 1,
        }

        light = calculate_readiness_status(
            recovery_context=base_context,
            last_workout=last_workout,
            last_load_metrics={
                "load_score": 4,
                "back_stress_score": 1,
            },
        )
        heavy = calculate_readiness_status(
            recovery_context=base_context,
            last_workout=last_workout,
            last_load_metrics={
                "load_score": 10,
                "back_stress_score": 4,
            },
        )

        self.assertGreater(light["score"], heavy["score"])
        self.assertFalse(
            any("relative to your baseline" in reason for reason in light["reasons"])
        )
        self.assertTrue(
            any("relative to your baseline" in reason for reason in heavy["reasons"])
        )

    def test_long_layoff_caps_low_confidence_and_personal_interval(self) -> None:
        low_confidence_context = {
            "hours_since_previous_workout": 22 * 24,
            "last_7d": {
                "load_score": 0,
                "back_stress_score": 0,
            },
            "previous_21d": {
                "avg_load_per_workout": 0,
                "avg_back_stress_per_workout": 0,
            },
            "last_42d": {
                "avg_load_per_workout": 0,
                "avg_back_stress_per_workout": 0,
            },
            "relative_load": {
                "baseline_confidence": "low",
                "acute_to_baseline": None,
                "acute_back_to_baseline": None,
            },
            "overall_interval": {
                "confidence": "low",
                "current_ratio": None,
            },
        }
        last_workout = {
            "session_rpe": 4,
            "lower_back_pain": 1,
        }

        low_confidence = calculate_readiness_status(
            recovery_context=low_confidence_context,
            last_workout=last_workout,
            last_load_metrics={
                "load_score": 2,
                "back_stress_score": 1,
            },
        )
        self.assertLessEqual(low_confidence["score"], 59)
        self.assertEqual(low_confidence["status"], "repeat")

        personal_interval_context = dict(low_confidence_context)
        personal_interval_context["hours_since_previous_workout"] = 14 * 24
        personal_interval_context["relative_load"] = {
            "baseline_confidence": "medium",
            "acute_to_baseline": 1.0,
            "acute_back_to_baseline": 1.0,
        }
        personal_interval_context["overall_interval"] = {
            "confidence": "medium",
            "current_ratio": 3.0,
        }

        personal_interval = calculate_readiness_status(
            recovery_context=personal_interval_context,
            last_workout=last_workout,
            last_load_metrics={
                "load_score": 2,
                "back_stress_score": 1,
            },
        )
        self.assertLessEqual(personal_interval["score"], 59)
        self.assertEqual(personal_interval["status"], "repeat")


if __name__ == "__main__":
    unittest.main()
