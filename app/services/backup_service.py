import json
import logging
import math
import sqlite3
from datetime import datetime
from typing import Any

from app.db import (
    EXERCISE_SETTINGS_WEIGHT_MIGRATION_KEY,
    get_db,
    initialize_exercise_settings,
    seed_default_exercises,
    set_metadata,
)
from app.repositories.analysis_profiles import (
    backup_profile_rows,
    ensure_default_analysis_profiles,
    normalize_profile_key,
)
from app.services.default_analysis_profiles import (
    DEFAULT_PROFILE_KEY,
    default_profile_rows,
    profile_key_for_exercise_name,
)


logger = logging.getLogger("training_log")

BACKUP_SCHEMA_VERSION = 5
ANALYSIS_PROFILE_BACKUP_COLUMNS: tuple[str, ...] = (
    "key",
    "label",
    "category",
    "exercise_factor",
    "compound_factor",
    "back_factor",
    "is_builtin",
    "is_active",
    "sort_order",
)
BASE_BACKUP_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
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
GARMIN_BACKUP_TABLE_COLUMNS: tuple[str, ...] = (
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
BACKUP_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "analysis_profiles": ANALYSIS_PROFILE_BACKUP_COLUMNS,
    **BASE_BACKUP_TABLE_COLUMNS,
    "garmin_daily_metrics": GARMIN_BACKUP_TABLE_COLUMNS,
}
SCHEMA_V4_BACKUP_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    **BASE_BACKUP_TABLE_COLUMNS,
    "garmin_daily_metrics": GARMIN_BACKUP_TABLE_COLUMNS,
}
BACKUP_TABLES = tuple(BACKUP_TABLE_COLUMNS)
BACKUP_SEQUENCE_TABLES = tuple(BASE_BACKUP_TABLE_COLUMNS)
LEGACY_BACKUP_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "exercises": ("id", "name"),
    "workouts": BASE_BACKUP_TABLE_COLUMNS["workouts"],
    "workout_exercises": BASE_BACKUP_TABLE_COLUMNS["workout_exercises"],
    "set_entries": BASE_BACKUP_TABLE_COLUMNS["set_entries"],
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
            if table_name == "analysis_profiles":
                tables[table_name] = backup_profile_rows(conn)
                continue

            column_sql = ", ".join(columns)
            order_sql = "date ASC" if table_name == "garmin_daily_metrics" else "id ASC"
            rows = conn.execute(
                f"SELECT {column_sql} FROM {table_name} ORDER BY {order_sql}"
            ).fetchall()
            table_rows = []
            for row in rows:
                row_data = dict(row)
                if table_name == "garmin_daily_metrics":
                    try:
                        row_data["raw_diagnostics"] = json.loads(
                            str(row_data["raw_diagnostics"] or "{}")
                        )
                    except json.JSONDecodeError:
                        row_data["raw_diagnostics"] = {"invalid": True}
                table_rows.append(row_data)
            tables[table_name] = table_rows

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


def default_backup_profile_rows() -> list[dict[str, Any]]:
    rows = []
    for row in default_profile_rows():
        rows.append(
            {
                "key": row["key"],
                "label": row["label"],
                "category": row["category"],
                "exercise_factor": row["exercise_factor"],
                "compound_factor": row["compound_factor"],
                "back_factor": row["back_factor"],
                "is_builtin": 1 if row["is_builtin"] else 0,
                "is_active": 1 if row["is_active"] else 0,
                "sort_order": row["sort_order"],
            }
        )
    return rows


