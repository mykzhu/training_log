import math
import unittest

from app.services.analysis_service import (
    DEFAULT_LOAD_PROFILE,
    calculate_workout_load_metrics,
    estimated_1rm,
    get_exercise_load_profile,
    intensity_factor,
    rep_factor,
    rpe_factor,
    workout_load_label,
)


class AnalysisServiceTests(unittest.TestCase):
    def test_estimated_1rm_valid_and_invalid_rep_ranges(self) -> None:
        self.assertIsNone(estimated_1rm(0, 5))
        self.assertIsNone(estimated_1rm(100, 2))
        self.assertIsNone(estimated_1rm(100, 13))
        self.assertTrue(math.isclose(estimated_1rm(100, 5) or 0, 116.6666667))
        self.assertTrue(math.isclose(estimated_1rm(50, 12) or 0, 70.0))

    def test_rep_factor_boundaries(self) -> None:
        cases = [
            (-1, 0.0),
            (0, 0.0),
            (1, 1.15),
            (3, 1.15),
            (4, 1.10),
            (8, 1.10),
            (9, 1.00),
            (15, 1.00),
            (16, 0.85),
        ]

        for reps, expected in cases:
            with self.subTest(reps=reps):
                self.assertEqual(rep_factor(reps), expected)

    def test_intensity_factor_boundaries(self) -> None:
        cases = [
            (None, 1.0),
            (0.54, 0.5),
            (0.55, 0.8),
            (0.69, 0.8),
            (0.70, 1.0),
            (0.79, 1.0),
            (0.80, 1.25),
            (0.89, 1.25),
            (0.90, 1.5),
        ]

        for relative_intensity, expected in cases:
            with self.subTest(relative_intensity=relative_intensity):
                self.assertEqual(intensity_factor(relative_intensity), expected)

    def test_rpe_factor(self) -> None:
        self.assertEqual(rpe_factor(None), 1.0)
        self.assertTrue(math.isclose(rpe_factor(5), 1.0))
        self.assertTrue(math.isclose(rpe_factor(10), 1.3))

    def test_workout_load_label_boundaries(self) -> None:
        cases = [
            (3.999, "Light"),
            (4.0, "Medium"),
            (7.999, "Medium"),
            (8.0, "Hard"),
            (13.999, "Hard"),
            (14.0, "Very hard"),
        ]

        for score, expected in cases:
            with self.subTest(score=score):
                self.assertEqual(workout_load_label(score), expected)

    def test_unknown_exercise_profile_uses_fallback(self) -> None:
        self.assertEqual(get_exercise_load_profile("Mystery Lift"), DEFAULT_LOAD_PROFILE)

    def test_profile_key_overrides_display_name_for_load_profile(self) -> None:
        profile = get_exercise_load_profile(
            "Romanian Pull",
            profile_key="deadlift",
        )

        self.assertEqual(profile["category"], "heavy compound")

        fallback = get_exercise_load_profile(
            "Deadlift",
            profile_key="unknown_profile",
        )

        self.assertEqual(fallback, DEFAULT_LOAD_PROFILE)

    def test_calculate_workout_load_metrics_scores_known_and_unknown_profiles(self) -> None:
        workout_exercises = [
            {
                "exercise_id": 1,
                "exercise_name": "Deadlift",
                "sets": [
                    {"weight": 100, "reps": 5},
                    {"weight": 80, "reps": 10},
                ],
            },
            {
                "exercise_id": 2,
                "exercise_name": "Mystery Lift",
                "sets": [
                    {"weight": 20, "reps": 12},
                ],
            },
        ]

        metrics = calculate_workout_load_metrics(
            workout_exercises=workout_exercises,
            session_rpe=5,
            best_e1rm_by_exercise={1: 120.0, 2: 25.0},
        )

        self.assertTrue(math.isclose(metrics["raw_load_score"], 6.72))
        self.assertTrue(math.isclose(metrics["load_score"], 6.72))
        self.assertEqual(metrics["load_label"], "Medium")
        self.assertTrue(math.isclose(metrics["compound_score"], 4.28))
        self.assertTrue(math.isclose(metrics["back_stress_score"], 5.67))
        self.assertEqual(metrics["scored_sets"], 3)
        self.assertTrue(math.isclose(metrics["intensity_score"], 99.37037037))

        deadlift_breakdown = metrics["exercise_breakdown"][0]
        self.assertEqual(deadlift_breakdown["category"], "heavy compound")
        self.assertTrue(math.isclose(deadlift_breakdown["load_score"], 5.22))

        fallback_breakdown = metrics["exercise_breakdown"][1]
        self.assertEqual(fallback_breakdown["category"], "accessory")
        self.assertTrue(math.isclose(fallback_breakdown["load_score"], 1.5))

    def test_exercise_intensity_averages_only_known_intensity_sets(self) -> None:
        metrics = calculate_workout_load_metrics(
            workout_exercises=[
                {
                    "exercise_id": 1,
                    "exercise_name": "Deadlift",
                    "sets": [
                        {"weight": 80, "reps": 5},
                        {"weight": 0, "reps": 20},
                    ],
                },
            ],
            best_e1rm_by_exercise={1: 100.0},
        )

        breakdown = metrics["exercise_breakdown"][0]

        self.assertTrue(math.isclose(metrics["intensity_score"], 93.33333333))
        self.assertTrue(math.isclose(breakdown["intensity_score"], 93.33333333))

    def test_bodyweight_reps_contribute_to_load_and_back_stress(self) -> None:
        metrics = calculate_workout_load_metrics(
            workout_exercises=[
                {
                    "exercise_id": 11,
                    "exercise_name": "Crunches",
                    "profile_key": "crunches",
                    "sets": [
                        {"weight": 0, "reps": 50},
                        {"weight": 0, "reps": 50},
                    ],
                },
            ],
            session_rpe=5,
            profiles_by_key={
                "crunches": {
                    "category": "core",
                    "exercise_factor": 0.7,
                    "compound_factor": 0.2,
                    "back_factor": 0.3,
                },
                "accessory": DEFAULT_LOAD_PROFILE,
            },
        )

        self.assertEqual(metrics["scored_sets"], 2)
        self.assertGreater(metrics["load_score"], 0)
        self.assertGreater(metrics["back_stress_score"], 0)
        self.assertIsNone(metrics["intensity_score"])

    def test_zero_weight_weighted_set_scores_without_intensity_or_crash(self) -> None:
        metrics = calculate_workout_load_metrics(
            workout_exercises=[
                {
                    "exercise_id": 1,
                    "exercise_name": "Deadlift",
                    "profile_key": "deadlift",
                    "sets": [{"weight": 0, "reps": 5}],
                },
            ],
            best_e1rm_by_exercise={1: 120.0},
            profiles_by_key={
                "deadlift": {
                    "category": "heavy compound",
                    "exercise_factor": 1.8,
                    "compound_factor": 1.0,
                    "back_factor": 1.5,
                },
                "accessory": DEFAULT_LOAD_PROFILE,
            },
        )

        self.assertEqual(metrics["scored_sets"], 1)
        self.assertGreater(metrics["load_score"], 0)
        self.assertGreater(metrics["back_stress_score"], 0)
        self.assertIsNone(metrics["intensity_score"])


if __name__ == "__main__":
    unittest.main()
