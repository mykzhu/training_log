import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from app import config
from app.db import init_db
import app.main as main
import app.routes.api_garmin as api_garmin
from app.routes.api_garmin import (
    disconnect_garmin,
    get_garmin_daily_metrics,
    get_garmin_auto_sync_settings,
    get_garmin_stats,
    get_garmin_status,
    login_garmin,
    submit_garmin_mfa,
    sync_garmin,
    update_garmin_auto_sync_settings,
)
from app.schemas import (
    GarminAutoSyncSettingsUpdateRequest,
    GarminLoginRequest,
    GarminMfaRequest,
    GarminSyncRequest,
)


class FakeGarminApiService:
    def __init__(self) -> None:
        self.synced_days: int | None = None
        self.stats_range: str | None = None
        self.disconnected = False

    def status(self) -> dict[str, Any]:
        return {
            "connected": True,
            "last_synced_at": "2026-06-26T08:00:00",
            "latest_metric": None,
            "pending_mfa": False,
        }

    def login(self, username: str, password: str) -> dict[str, Any]:
        return {"connected": True, "mfa_required": False, "mfa_token": None}

    def submit_mfa(self, mfa_token: str, code: str) -> dict[str, Any]:
        return {"connected": True, "mfa_required": False, "mfa_token": None}

    def disconnect(self) -> dict[str, Any]:
        self.disconnected = True
        return self.status()

    def sync(self, days: int | None = None) -> dict[str, Any]:
        self.synced_days = 35 if days is None else days
        return {
            "synced": True,
            "days": self.synced_days,
            "saved_dates": ["2026-06-26"],
            "skipped_dates": [],
            "errors": {},
            "status": self.status(),
        }

    def list_daily(self, days: int | None = None) -> dict[str, Any]:
        return {"days": 35 if days is None else days, "metrics": []}

    def stats(self, range_value: str = "90") -> dict[str, Any]:
        self.stats_range = range_value
        return {
            "range": range_value,
            "date_from": "2026-03-29",
            "date_to": "2026-06-26",
            "metric_count": 0,
            "coverage": {
                "expected_days": 90,
                "available_days": 0,
                "missing_days": 90,
            },
            "latest_metric": None,
            "series": [],
            "baselines": {
                "resting_heart_rate": None,
                "hrv_ms": None,
                "stress_avg": None,
                "steps": None,
            },
        }


class GarminApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_service = api_garmin.garmin_service
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()
        self.fake_service = FakeGarminApiService()
        api_garmin.garmin_service = self.fake_service

    def tearDown(self) -> None:
        api_garmin.garmin_service = self.original_service
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_garmin_routes_are_registered(self) -> None:
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in main.app.routes
            if hasattr(route, "methods")
        }

        self.assertIn(("/api/v1/garmin/status", ("GET",)), routes)
        self.assertIn(("/api/v1/garmin/login", ("POST",)), routes)
        self.assertIn(("/api/v1/garmin/mfa", ("POST",)), routes)
        self.assertIn(("/api/v1/garmin/disconnect", ("POST",)), routes)
        self.assertIn(("/api/v1/garmin/sync", ("POST",)), routes)
        self.assertIn(("/api/v1/garmin/auto-sync", ("GET",)), routes)
        self.assertIn(("/api/v1/garmin/auto-sync", ("PATCH",)), routes)
        self.assertIn(("/api/v1/garmin/daily", ("GET",)), routes)
        self.assertIn(("/api/v1/garmin/stats", ("GET",)), routes)

    def test_status_login_mfa_disconnect_sync_and_daily_routes_delegate(self) -> None:
        self.assertTrue(get_garmin_status()["connected"])
        self.assertTrue(
            login_garmin(
                GarminLoginRequest(username="user@example.com", password="secret")
            )["connected"]
        )
        self.assertTrue(
            submit_garmin_mfa(
                GarminMfaRequest(mfa_token="token", code="123456")
            )["connected"]
        )
        self.assertTrue(disconnect_garmin()["connected"])
        auto_sync_response = update_garmin_auto_sync_settings(
            GarminAutoSyncSettingsUpdateRequest(enabled=True)
        )

        sync_response = sync_garmin(GarminSyncRequest(days=7))
        daily_response = get_garmin_daily_metrics(days=14)
        stats_response = get_garmin_stats(range_value="180")

        self.assertTrue(auto_sync_response["enabled"])
        self.assertTrue(get_garmin_auto_sync_settings()["enabled"])
        self.assertEqual(sync_response["days"], 7)
        self.assertEqual(self.fake_service.synced_days, 7)
        self.assertEqual(daily_response["days"], 14)
        self.assertEqual(stats_response["range"], "180")
        self.assertEqual(self.fake_service.stats_range, "180")
        self.assertTrue(self.fake_service.disconnected)

    def test_sync_days_model_allows_only_one_to_ninety(self) -> None:
        with self.assertRaises(ValidationError):
            GarminSyncRequest(days=0)

        with self.assertRaises(ValidationError):
            GarminSyncRequest(days=91)

    def test_route_errors_are_json_api_friendly(self) -> None:
        class BrokenService(FakeGarminApiService):
            def sync(self, days: int | None = None) -> dict[str, Any]:
                raise ValueError("bad sync")

        api_garmin.garmin_service = BrokenService()

        with self.assertRaises(HTTPException) as exc:
            sync_garmin(GarminSyncRequest(days=1))

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "bad sync")


if __name__ == "__main__":
    unittest.main()
