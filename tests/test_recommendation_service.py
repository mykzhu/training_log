import math
import unittest

from app.services.recommendation_service import (
    build_exercise_progression_trend,
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


if __name__ == "__main__":
    unittest.main()
