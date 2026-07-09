import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import config
from app.db import init_db
from app.repositories import garmin as garmin_repository
from app.services.garmin_readiness_service import build_garmin_readiness_adjustment
from app.services.garmin_service import GarminService


class GarminInsightsUnificationTests(unittest.TestCase):
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

    def insert_baseline_metrics(self) -> None:
        current_day = date(2026, 6, 26)
        start_day = current_day - timedelta(days=28)
        for offset in range(28):
            self.insert_metric((start_day + timedelta(days=offset)).isoformat())

    def readiness_rule_by_metric(self, adjustment: dict, metric: str) -> dict:
        for rule in adjustment["rules"]:
            if rule["metric"] == metric:
                return rule
        raise AssertionError(f"Rule not found: {metric}")

    def stats_signal_by_metric(self, stats: dict, metric: str) -> dict:
        for signal in stats["insights"]["signals"]:
            if signal["metric"] == metric:
                return signal
        raise AssertionError(f"Signal not found: {metric}")

    def test_stats_insights_match_readiness_adjustment_fixture(self) -> None:
        self.insert_baseline_metrics()
        self.insert_metric("2026-06-25", stress_avg=85, body_battery_end=30)
        self.insert_metric(
            "2026-06-26",
            resting_heart_rate=72,
            hrv_ms=35.0,
            stress_avg=90,
            body_battery_start=35,
            body_battery_end=20,
        )

        adjustment = build_garmin_readiness_adjustment(
            "2026-06-26T10:00:00",
            today=date(2026, 6, 26),
        )
        stats = GarminService().stats("35", today=date(2026, 6, 26))

        self.assertEqual(
            stats["insights"]["readiness_impact"]["score_delta"],
            adjustment["score_delta"],
        )
        self.assertEqual(
            stats["insights"]["readiness_impact"]["raw_score_delta"],
            adjustment["raw_score_delta"],
        )
        self.assertEqual(stats["insights"]["current_date"], adjustment["current_date"])
        self.assertEqual(stats["insights"]["previous_date"], adjustment["previous_date"])
        self.assertEqual(
            stats["insights"]["baseline_start_date"],
            adjustment["baseline_start_date"],
        )
        self.assertEqual(
            stats["insights"]["baseline_end_date"],
            adjustment["baseline_end_date"],
        )

        metric_pairs = (
            ("resting_heart_rate", "resting_heart_rate"),
            ("hrv_ms", "hrv_ms"),
            ("body_battery_start", "body_battery_start"),
            ("stress_avg", "stress_avg"),
            ("current_stress_avg", "current_stress_avg"),
        )
        for rule_metric, signal_metric in metric_pairs:
            rule = self.readiness_rule_by_metric(adjustment, rule_metric)
            signal = self.stats_signal_by_metric(stats, signal_metric)
            self.assertEqual(signal["source_date"], rule["source_date"])
            self.assertEqual(signal["current"], rule["current"])
            self.assertEqual(signal["baseline_median"], rule["baseline_median"])
            self.assertEqual(
                signal["baseline_sample_count"],
                rule["baseline_sample_count"],
            )
            self.assertEqual(signal["score_delta"], rule["score_delta"])


if __name__ == "__main__":
    unittest.main()
