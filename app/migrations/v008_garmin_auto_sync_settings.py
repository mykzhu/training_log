import sqlite3
from datetime import datetime, timezone


VERSION = 8
NAME = "garmin_auto_sync_settings"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS garmin_sync_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            auto_sync_enabled INTEGER NOT NULL DEFAULT 0
                CHECK (auto_sync_enabled IN (0, 1)),
            sync_after_local_time TEXT NOT NULL DEFAULT '07:00',
            sync_days INTEGER NOT NULL DEFAULT 35
                CHECK (sync_days BETWEEN 1 AND 90),
            last_auto_attempt_at TEXT,
            last_auto_success_at TEXT,
            last_auto_error TEXT,
            last_auto_result_json TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO garmin_sync_settings (
            id,
            auto_sync_enabled,
            sync_after_local_time,
            sync_days,
            updated_at
        )
        VALUES (1, 0, '07:00', 35, ?)
        """,
        (utc_now(),),
    )
