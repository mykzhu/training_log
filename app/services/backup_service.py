import logging
import math
import sqlite3
from datetime import datetime
from typing import Any

from app.db import (
    get_db,
    initialize_exercise_settings,
    seed_default_exercises,
)
from app.services.analysis_service import profile_key_for_exercise_name


logger = logging.getLogger("training_log")

BACKUP_SCHEMA_VERSION = 3
BACKUP_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "exercises": ("id", "name", "is_active", "sort_order", "profile_key"),
    "exercise_weight_options": ("id", "exercise_id", "weight", "sort_order"),
    "workouts": (
        "id",
        "workout_date",
        "created_at",
        "finished_at",
        "session_rpe",
        "lower_back_pain",
        "duration_seconds",
    ),
    "workout_exercises": ("id", "workout_id", "exercise_id", "position"),
    "set_entries": (
        "id",
        "workout_exercise_id",
        "set_number",
        "weight",
        "reps",
        "created_at",
    ),
}
BACKUP_TABLES = tuple(BACKUP_TABLE_COLUMNS)
LEGACY_BACKUP_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "exercises": ("id", "name"),
    "workouts": BACKUP_TABLE_COLUMNS["workouts"],
    "workout_exercises": BACKUP_TABLE_COLUMNS["workout_exercises"],
    "set_entries": BACKUP_TABLE_COLUMNS["set_entries"],
}
DRAFT_TABLES = (
    "active_draft_sets",
    "active_draft_exercises",
    "active_workout_draft",
)


def clear_draft_tables(conn: sqlite3.Connection) -> None:
    for table_name in DRAFT_TABLES:
        conn.execute(f"DELETE FROM {table_name}")


def get_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {
        table_name: conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        for table_name in BACKUP_TABLES
    }
    logger.debug("db.table_counts counts=%s", counts)
    return counts


def build_backup_payload() -> dict[str, Any]:
    with get_db() as conn:
        tables = {}

        for table_name, columns in BACKUP_TABLE_COLUMNS.items():
            column_sql = ", ".join(columns)
            rows = conn.execute(
                f"SELECT {column_sql} FROM {table_name} ORDER BY id ASC"
            ).fetchall()
            tables[table_name] = [dict(row) for row in rows]

    payload = {
        "app": "training-log",
        "schema_version": BACKUP_SCHEMA_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "tables": tables,
    }
    logger.info(
        "backup.build schema_version=%s counts=%s",
        BACKUP_SCHEMA_VERSION,
        {table_name: len(rows) for table_name, rows in tables.items()},
    )
    return payload


