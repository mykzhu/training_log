import sqlite3


VERSION = 6
NAME = "garmin_daily_metrics"


def up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS garmin_daily_metrics (
            date TEXT PRIMARY KEY,
            resting_heart_rate INTEGER,
            hrv_ms REAL,
            stress_avg INTEGER,
            body_battery_start INTEGER,
            body_battery_end INTEGER,
            steps INTEGER,
            synced_at TEXT NOT NULL,
            raw_diagnostics TEXT NOT NULL DEFAULT '{}'
        )
        """
    )