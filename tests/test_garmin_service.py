import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app import config
from app.db import get_db, init_db
from app.repositories import garmin as garmin_repository
from app.services.garmin_client import GarminClientAdapter
from app.services import garmin_service as garmin_service_module
from app.services.garmin_service import GarminService


class FakeGarminDataClient:
    def __init__(self, payloads: dict[str, dict[str, Any]], failures: set[tuple[str, str]] | None = None) -> None:
        self.payloads = payloads
        self.failures = failures or set()
        self.connected = True

    def has_tokens(self) -> bool:
        return self.connected

    def connect_from_tokens(self) -> object:
        return object()

    def disconnect(self) -> None:
        self.connected = False

    def login(self, username: str, password: str):
        return False, object(), None

    def resume_mfa(self, client: Any, state: Any, code: str) -> None:
        return None

    def _payload(self, source: str, metric_date: str) -> Any:
        if (metric_date, source) in self.failures:
            raise RuntimeError(f"{source} unavailable")
        return self.payloads.get(metric_date, {}).get(source, {})

    def get_daily_summary(self, client: Any, metric_date: str) -> Any:
        return self._payload("summary", metric_date)

    def get_hrv_data(self, client: Any, metric_date: str) -> Any:
        return self._payload("hrv", metric_date)

    def get_stress_data(self, client: Any, metric_date: str) -> Any:
        return self._payload("stress", metric_date)

    def get_body_battery_data(self, client: Any, metric_date: str) -> Any:
        return self._payload("body_battery", metric_date)


class FakeMfaClient:
    def __init__(self) -> None:
        self.resumed_code: str | None = None


class FakeMfaGarminClient:
    def __init__(self) -> None:
        self.connected = False
        self.session = FakeMfaClient()

    def has_tokens(self) -> bool:
        return self.connected

    def login(self, username: str, password: str):
        return True, self.session, {"challenge": "sms"}

    def resume_mfa(self, client: FakeMfaClient, state: Any, code: str) -> None:
        client.resumed_code = code
        self.connected = True

    def connect_from_tokens(self) -> object:
        return object()

    def disconnect(self) -> None:
        self.connected = False

    def get_daily_summary(self, client: Any, metric_date: str) -> Any:
        return {}

    def get_hrv_data(self, client: Any, metric_date: str) -> Any:
        return {}

    def get_stress_data(self, client: Any, metric_date: str) -> Any:
        return {}

    def get_body_battery_data(self, client: Any, metric_date: str) -> Any:
        return {}


class FakeGarth:
    def __init__(self) -> None:
        self.dumped_to: str | None = None

    def dump(self, token_dir: str) -> None:
        self.dumped_to = token_dir
        Path(token_dir).mkdir(parents=True, exist_ok=True)
        (Path(token_dir) / "oauth.json").write_text("token", encoding="utf-8")


class FakeGarminConnect:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.garth = FakeGarth()

    def login(self, *args: Any) -> None:
        return None


class ExplodingGarminClient:
    def has_tokens(self) -> bool:
        raise AssertionError("stats must not check Garmin tokens")

    def login(self, username: str, password: str):
        raise AssertionError("stats must not call Garmin login")

    def resume_mfa(self, client: Any, state: Any, code: str) -> None:
        raise AssertionError("stats must not call Garmin MFA")

    def connect_from_tokens(self) -> object:
        raise AssertionError("stats must not connect to Garmin")

    def disconnect(self) -> None:
        raise AssertionError("stats must not disconnect Garmin")

    def get_daily_summary(self, client: Any, metric_date: str) -> Any:
        raise AssertionError("stats must not fetch Garmin summaries")

    def get_hrv_data(self, client: Any, metric_date: str) -> Any:
        raise AssertionError("stats must not fetch Garmin HRV")

    def get_stress_data(self, client: Any, metric_date: str) -> Any:
        raise AssertionError("stats must not fetch Garmin stress")

    def get_body_battery_data(self, client: Any, metric_date: str) -> Any:
        raise AssertionError("stats must not fetch Garmin Body Battery")


class GarminServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_token_dir = config.GARMIN_TOKEN_DIR
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        config.GARMIN_TOKEN_DIR = Path(self.temp_dir.name) / "garmin_tokens"
        init_db()
        garmin_service_module.PENDING_MFA.clear()

    def tearDown(self) -> None:
        garmin_service_module.PENDING_MFA.clear()
        config.DB_PATH = self.original_db_path
        config.GARMIN_TOKEN_DIR = self.original_token_dir
        self.temp_dir.cleanup()

    def seed_metric(self, metric_date: str, **overrides: Any) -> None:
        metric = {
            "date": metric_date,
            "resting_heart_rate": 50,
            "hrv_ms": 40.0,
            "stress_avg": 25,
            "body_battery_start": 70,
            "body_battery_end": 35,
            "steps": 7000,
            "synced_at": f"{metric_date}T08:00:00",
            "raw_diagnostics": {"seed": {"ok": True}},
        }
        metric.update(overrides)
        garmin_repository.upsert_daily_metric(metric)

    def test_sync_extracts_fenix_style_payload_shapes(self) -> None:
        payloads = {
            "2026-06-26": {
                "summary": {"restingHeartRate": 52, "totalSteps": 12345},
                "hrv": {"hrvSummary": {"lastNightAvg": 48}},
                "stress": {"stressValuesArray": [["08:00", 20], ["09:00", 40]]},
                "body_battery": {"bodyBatteryValuesArray": [["00:00", 82], ["23:59", 37]]},
            }
        }
        service = GarminService(FakeGarminDataClient(payloads))

        response = service.sync(1, today=date(2026, 6, 26))
        metric = garmin_repository.get_daily_metric("2026-06-26")

        self.assertEqual(response["saved_dates"], ["2026-06-26"])
        self.assertEqual(metric["resting_heart_rate"], 52)
        self.assertEqual(metric["hrv_ms"], 48)
        self.assertEqual(metric["stress_avg"], 30)
        self.assertEqual(metric["body_battery_start"], 82)
        self.assertEqual(metric["body_battery_end"], 37)
        self.assertEqual(metric["steps"], 12345)
        self.assertIn("summary", metric["raw_diagnostics"])

    def test_sync_extracts_body_battery_from_daily_summary_fallback(self) -> None:
        payloads = {
            "2026-06-26": {
                "summary": {
                    "bodyBatteryAtWakeTime": 84,
                    "bodyBatteryMostRecentValue": 26,
                },
                "body_battery": {},
            }
        }
        service = GarminService(FakeGarminDataClient(payloads))

        service.sync(1, today=date(2026, 6, 26))
        metric = garmin_repository.get_daily_metric("2026-06-26")

        self.assertEqual(metric["body_battery_start"], 84)
        self.assertEqual(metric["body_battery_end"], 26)

    def test_sync_extracts_nested_body_battery_payload_shapes(self) -> None:
        payloads = {
            "2026-06-26": {
                "body_battery": {
                    "bodyBattery": {
                        "values": [
                            {"bodyBatteryLevel": 91},
                            ["12:00", 1687780800000, 64, "MEASURED"],
                            {"valueDescriptorDTO": {"value": 42}},
                        ]
                    }
                },
            }
        }
        service = GarminService(FakeGarminDataClient(payloads))

        service.sync(1, today=date(2026, 6, 26))
        metric = garmin_repository.get_daily_metric("2026-06-26")

        self.assertEqual(metric["body_battery_start"], 91)
        self.assertEqual(metric["body_battery_end"], 42)

    def test_partial_sync_preserves_existing_valid_values(self) -> None:
        garmin_repository.upsert_daily_metric(
            {
                "date": "2026-06-26",
                "resting_heart_rate": 50,
                "hrv_ms": 42.0,
                "stress_avg": None,
                "body_battery_start": None,
                "body_battery_end": None,
                "steps": None,
                "synced_at": "2026-06-26T08:00:00",
                "raw_diagnostics": {"seed": {"ok": True}},
            }
        )
        payloads = {
            "2026-06-26": {
                "summary": {"totalSteps": 6000},
                "stress": {"avgStressLevel": 35},
            }
        }
        service = GarminService(
            FakeGarminDataClient(
                payloads,
                failures={
                    ("2026-06-26", "hrv"),
                    ("2026-06-26", "body_battery"),
                },
            )
        )

        service.sync(1, today=date(2026, 6, 26))
        metric = garmin_repository.get_daily_metric("2026-06-26")

        self.assertEqual(metric["resting_heart_rate"], 50)
        self.assertEqual(metric["hrv_ms"], 42.0)
        self.assertEqual(metric["stress_avg"], 35)
        self.assertEqual(metric["steps"], 6000)
        self.assertIn("error", metric["raw_diagnostics"]["hrv"])

    def test_sync_skips_empty_rows_when_all_sources_fail_or_empty(self) -> None:
        service = GarminService(FakeGarminDataClient({}))

        response = service.sync(1, today=date(2026, 6, 26))

        self.assertEqual(response["saved_dates"], [])
        self.assertEqual(response["skipped_dates"], ["2026-06-26"])
        self.assertIsNone(garmin_repository.get_daily_metric("2026-06-26"))

    def test_mfa_session_uses_ephemeral_token_without_persisting_credentials(self) -> None:
        fake_client = FakeMfaGarminClient()
        service = GarminService(fake_client)

        login_response = service.login("user@example.com", "secret")
        self.assertTrue(login_response["mfa_required"])
        self.assertNotIn("user@example.com", login_response["mfa_token"])
        self.assertNotIn("secret", login_response["mfa_token"])

        mfa_response = service.submit_mfa(login_response["mfa_token"], "123456")

        self.assertTrue(mfa_response["connected"])
        self.assertEqual(fake_client.session.resumed_code, "123456")

    def test_client_adapter_persists_tokens_and_disconnects_without_credentials(self) -> None:
        token_dir = config.GARMIN_TOKEN_DIR
        adapter = GarminClientAdapter(
            token_dir=token_dir,
            client_factory=FakeGarminConnect,
        )

        mfa_required, _client, _state = adapter.login("user@example.com", "secret")

        self.assertFalse(mfa_required)
        token_file = token_dir / "oauth.json"
        self.assertTrue(token_file.is_file())
        self.assertNotIn("user@example.com", token_file.read_text(encoding="utf-8"))
        self.assertNotIn("secret", token_file.read_text(encoding="utf-8"))

        adapter.disconnect()

        self.assertFalse(token_file.exists())

    def test_stats_with_no_rows_returns_stable_empty_response(self) -> None:
        service = GarminService(ExplodingGarminClient())

        response = service.stats("90", today=date(2026, 6, 26))

        self.assertEqual(response["range"], "90")
        self.assertEqual(response["date_from"], "2026-03-29")
        self.assertEqual(response["date_to"], "2026-06-26")
        self.assertEqual(response["metric_count"], 0)
        self.assertEqual(response["coverage"]["expected_days"], 90)
        self.assertEqual(response["coverage"]["available_days"], 0)
        self.assertEqual(response["coverage"]["missing_days"], 90)
        self.assertIsNone(response["latest_metric"])
        self.assertEqual(response["series"], [])
        self.assertEqual(
            response["baselines"],
            {
                "resting_heart_rate": None,
                "hrv_ms": None,
                "stress_avg": None,
                "steps": None,
            },
        )

    def test_stats_supports_expected_ranges(self) -> None:
        self.seed_metric("2026-06-24")
        service = GarminService(ExplodingGarminClient())

        for range_value, days in (("35", 35), ("90", 90), ("180", 180), ("365", 365)):
            with self.subTest(range_value=range_value):
                response = service.stats(range_value, today=date(2026, 6, 26))
                expected_start = (date(2026, 6, 26) - timedelta(days=days - 1)).isoformat()

                self.assertEqual(response["range"], range_value)
                self.assertEqual(response["date_from"], expected_start)
                self.assertEqual(response["date_to"], "2026-06-26")
                self.assertEqual(response["coverage"]["expected_days"], days)

        all_response = service.stats("all", today=date(2026, 6, 26))

        self.assertEqual(all_response["range"], "all")
        self.assertEqual(all_response["date_from"], "2026-06-24")
        self.assertEqual(all_response["date_to"], "2026-06-24")
        self.assertIsNone(all_response["coverage"]["expected_days"])
        self.assertIsNone(all_response["coverage"]["missing_days"])

    def test_stats_rejects_unknown_range(self) -> None:
        service = GarminService(ExplodingGarminClient())

        with self.assertRaises(ValueError):
            service.stats("14", today=date(2026, 6, 26))

    def test_stats_series_is_chronological(self) -> None:
        self.seed_metric("2026-06-25")
        self.seed_metric("2026-06-23")
        self.seed_metric("2026-06-24")
        service = GarminService(ExplodingGarminClient())

        response = service.stats("35", today=date(2026, 6, 26))

        self.assertEqual(
            [point["date"] for point in response["series"]],
            ["2026-06-23", "2026-06-24", "2026-06-25"],
        )

    def test_stats_preserves_null_metric_values(self) -> None:
        self.seed_metric(
            "2026-06-26",
            resting_heart_rate=None,
            hrv_ms=None,
            stress_avg=None,
            body_battery_start=None,
            body_battery_end=None,
            steps=None,
        )
        service = GarminService(ExplodingGarminClient())

        point = service.stats("35", today=date(2026, 6, 26))["series"][0]

        self.assertIsNone(point["resting_heart_rate"])
        self.assertIsNone(point["hrv_ms"])
        self.assertIsNone(point["stress_avg"])
        self.assertIsNone(point["body_battery_start"])
        self.assertIsNone(point["body_battery_end"])
        self.assertIsNone(point["steps"])

    def test_stats_coverage_counts_only_selected_range(self) -> None:
        self.seed_metric("2026-05-22")
        self.seed_metric("2026-06-01")
        self.seed_metric("2026-06-10")
        self.seed_metric("2026-06-26")
        service = GarminService(ExplodingGarminClient())

        response = service.stats("35", today=date(2026, 6, 26))

        self.assertEqual(response["metric_count"], 3)
        self.assertEqual(response["coverage"]["available_days"], 3)
        self.assertEqual(response["coverage"]["missing_days"], 32)

    def test_stats_baselines_require_enough_samples(self) -> None:
        for offset in range(6):
            metric_date = (date(2026, 6, 26) - timedelta(days=offset)).isoformat()
            self.seed_metric(metric_date, resting_heart_rate=50 + offset)
        service = GarminService(ExplodingGarminClient())

        response = service.stats("35", today=date(2026, 6, 26))

        self.assertIsNone(response["baselines"]["resting_heart_rate"])

    def test_stats_baselines_use_recent_median_with_enough_samples(self) -> None:
        for offset in range(8):
            metric_date = (date(2026, 6, 26) - timedelta(days=offset)).isoformat()
            self.seed_metric(
                metric_date,
                resting_heart_rate=50 + offset,
                hrv_ms=40.0 + offset,
                stress_avg=20 + offset,
                steps=1000 * (offset + 1),
            )
        service = GarminService(ExplodingGarminClient())

        response = service.stats("35", today=date(2026, 6, 26))

        self.assertEqual(response["baselines"]["resting_heart_rate"], 53.5)
        self.assertEqual(response["baselines"]["hrv_ms"], 43.5)
        self.assertEqual(response["baselines"]["stress_avg"], 23.5)
        self.assertEqual(response["baselines"]["steps"], 4500.0)

    def test_stats_works_when_disconnected_but_history_exists(self) -> None:
        self.seed_metric("2026-06-26", hrv_ms=44.0)
        fake_client = FakeGarminDataClient({})
        fake_client.connected = False
        service = GarminService(fake_client)

        response = service.stats("35", today=date(2026, 6, 26))

        self.assertEqual(response["metric_count"], 1)
        self.assertEqual(response["series"][0]["hrv_ms"], 44.0)

    def test_stats_response_never_exposes_raw_diagnostics(self) -> None:
        self.seed_metric("2026-06-26")
        service = GarminService(ExplodingGarminClient())

        response = service.stats("35", today=date(2026, 6, 26))

        self.assertNotIn("raw_diagnostics", json.dumps(response))

    def test_stats_does_not_call_garmin_client(self) -> None:
        self.seed_metric("2026-06-26")
        service = GarminService(ExplodingGarminClient())

        response = service.stats("35", today=date(2026, 6, 26))

        self.assertEqual(response["metric_count"], 1)

    def test_only_garmin_client_imports_garminconnect(self) -> None:
        app_dir = Path(__file__).resolve().parents[1] / "app"
        matches = []
        for path in app_dir.rglob("*.py"):
            if "garminconnect" in path.read_text(encoding="utf-8"):
                matches.append(path.relative_to(app_dir).as_posix())

        self.assertEqual(matches, ["services/garmin_client.py"])


if __name__ == "__main__":
    unittest.main()