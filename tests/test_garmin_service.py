import tempfile
import unittest
from datetime import date
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

    def test_only_garmin_client_imports_garminconnect(self) -> None:
        app_dir = Path(__file__).resolve().parents[1] / "app"
        matches = []
        for path in app_dir.rglob("*.py"):
            if "garminconnect" in path.read_text(encoding="utf-8"):
                matches.append(path.relative_to(app_dir).as_posix())

        self.assertEqual(matches, ["services/garmin_client.py"])


if __name__ == "__main__":
    unittest.main()