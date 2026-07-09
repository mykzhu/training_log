import sqlite3
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Protocol

from app.migrations import (
    v001_initial,
    v002_workout_metadata,
    v003_active_draft,
    v004_exercise_settings,
    v005_performance_indexes,
    v006_garmin_daily_metrics,
    v007_analysis_profiles,
    v008_garmin_auto_sync_settings,
    v009_exercise_option_settings,
    v010_exercise_measurement_type,
)


class Migration(Protocol):
    VERSION: int
    NAME: str

    @staticmethod
    def up(conn: sqlite3.Connection) -> None: ...


MIGRATIONS: tuple[Migration, ...] = (
    v001_initial,
    v002_workout_metadata,
    v003_active_draft,
    v004_exercise_settings,
    v005_performance_indexes,
    v006_garmin_daily_metrics,
    v007_analysis_profiles,
    v008_garmin_auto_sync_settings,
    v009_exercise_option_settings,
    v010_exercise_measurement_type,
)


def migration_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def applied_versions(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute(
        """
        SELECT version
        FROM schema_migrations
        """
    ).fetchall()
    return {
        int(row["version"] if isinstance(row, sqlite3.Row) else row[0])
        for row in rows
    }


def run_migrations(
    conn: sqlite3.Connection,
    migrations: Sequence[Migration] = MIGRATIONS,
) -> None:
    ensure_schema_migrations_table(conn)
    seen_versions = applied_versions(conn)

    for migration in sorted(migrations, key=lambda item: item.VERSION):
        if migration.VERSION in seen_versions:
            continue

        try:
            conn.execute("BEGIN")
            migration.up(conn)
            conn.execute(
                """
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (?, ?, ?)
                """,
                (
                    migration.VERSION,
                    migration.NAME,
                    migration_timestamp(),
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        seen_versions.add(migration.VERSION)
