import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import config
from app.db import init_db
from app.repositories import garmin as garmin_repository
from app.services.garmin_readiness_service import build_garmin_readiness_adjustment


class GarminReadinessServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def insert_metric(
        self,
        metric_date: str,
        *,
        resting_heart_rate: int | None = 60,
        hrv_ms: float | None = 50.0,
        stress_avg: int | None = 50,
        body_battery_start: int | None = 70,
        body_battery_end: int | None = 35,
        steps: int | None = 8000,
    ) -> None:
        garmin_repository.upsert_daily_metric(
            {
                "date": metric_date,
                "resting_heart_rate": resting_heart_rate,
                "hrv_ms": hrv_ms,
                "stress_avg": stress_avg,
                "body_battery_start": body_battery_start,
                "body_battery_end": body_battery_end,
                "steps": steps,
                "synced_at": f"{metric_date}T08:00:00",
                "raw_diagnostics": {"test": {"ok": True}},
            }
        )

    def insert_baseline_metrics(self, *, days: int = 28) -> None:
        current_day = date(2026, 6, 26)
        start_day = current_day - timedelta(days=days)
        for offset in range(days):
            metric_date = (start_day + timedelta(days=offset)).isoformat()
            self.insert_metric(metric_date)

    def rule_by_metric(self, adjustment: dict, metric: str) -> dict:
        for rule in adjustment["rules"]:
            if rule["metric"] == metric:
                return rule
        raise AssertionError(f"Rule not found: {metric}")

    def test_no_garmin_data_returns_zero_not_available_adjustment(self) -> None:
        adjustment = build_garmin_readiness_adjustment("2026-06-26T10:00:00")

        self.assertFalse(adjustment["applied"])
        self.assertEqual(adjustment["status"], "not_available")
        self.assertEqual(adjustment["score_delta"], 0)
        self.assertEqual(adjustment["baseline_days"], 28)
        self.assertEqual(adjustment["minimum_baseline_samples"], 7)

    def test_bad_current_metrics_and_previous_day_stress_clamp_negative_delta(self) -> None:
        self.insert_baseline_metrics()
        self.insert_metric(
            "2026-06-25",
            stress_avg=85,
        )
        self.insert_metric(
            "2026-06-26",
            resting_heart_rate=72,
            hrv_ms=35.0,
            stress_avg=90,
            body_battery_start=35,
        )

        adjustment = build_garmin_readiness_adjustment("2026-06-26T10:00:00")

        self.assertTrue(adjustment["applied"])
        self.assertEqual(adjustment["status"], "negative")
        self.assertLess(adjustment["raw_score_delta"], -20)
        self.assertEqual(adjustment["score_delta"], -20)
        self.assertEqual(
            self.rule_by_metric(adjustment, "current_stress_avg")["status"],
            "display_only",
        )
        self.assertEqual(
            self.rule_by_metric(adjustment, "stress_avg")["source_date"],
            "2026-06-25",
        )
        self.assertLess(
            self.rule_by_metric(adjustment, "stress_avg")["score_delta"],
            0,
        )

    def test_good_current_metrics_and_previous_day_stress_clamp_positive_delta(self) -> None:
        self.insert_baseline_metrics()
        self.insert_metric("2026-06-25", stress_avg=25)
        self.insert_metric(
            "2026-06-26",
            resting_heart_rate=54,
            hrv_ms=60.0,
            body_battery_start=92,
        )

        adjustment = build_garmin_readiness_adjustment("2026-06-26T10:00:00")

        self.assertEqual(adjustment["status"], "positive")
        self.assertGreater(adjustment["raw_score_delta"], 10)
        self.assertEqual(adjustment["score_delta"], 10)

    def test_minimum_seven_baseline_samples_required_per_metric(self) -> None:
        self.insert_baseline_metrics(days=6)
        self.insert_metric(
            "2026-06-26",
            resting_heart_rate=72,
            hrv_ms=35.0,
            body_battery_start=35,
        )

        adjustment = build_garmin_readiness_adjustment("2026-06-26T10:00:00")

        self.assertEqual(adjustment["score_delta"], 0)
        self.assertEqual(adjustment["status"], "insufficient_baseline")
        self.assertEqual(
            self.rule_by_metric(adjustment, "resting_heart_rate")["status"],
            "insufficient_baseline",
        )

    def test_only_current_date_metrics_score_except_previous_day_stress(self) -> None:
        self.insert_baseline_metrics()
        self.insert_metric(
            "2026-06-25",
            resting_heart_rate=75,
            hrv_ms=30.0,
            stress_avg=85,
            body_battery_start=30,
        )

        adjustment = build_garmin_readiness_adjustment("2026-06-26T10:00:00")

        self.assertEqual(
            self.rule_by_metric(adjustment, "resting_heart_rate")["status"],
            "missing_current",
        )
        self.assertEqual(
            self.rule_by_metric(adjustment, "hrv_ms")["status"],
            "missing_current",
        )
        self.assertEqual(
            self.rule_by_metric(adjustment, "body_battery_start")["status"],
            "missing_current",
        )
        self.assertEqual(
            self.rule_by_metric(adjustment, "stress_avg")["status"],
            "scored",
        )
        self.assertEqual(adjustment["score_delta"], -8)


if __name__ == "__main__":
    unittest.main()