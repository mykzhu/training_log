import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.db import get_db


SETTINGS_ID = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def serialize_settings(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    result_json = row["last_auto_result_json"]
    last_result = None
    if result_json:
        try:
            last_result = json.loads(str(result_json))
        except json.JSONDecodeError:
            last_result = {"invalid": True}

    return {
        "enabled": bool(row["auto_sync_enabled"]),
        "sync_after_local_time": row["sync_after_local_time"],
        "sync_days": int(row["sync_days"]),
        "last_attempt_at": row["last_auto_attempt_at"],
        "last_success_at": row["last_auto_success_at"],
        "last_error": row["last_auto_error"],
        "last_result": last_result,
        "updated_at": row["updated_at"],
    }


def ensure_default_settings(conn: sqlite3.Connection) -> None:
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


def get_garmin_auto_sync_settings(
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    def fetch(active_conn: sqlite3.Connection) -> dict[str, Any]:
        ensure_default_settings(active_conn)
        row = active_conn.execute(
            """
            SELECT
                auto_sync_enabled,
                sync_after_local_time,
                sync_days,
                last_auto_attempt_at,
                last_auto_success_at,
                last_auto_error,
                last_auto_result_json,
                updated_at
            FROM garmin_sync_settings
            WHERE id = ?
            """,
            (SETTINGS_ID,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Garmin auto-sync settings row is missing.")
        return serialize_settings(row)

    if conn is not None:
        return fetch(conn)

    with get_db() as active_conn:
        return fetch(active_conn)


def update_garmin_auto_sync_settings(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        raise ValueError("At least one auto-sync setting must be provided.")

    allowed_columns = {
        "enabled": "auto_sync_enabled",
        "sync_after_local_time": "sync_after_local_time",
        "sync_days": "sync_days",
    }
    assignments = []
    params: list[Any] = []
    for key, column in allowed_columns.items():
        if key not in payload:
            continue
        value = payload[key]
        if key == "enabled":
            value = 1 if bool(value) else 0
        assignments.append(f"{column} = ?")
        params.append(value)

    if not assignments:
        raise ValueError("At least one auto-sync setting must be provided.")

    assignments.append("updated_at = ?")
    params.append(utc_now())
    params.append(SETTINGS_ID)

    with get_db() as conn:
        ensure_default_settings(conn)
        conn.execute(
            f"""
            UPDATE garmin_sync_settings
            SET {', '.join(assignments)}
            WHERE id = ?
            """,
            tuple(params),
        )
        return get_garmin_auto_sync_settings(conn)


def record_garmin_auto_sync_attempt(at: str) -> dict[str, Any]:
    with get_db() as conn:
        ensure_default_settings(conn)
        conn.execute(
            """
            UPDATE garmin_sync_settings
            SET last_auto_attempt_at = ?,
                last_auto_error = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (at, utc_now(), SETTINGS_ID),
        )
        return get_garmin_auto_sync_settings(conn)


def record_garmin_auto_sync_success(
    *,
    at: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    with get_db() as conn:
        ensure_default_settings(conn)
        conn.execute(
            """
            UPDATE garmin_sync_settings
            SET last_auto_success_at = ?,
                last_auto_error = NULL,
                last_auto_result_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                at,
                json.dumps(result, sort_keys=True, separators=(",", ":")),
                utc_now(),
                SETTINGS_ID,
            ),
        )
        return get_garmin_auto_sync_settings(conn)


def record_garmin_auto_sync_error(
    *,
    at: str,
    error: str,
) -> dict[str, Any]:
    with get_db() as conn:
        ensure_default_settings(conn)
        conn.execute(
            """
            UPDATE garmin_sync_settings
            SET last_auto_error = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (error[:500], utc_now(), SETTINGS_ID),
        )
        return get_garmin_auto_sync_settings(conn)