def validate_backup_payload(payload: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise ValueError("Backup file must contain a JSON object.")

    schema_version = payload.get("schema_version")
    if schema_version not in (1, 2, 3, 4, BACKUP_SCHEMA_VERSION):
        raise ValueError(
            "Unsupported backup schema version. Expected 1, 2, 3, 4 or "
            f"{BACKUP_SCHEMA_VERSION}."
        )

    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("Backup file is missing the tables object.")

    validated: dict[str, list[dict[str, Any]]] = {}

    if schema_version == BACKUP_SCHEMA_VERSION:
        table_columns = BACKUP_TABLE_COLUMNS
    elif schema_version == 4:
        table_columns = SCHEMA_V4_BACKUP_TABLE_COLUMNS
    elif schema_version == 3:
        table_columns = BASE_BACKUP_TABLE_COLUMNS
    else:
        table_columns = LEGACY_BACKUP_TABLE_COLUMNS

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

    if schema_version in (1, 2):
        for index, row in enumerate(validated["exercises"], start=1):
            row["is_active"] = 1
            row["sort_order"] = index * 10
            row["profile_key"] = profile_key_for_exercise_name(str(row["name"]))

        validated["exercise_weight_options"] = []

    if schema_version != BACKUP_SCHEMA_VERSION:
        validated["analysis_profiles"] = default_backup_profile_rows()

    if schema_version < 4:
        validated["garmin_daily_metrics"] = []

    validate_table_ids(validated)
    validate_analysis_profiles(validated["analysis_profiles"])
    profile_keys = {str(row["key"]) for row in validated["analysis_profiles"]}
    validate_exercises(validated["exercises"], profile_keys)
    validate_exercise_weight_options(
        validated["exercise_weight_options"],
        validated,
        enforce_active_weights=schema_version in (3, 4, BACKUP_SCHEMA_VERSION),
    )
    validate_workout_graph(validated)
    validate_garmin_daily_metrics(validated["garmin_daily_metrics"])

    logger.info(
        "backup.validate.success schema_version=%s target_schema_version=%s counts=%s",
        schema_version,
        BACKUP_SCHEMA_VERSION,
        {table_name: len(rows) for table_name, rows in validated.items()},
    )
    return validated


def coerce_int(value: Any, context: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be an integer.") from exc

    return result


def coerce_float(value: Any, context: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be numeric.") from exc

    if not math.isfinite(result):
        raise ValueError(f"{context} must be finite.")

    return result


def validate_table_ids(tables: dict[str, list[dict[str, Any]]]) -> None:
    for table_name, rows in tables.items():
        if table_name in ("analysis_profiles", "garmin_daily_metrics"):
            continue

        seen_ids: set[int] = set()
        for index, row in enumerate(rows, start=1):
            row_id = coerce_int(row["id"], f"Row {index} in {table_name} id")
            if row_id <= 0:
                raise ValueError(f"Row {index} in {table_name} has an invalid id.")
            if row_id in seen_ids:
                raise ValueError(f"Row {index} in {table_name} duplicates an id.")
            seen_ids.add(row_id)


def validate_analysis_profiles(rows: list[dict[str, Any]]) -> None:
    seen_keys: set[str] = set()
    seen_labels: set[str] = set()

    for index, row in enumerate(rows, start=1):
        try:
            key = normalize_profile_key(str(row["key"]))
        except ValueError as exc:
            raise ValueError(f"Row {index} in analysis_profiles has an invalid key.") from exc
        if key in seen_keys:
            raise ValueError(f"Row {index} in analysis_profiles duplicates a key.")
        seen_keys.add(key)
        row["key"] = key

        label = " ".join(str(row["label"]).strip().split())
        if not label:
            raise ValueError(f"Row {index} in analysis_profiles has a blank label.")
        normalized_label = label.lower()
        if normalized_label in seen_labels:
            raise ValueError(
                f"Row {index} in analysis_profiles duplicates a label ignoring case."
            )
        seen_labels.add(normalized_label)
        row["label"] = label

        category = " ".join(str(row["category"]).strip().split())
        if not category:
            raise ValueError(f"Row {index} in analysis_profiles has a blank category.")
        row["category"] = category

        for field_name in ("exercise_factor", "compound_factor", "back_factor"):
            value = coerce_float(row[field_name], f"Row {index} in analysis_profiles {field_name}")
            if value < 0 or value > 5:
                raise ValueError(
                    f"Row {index} in analysis_profiles has an invalid {field_name}."
                )
            row[field_name] = value

        for field_name in ("is_builtin", "is_active"):
            value = coerce_int(row[field_name], f"Row {index} in analysis_profiles {field_name}")
            if value not in (0, 1):
                raise ValueError(
                    f"Row {index} in analysis_profiles has invalid {field_name}."
                )
            row[field_name] = value

        row["sort_order"] = coerce_int(
            row["sort_order"],
            f"Row {index} in analysis_profiles sort_order",
        )

    if DEFAULT_PROFILE_KEY not in seen_keys:
        raise ValueError("Backup analysis profiles must include accessory.")

    accessory = next(row for row in rows if row["key"] == DEFAULT_PROFILE_KEY)
    if int(accessory["is_active"]) != 1:
        raise ValueError("Accessory analysis profile must be active.")


def validate_exercises(
    rows: list[dict[str, Any]],
    profile_keys: set[str],
) -> None:
    seen_names: set[str] = set()
    seen_orders: set[int] = set()

    for index, row in enumerate(rows, start=1):
        name = " ".join(str(row["name"]).strip().split())
        if not name:
            raise ValueError(f"Row {index} in exercises has a blank name.")
        if len(name) > 120:
            raise ValueError(f"Row {index} in exercises has a name that is too long.")

        normalized_name = name.lower()
        if normalized_name in seen_names:
            raise ValueError(
                f"Row {index} in exercises duplicates a name ignoring case."
            )
        seen_names.add(normalized_name)
        row["name"] = name

        is_active = coerce_int(row["is_active"], f"Row {index} in exercises is_active")
        if is_active not in (0, 1):
            raise ValueError(f"Row {index} in exercises has invalid active state.")
        row["is_active"] = is_active

        sort_order = coerce_int(
            row["sort_order"],
            f"Row {index} in exercises sort_order",
        )
        if sort_order < 0:
            raise ValueError(f"Row {index} in exercises has invalid sort order.")
        if sort_order in seen_orders:
            raise ValueError(f"Row {index} in exercises duplicates sort order.")
        seen_orders.add(sort_order)
        row["sort_order"] = sort_order

        profile_key = str(row["profile_key"] or "").strip()
        if profile_key not in profile_keys:
            raise ValueError(f"Row {index} in exercises has an invalid profile.")
        row["profile_key"] = profile_key


def validate_exercise_weight_options(
    rows: list[dict[str, Any]],
    tables: dict[str, list[dict[str, Any]]],
    *,
    enforce_active_weights: bool,
) -> None:
    exercise_ids = {int(row["id"]) for row in tables["exercises"]}
    active_exercise_ids = {
        int(row["id"])
        for row in tables["exercises"]
        if int(row["is_active"]) == 1
    }
    weights_by_exercise: dict[int, list[float]] = {
        exercise_id: []
        for exercise_id in exercise_ids
    }
    seen_pairs: set[tuple[int, float]] = set()

    for index, row in enumerate(rows, start=1):
        exercise_id = coerce_int(
            row["exercise_id"],
            f"Row {index} in exercise_weight_options exercise_id",
        )
        if exercise_id not in exercise_ids:
            raise ValueError(
                f"Row {index} in exercise_weight_options references an unknown exercise."
            )

        weight = coerce_float(row["weight"], f"Row {index} in exercise_weight_options weight")
        if weight < 0:
            raise ValueError(
                f"Row {index} in exercise_weight_options has an invalid weight."
            )
        row["exercise_id"] = exercise_id
        row["weight"] = round(weight, 4)
        row["sort_order"] = coerce_int(
            row["sort_order"],
            f"Row {index} in exercise_weight_options sort_order",
        )

        pair = (exercise_id, row["weight"])
        if pair in seen_pairs:
            raise ValueError(
                f"Row {index} in exercise_weight_options duplicates a weight."
            )
        seen_pairs.add(pair)
        weights_by_exercise[exercise_id].append(row["weight"])

    if enforce_active_weights:
        for exercise_id in active_exercise_ids:
            if not weights_by_exercise.get(exercise_id):
                raise ValueError(
                    f"Active exercise {exercise_id} must have at least one weight."
                )


def coerce_optional_int(
    value: Any,
    context: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    if value is None:
        return None

    result = coerce_int(value, context)
    if minimum is not None and result < minimum:
        raise ValueError(f"{context} is below the allowed range.")
    if maximum is not None and result > maximum:
        raise ValueError(f"{context} is above the allowed range.")
    return result


def coerce_optional_float(
    value: Any,
    context: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    if value is None:
        return None

    result = coerce_float(value, context)
    if minimum is not None and result < minimum:
        raise ValueError(f"{context} is below the allowed range.")
    if maximum is not None and result > maximum:
        raise ValueError(f"{context} is above the allowed range.")
    return result


def validate_garmin_daily_metrics(rows: list[dict[str, Any]]) -> None:
    seen_dates: set[str] = set()
    for index, row in enumerate(rows, start=1):
        metric_date = str(row["date"]).strip()
        try:
            datetime.fromisoformat(metric_date)
        except ValueError as exc:
            raise ValueError(
                f"Row {index} in garmin_daily_metrics has an invalid date."
            ) from exc
        if metric_date in seen_dates:
            raise ValueError(
                f"Row {index} in garmin_daily_metrics duplicates a date."
            )
        seen_dates.add(metric_date)
        row["date"] = metric_date

        row["resting_heart_rate"] = coerce_optional_int(
            row["resting_heart_rate"],
            f"Row {index} in garmin_daily_metrics resting_heart_rate",
            minimum=20,
            maximum=240,
        )
        row["hrv_ms"] = coerce_optional_float(
            row["hrv_ms"],
            f"Row {index} in garmin_daily_metrics hrv_ms",
            minimum=0,
        )
        row["stress_avg"] = coerce_optional_int(
            row["stress_avg"],
            f"Row {index} in garmin_daily_metrics stress_avg",
            minimum=0,
            maximum=100,
        )
        row["body_battery_start"] = coerce_optional_int(
            row["body_battery_start"],
            f"Row {index} in garmin_daily_metrics body_battery_start",
            minimum=0,
            maximum=100,
        )
        row["body_battery_end"] = coerce_optional_int(
            row["body_battery_end"],
            f"Row {index} in garmin_daily_metrics body_battery_end",
            minimum=0,
            maximum=100,
        )
        row["steps"] = coerce_optional_int(
            row["steps"],
            f"Row {index} in garmin_daily_metrics steps",
            minimum=0,
        )

        synced_at = str(row["synced_at"]).strip()
        try:
            datetime.fromisoformat(synced_at)
        except ValueError as exc:
            raise ValueError(
                f"Row {index} in garmin_daily_metrics has an invalid synced_at."
            ) from exc
        row["synced_at"] = synced_at

        raw_diagnostics = row["raw_diagnostics"]
        if isinstance(raw_diagnostics, str):
            try:
                raw_diagnostics = json.loads(raw_diagnostics)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Row {index} in garmin_daily_metrics has invalid diagnostics."
                ) from exc
        if not isinstance(raw_diagnostics, dict):
            raise ValueError(
                f"Row {index} in garmin_daily_metrics diagnostics must be an object."
            )
        row["raw_diagnostics"] = json.dumps(
            raw_diagnostics,
            sort_keys=True,
            separators=(",", ":"),
        )


def validate_workout_graph(tables: dict[str, list[dict[str, Any]]]) -> None:
    exercise_ids = {int(row["id"]) for row in tables["exercises"]}
    workout_ids = {int(row["id"]) for row in tables["workouts"]}
    workout_exercise_ids = {int(row["id"]) for row in tables["workout_exercises"]}

    for index, row in enumerate(tables["workout_exercises"], start=1):
        workout_id = coerce_int(
            row["workout_id"],
            f"Row {index} in workout_exercises workout_id",
        )
        exercise_id = coerce_int(
            row["exercise_id"],
            f"Row {index} in workout_exercises exercise_id",
        )
        position = coerce_int(row["position"], f"Row {index} in workout_exercises position")
        if workout_id not in workout_ids:
            raise ValueError(
                f"Row {index} in workout_exercises references an unknown workout."
            )
        if exercise_id not in exercise_ids:
            raise ValueError(
                f"Row {index} in workout_exercises references an unknown exercise."
            )
        if position <= 0:
            raise ValueError(f"Row {index} in workout_exercises has invalid position.")
        row["workout_id"] = workout_id
        row["exercise_id"] = exercise_id
        row["position"] = position

    for index, row in enumerate(tables["set_entries"], start=1):
        workout_exercise_id = coerce_int(
            row["workout_exercise_id"],
            f"Row {index} in set_entries workout_exercise_id",
        )
        if workout_exercise_id not in workout_exercise_ids:
            raise ValueError(
                f"Row {index} in set_entries references an unknown workout exercise."
            )

        set_number = coerce_int(row["set_number"], f"Row {index} in set_entries set_number")
        reps = coerce_int(row["reps"], f"Row {index} in set_entries reps")
        weight = coerce_float(row["weight"], f"Row {index} in set_entries weight")
        if set_number <= 0:
            raise ValueError(f"Row {index} in set_entries has invalid set number.")
        if reps <= 0 or reps > 100:
            raise ValueError(f"Row {index} in set_entries has invalid reps.")
        if weight < 0:
            raise ValueError(f"Row {index} in set_entries has invalid weight.")
        row["workout_exercise_id"] = workout_exercise_id
        row["set_number"] = set_number
        row["reps"] = reps
        row["weight"] = weight


def reset_sqlite_sequences(conn: sqlite3.Connection) -> None:
    logger.debug("db.sqlite_sequence.reset.start")
    placeholders = ", ".join("?" for _ in BACKUP_SEQUENCE_TABLES)
    conn.execute(
        f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
        BACKUP_SEQUENCE_TABLES,
    )

    for table_name in BACKUP_SEQUENCE_TABLES:
        max_id = conn.execute(
            f"SELECT COALESCE(MAX(id), 0) FROM {table_name}"
        ).fetchone()[0]

        if max_id:
            conn.execute(
                "INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)",
                (table_name, max_id),
            )

    logger.debug("db.sqlite_sequence.reset.done")


def insert_analysis_profile_rows(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    columns = (*ANALYSIS_PROFILE_BACKUP_COLUMNS, "created_at", "updated_at")
    column_sql = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f"INSERT INTO analysis_profiles ({column_sql}) VALUES ({placeholders})"

    for row in rows:
        values = [row[column] for column in ANALYSIS_PROFILE_BACKUP_COLUMNS]
        conn.execute(insert_sql, (*values, now, now))


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
            if table_name == "analysis_profiles":
                insert_analysis_profile_rows(conn, tables[table_name])
                continue

            column_sql = ", ".join(columns)
            placeholders = ", ".join("?" for _ in columns)
            insert_sql = (
                f"INSERT INTO {table_name} ({column_sql}) "
                f"VALUES ({placeholders})"
            )

            for row in tables[table_name]:
                conn.execute(insert_sql, tuple(row[column] for column in columns))

        reset_sqlite_sequences(conn)
        if schema_version in (3, 4, BACKUP_SCHEMA_VERSION):
            set_metadata(conn, EXERCISE_SETTINGS_WEIGHT_MIGRATION_KEY, "1")
        else:
            initialize_exercise_settings(conn, force_weight_migration=True)

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

        placeholders = ", ".join("?" for _ in BACKUP_SEQUENCE_TABLES)
        conn.execute(
            f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
            BACKUP_SEQUENCE_TABLES,
        )

        ensure_default_analysis_profiles(conn)
        seed_default_exercises(conn)
        initialize_exercise_settings(conn, force_weight_migration=True)

        logger.warning("db.reset.done")
