import json
import sqlite3
from typing import Any

from app.db import get_db


GARMIN_DAILY_METRIC_COLUMNS = (
    "date",
    "resting_heart_rate",
    "hrv_ms",
    "stress_avg",
    "body_battery_start",
    "body_battery_end",
    "steps",
    "synced_at",
    "raw_diagnostics",
)
GARMIN_VALUE_COLUMNS = (
    "resting_heart_rate",
    "hrv_ms",
    "stress_avg",
    "body_battery_start",
    "body_battery_end",
    "steps",
)


def serialize_metric_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    raw_diagnostics = row["raw_diagnostics"] or "{}"
    try:
        diagnostics = json.loads(str(raw_diagnostics))
    except json.JSONDecodeError:
        diagnostics = {"invalid": True}

    return {
        "date": row["date"],
        "resting_heart_rate": row["resting_heart_rate"],
        "hrv_ms": row["hrv_ms"],
        "stress_avg": row["stress_avg"],
        "body_battery_start": row["body_battery_start"],
        "body_battery_end": row["body_battery_end"],
        "steps": row["steps"],
        "synced_at": row["synced_at"],
        "raw_diagnostics": diagnostics,
    }


def list_daily_metrics(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    where = []
    params: list[Any] = []

    if start_date is not None:
        where.append("date >= ?")
        params.append(start_date)

    if end_date is not None:
        where.append("date <= ?")
        params.append(end_date)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT ?"
        params.append(limit)

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT {', '.join(GARMIN_DAILY_METRIC_COLUMNS)}
            FROM garmin_daily_metrics
            {where_sql}
            ORDER BY date DESC
            {limit_sql}
            """,
            params,
        ).fetchall()

    return [serialize_metric_row(row) for row in rows]


def list_daily_metrics_chronological(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    where = []
    params: list[Any] = []

    if start_date is not None:
        where.append("date >= ?")
        params.append(start_date)

    if end_date is not None:
        where.append("date <= ?")
        params.append(end_date)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    columns = ("date", *GARMIN_VALUE_COLUMNS, "synced_at")

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT {', '.join(columns)}
            FROM garmin_daily_metrics
            {where_sql}
            ORDER BY date ASC
            """,
            params,
        ).fetchall()

    return [{column: row[column] for column in columns} for row in rows]


def get_daily_metric(metric_date: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            f"""
            SELECT {', '.join(GARMIN_DAILY_METRIC_COLUMNS)}
            FROM garmin_daily_metrics
            WHERE date = ?
            """,
            (metric_date,),
        ).fetchone()

    return serialize_metric_row(row) if row else None


def get_latest_metric() -> dict[str, Any] | None:
    metrics = list_daily_metrics(limit=1)
    return metrics[0] if metrics else None


def get_metric_count_since(start_date: str) -> int:
    with get_db() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM garmin_daily_metrics WHERE date >= ?",
                (start_date,),
            ).fetchone()[0]
        )


def get_last_synced_at() -> str | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT MAX(synced_at) AS last_synced_at FROM garmin_daily_metrics"
        ).fetchone()

    return str(row["last_synced_at"]) if row and row["last_synced_at"] else None


def upsert_daily_metric(metric: dict[str, Any]) -> None:
    values = {column: metric.get(column) for column in GARMIN_DAILY_METRIC_COLUMNS}
    values["raw_diagnostics"] = json.dumps(
        values.get("raw_diagnostics") or {},
        sort_keys=True,
        separators=(",", ":"),
    )

    columns = list(GARMIN_DAILY_METRIC_COLUMNS)
    placeholders = ", ".join("?" for _ in columns)
    update_columns = [
        f"{column} = COALESCE(excluded.{column}, garmin_daily_metrics.{column})"
        for column in GARMIN_VALUE_COLUMNS
    ]
    update_columns.extend(
        [
            "synced_at = excluded.synced_at",
            "raw_diagnostics = excluded.raw_diagnostics",
        ]
    )

    with get_db() as conn:
        conn.execute(
            f"""
            INSERT INTO garmin_daily_metrics ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(date) DO UPDATE SET {', '.join(update_columns)}
            """,
            tuple(values[column] for column in columns),
        )


def delete_all_daily_metrics() -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM garmin_daily_metrics")