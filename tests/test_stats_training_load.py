import unittest
from datetime import date

from app.services.training_load_service import (
    build_training_load_summary,
    percentile_95,
)


class TrainingLoadTests(unittest.TestCase):
    def test_training_load_includes_rest_days_and_latest_metrics(self) -> None:
        summary = build_training_load_summary(
            [
                {"date": "2026-01-01", "load_score": 100.0},
                {"date": "2026-01-03", "load_score": 50.0},
            ],
            today=date(2026, 1, 4),
        )

        self.assertEqual(summary["latest_date"], "2026-01-04")
        self.assertEqual(
            summary["daily_load"],
            [
                {"date": "2026-01-01", "load": 100.0},
                {"date": "2026-01-02", "load": 0.0},
                {"date": "2026-01-03", "load": 50.0},
                {"date": "2026-01-04", "load": 0.0},
            ],
        )
        self.assertEqual(len(summary["series"]), 4)
        self.assertAlmostEqual(summary["series"][-1]["atl"], 69.0962, places=4)
        self.assertGreater(summary["series"][-1]["ctl"], summary["series"][-1]["atl"])
        self.assertAlmostEqual(summary["weekly_load"], 150.0, places=4)
        self.assertIsNotNone(summary["monotony"])
        self.assertIsNotNone(summary["strain"])

        metrics = {metric["key"]: metric for metric in summary["metrics"]}
        self.assertIn("atl", metrics)
        self.assertIn("ctl", metrics)
        self.assertIn("tsb", metrics)
        self.assertIn("ac_ratio", metrics)
        self.assertIn("training_strain", metrics)
        self.assertEqual(metrics["atl"]["formatted"], "69.1")

    def test_empty_training_load_returns_null_values(self) -> None:
        summary = build_training_load_summary([], today=date(2026, 1, 4))

        self.assertIsNone(summary["latest_date"])
        self.assertEqual(summary["daily_load"], [])
        self.assertEqual(summary["series"], [])
        self.assertTrue(
            all(metric["status"] == "neutral" for metric in summary["metrics"])
        )

    def test_percentile_uses_max_until_enough_samples(self) -> None:
        self.assertEqual(percentile_95([1.0, 3.0, 2.0]), 3.0)
        self.assertAlmostEqual(
            percentile_95([float(index) for index in range(1, 22)]),
            20.0,
            places=4,
        )


if __name__ == "__main__":
    unittest.main()
