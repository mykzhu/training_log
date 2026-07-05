import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app import config
from app.db import get_db, init_db
from app.repositories import garmin_sync_settings
import app.routes.api_garmin as api_garmin
from app.routes.api_garmin import update_garmin_auto_sync_settings
from app.schemas import GarminAutoSyncSettingsUpdateRequest
from app.services import garmin_auto_sync_service
from app.services.backup_service import build_backup_payload


class FakeGarminService:
    def __init__(self, *, connected: bool = True, fail: bool = False) -> None:
        self.connected = connected
        self.fail = fail
        self.synced_days: list[int] = []

    def status(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "last_synced_at": None,
            "latest_metric": None,
            "pending_mfa": False,
        }

    def sync(self, days: int | None = None) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("token secret should not leak")
        sync_days = 35 if days is None else days
        self.synced_days.append(sync_days)
        return {
            "synced": True,
            "days": sync_days,
            "saved_dates": ["2026-07-02"],
            "skipped_dates": ["2026-07-01"],
            "errors": {"2026-07-01:hrv": "missing"},
            "status": self.status(),
        }


class GarminAutoSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_timezone = config.APP_TIMEZONE
        self.original_service = garmin_auto_sync_service.garmin_service
        self.original_to_thread = asyncio.to_thread
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        config.APP_TIMEZONE = "UTC"
        init_db()

    def tearDown(self) -> None:
        asyncio.to_thread = self.original_to_thread
        garmin_auto_sync_service.garmin_service = self.original_service
        config.APP_TIMEZONE = self.original_timezone
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_default_settings_row_exists_after_migration(self) -> None:
        settings = garmin_sync_settings.get_garmin_auto_sync_settings()

        self.assertFalse(settings["enabled"])
        self.assertEqual(settings["sync_after_local_time"], "07:00")
        self.assertEqual(settings["sync_days"], 35)

    def test_patch_persists_enabled_time_and_days(self) -> None:
        settings = garmin_auto_sync_service.update_settings(
            {
                "enabled": True,
                "sync_after_local_time": "08:30",
                "sync_days": 14,
            }
        )

        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["sync_after_local_time"], "08:30")
        self.assertEqual(settings["sync_days"], 14)
        self.assertEqual(settings["timezone"], "UTC")

    def test_rejects_invalid_or_empty_patch(self) -> None:
        with self.assertRaises(ValueError):
            garmin_auto_sync_service.update_settings({})

        with self.assertRaises(ValueError):
            garmin_auto_sync_service.update_settings(
                {"sync_after_local_time": "24:00"}
            )

        with self.assertRaises(ValueError):
            garmin_auto_sync_service.update_settings({"sync_after_local_time": "7:00"})

        with self.assertRaises(ValueError):
            garmin_auto_sync_service.update_settings({"sync_days": 0})

        with self.assertRaises(ValueError):
            garmin_auto_sync_service.update_settings({"sync_days": 91})

        for payload in (
            GarminAutoSyncSettingsUpdateRequest(enabled=None),
            GarminAutoSyncSettingsUpdateRequest(sync_after_local_time=None),
            GarminAutoSyncSettingsUpdateRequest(sync_days=None),
        ):
            with self.assertRaises(HTTPException) as exc:
                update_garmin_auto_sync_settings(payload)
            self.assertEqual(exc.exception.status_code, 400)

        with self.assertRaises(HTTPException) as exc:
            update_garmin_auto_sync_settings(
                GarminAutoSyncSettingsUpdateRequest()
            )

        self.assertEqual(exc.exception.status_code, 400)

    def test_parse_int_env_value_defaults_and_clamps(self) -> None:
        self.assertEqual(
            config.parse_int_env_value(None, 3600, minimum=300),
            3600,
        )
        self.assertEqual(
            config.parse_int_env_value("abc", 3600, minimum=300),
            3600,
        )
        self.assertEqual(
            config.parse_int_env_value("60", 3600, minimum=300),
            300,
        )
        self.assertEqual(
            config.parse_int_env_value("600", 3600, minimum=300),
            600,
        )

    def test_due_logic_requires_enabled_connected_time_and_no_attempt_today(self) -> None:
        tz = ZoneInfo("UTC")
        settings = {
            "enabled": True,
            "sync_after_local_time": "07:00",
            "sync_days": 35,
            "last_attempt_at": None,
            "last_success_at": None,
        }

        self.assertFalse(
            garmin_auto_sync_service.is_auto_sync_due(
                {**settings, "enabled": False},
                connected=True,
                now_local=datetime(2026, 7, 2, 8, 0, tzinfo=tz),
            )
        )
        self.assertFalse(
            garmin_auto_sync_service.is_auto_sync_due(
                settings,
                connected=False,
                now_local=datetime(2026, 7, 2, 8, 0, tzinfo=tz),
            )
        )
        self.assertFalse(
            garmin_auto_sync_service.is_auto_sync_due(
                settings,
                connected=True,
                now_local=datetime(2026, 7, 2, 6, 59, tzinfo=tz),
            )
        )
        self.assertTrue(
            garmin_auto_sync_service.is_auto_sync_due(
                settings,
                connected=True,
                now_local=datetime(2026, 7, 2, 7, 0, tzinfo=tz),
            )
        )
        self.assertEqual(
            garmin_auto_sync_service.next_eligible_auto_sync_at(
                settings,
                now_local=datetime(2026, 7, 2, 8, 0, tzinfo=tz),
            ),
            datetime(2026, 7, 2, 7, 0, tzinfo=tz),
        )
        self.assertEqual(
            garmin_auto_sync_service.next_eligible_auto_sync_at(
                settings,
                now_local=datetime(2026, 7, 2, 6, 0, tzinfo=tz),
            ),
            datetime(2026, 7, 2, 7, 0, tzinfo=tz),
        )
        self.assertFalse(
            garmin_auto_sync_service.is_auto_sync_due(
                {
                    **settings,
                    "last_success_at": "2026-07-02T07:05:00+03:00",
                },
                connected=True,
                now_local=datetime(2026, 7, 2, 8, 0, tzinfo=tz),
            )
        )
        self.assertEqual(
            garmin_auto_sync_service.next_eligible_auto_sync_at(
                {
                    **settings,
                    "last_success_at": "2026-07-02T07:05:00+00:00",
                },
                now_local=datetime(2026, 7, 2, 8, 0, tzinfo=tz),
            ),
            datetime(2026, 7, 3, 7, 0, tzinfo=tz),
        )
        self.assertEqual(
            garmin_auto_sync_service.next_eligible_auto_sync_at(
                {
                    **settings,
                    "last_attempt_at": "2026-07-02T07:05:00+00:00",
                },
                now_local=datetime(2026, 7, 2, 8, 0, tzinfo=tz),
            ),
            datetime(2026, 7, 3, 7, 0, tzinfo=tz),
        )

    def test_run_once_records_success_and_skips_second_attempt_same_day(self) -> None:
        fake_service = FakeGarminService()
        garmin_auto_sync_service.garmin_service = fake_service
        to_thread_calls = []

        async def fake_to_thread(func: Any, *args: Any, **kwargs: Any) -> Any:
            to_thread_calls.append((func, args, kwargs))
            return func(*args, **kwargs)

        original_to_thread = asyncio.to_thread
        asyncio.to_thread = fake_to_thread
        try:
            garmin_auto_sync_service.update_settings(
                {
                    "enabled": True,
                    "sync_after_local_time": "00:00",
                    "sync_days": 14,
                }
            )
            first = asyncio.run(garmin_auto_sync_service.run_garmin_auto_sync_once())
            second = asyncio.run(garmin_auto_sync_service.run_garmin_auto_sync_once())
        finally:
            asyncio.to_thread = original_to_thread

        settings = garmin_sync_settings.get_garmin_auto_sync_settings()

        self.assertTrue(first["ran"])
        self.assertTrue(first["success"])
        self.assertFalse(second["ran"])
        self.assertEqual(fake_service.synced_days, [14])
        self.assertEqual(to_thread_calls[0][0], fake_service.sync)
        self.assertEqual(to_thread_calls[0][1], (14,))
        self.assertIsNotNone(settings["last_attempt_at"])
        self.assertIsNotNone(settings["last_success_at"])
        self.assertEqual(
            settings["last_result"],
            {"days": 14, "saved": 1, "skipped": 1, "warnings": 1},
        )

    def test_disconnected_auto_sync_does_not_call_garmin(self) -> None:
        fake_service = FakeGarminService(connected=False)
        garmin_auto_sync_service.garmin_service = fake_service
        garmin_auto_sync_service.update_settings(
            {"enabled": True, "sync_after_local_time": "00:00"}
        )

        result = asyncio.run(garmin_auto_sync_service.run_garmin_auto_sync_once())

        self.assertFalse(result["ran"])
        self.assertEqual(fake_service.synced_days, [])

    def test_backup_payload_does_not_include_auto_sync_settings(self) -> None:
        garmin_auto_sync_service.update_settings({"enabled": True})

        with get_db() as conn:
            table_names = {
                row["name"]
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                )
            }

        self.assertIn("garmin_sync_settings", table_names)
        self.assertNotIn("garmin_sync_settings", build_backup_payload()["tables"])


if __name__ == "__main__":
    unittest.main()