def validate_backup_payload(payload: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise ValueError("Backup file must contain a JSON object.")

    schema_version = payload.get("schema_version")
    if schema_version not in (1, 2, BACKUP_SCHEMA_VERSION):
        raise ValueError(
            f"Unsupported backup schema version. Expected 1, 2 or {BACKUP_SCHEMA_VERSION}."
        )

    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("Backup file is missing the tables object.")

    validated: dict[str, list[dict[str, Any]]] = {}

    table_columns = (
        BACKUP_TABLE_COLUMNS
        if schema_version == BACKUP_SCHEMA_VERSION
        else LEGACY_BACKUP_TABLE_COLUMNS
    )

    for table_name, columns in table_columns.items():
        rows = tables.get(table_name)
        if not isinstance(rows, list):
            raise ValueError(f"Backup table {table_name} must be a list.")

        validated_rows: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise ValueError(f"Row {index} in {table_name} must be an object.")

            row_data: dict[str, Any] = {}
            for column in columns:
                if column in row:
                    row_data[column] = row[column]
                elif (
                    table_name == "workouts"
                    and column == "duration_seconds"
                    and schema_version == 1
                ):
                    row_data[column] = None
                else:
                    raise ValueError(
                        f"Row {index} in {table_name} is missing {column}."
                    )

            validated_rows.append(row_data)

        validated[table_name] = validated_rows

    if schema_version != BACKUP_SCHEMA_VERSION:
        for index, row in enumerate(validated["exercises"], start=1):
            row["is_active"] = 1
            row["sort_order"] = index * 10
            row["profile_key"] = profile_key_for_exercise_name(str(row["name"]))

        validated["exercise_weight_options"] = []

    validate_exercise_weight_options(validated["exercise_weight_options"], validated)

    logger.info(
        "backup.validate.success schema_version=%s target_schema_version=%s counts=%s",
        schema_version,
        BACKUP_SCHEMA_VERSION,
        {table_name: len(rows) for table_name, rows in validated.items()},
    )
    return validated


def validate_exercise_weight_options(
    rows: list[dict[str, Any]],
    tables: dict[str, list[dict[str, Any]]],
) -> None:
    exercise_ids = {int(row["id"]) for row in tables["exercises"]}
    seen_pairs: set[tuple[int, float]] = set()

    for index, row in enumerate(rows, start=1):
        exercise_id = int(row["exercise_id"])
        if exercise_id not in exercise_ids:
            raise ValueError(
                f"Row {index} in exercise_weight_options references an unknown exercise."
            )

        weight = float(row["weight"])
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(
                f"Row {index} in exercise_weight_options has an invalid weight."
            )

        pair = (exercise_id, round(weight, 4))
        if pair in seen_pairs:
            raise ValueError(
                f"Row {index} in exercise_weight_options duplicates a weight."
            )
        seen_pairs.add(pair)


def reset_sqlite_sequences(conn: sqlite3.Connection) -> None:
    logger.debug("db.sqlite_sequence.reset.start")
    placeholders = ", ".join("?" for _ in BACKUP_TABLES)
    conn.execute(
        f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
        BACKUP_TABLES,
    )

    for table_name in BACKUP_TABLES:
        max_id = conn.execute(
            f"SELECT COALESCE(MAX(id), 0) FROM {table_name}"
        ).fetchone()[0]

        if max_id:
            conn.execute(
                "INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)",
                (table_name, max_id),
            )

    logger.debug("db.sqlite_sequence.reset.done")


def restore_backup_payload(payload: Any) -> None:
    schema_version = payload.get("schema_version") if isinstance(payload, dict) else None
    tables = validate_backup_payload(payload)
    logger.warning(
        "backup.restore.start counts=%s",
        {table_name: len(rows) for table_name, rows in tables.items()},
    )

    with get_db() as conn:
        clear_draft_tables(conn)

        for table_name in reversed(BACKUP_TABLES):
            conn.execute(f"DELETE FROM {table_name}")

        for table_name, columns in BACKUP_TABLE_COLUMNS.items():
            column_sql = ", ".join(columns)
            placeholders = ", ".join("?" for _ in columns)
            insert_sql = (
                f"INSERT INTO {table_name} ({column_sql}) "
                f"VALUES ({placeholders})"
            )

            for row in tables[table_name]:
                conn.execute(insert_sql, tuple(row[column] for column in columns))

        reset_sqlite_sequences(conn)
        initialize_exercise_settings(
            conn,
            force_weight_migration=schema_version != BACKUP_SCHEMA_VERSION,
        )

    logger.warning(
        "backup.restore.done counts=%s",
        {table_name: len(rows) for table_name, rows in tables.items()},
    )


def reset_database_data() -> None:
    with get_db() as conn:
        logger.warning("db.reset.start")

        clear_draft_tables(conn)

        for table_name in reversed(BACKUP_TABLES):
            conn.execute(f"DELETE FROM {table_name}")

        placeholders = ", ".join("?" for _ in BACKUP_TABLES)
        conn.execute(
            f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
            BACKUP_TABLES,
        )

        seed_default_exercises(conn)
        initialize_exercise_settings(conn, force_weight_migration=True)

        logger.warning("db.reset.done")
