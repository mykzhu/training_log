import math
import sqlite3
from typing import Any

from app.db import get_db
from app.repositories.analysis_profiles import active_profile_exists
from app.services.default_analysis_profiles import profile_key_for_exercise_name


class ActiveExerciseWeightError(ValueError):
    pass


class InactiveExerciseProfileError(ValueError):
    pass


class ExerciseInUseError(ValueError):
    pass


EXERCISE_OPTION_SETTING_DEFAULTS = {
    "default_weight": 0.0,
    "min_weight": 0.0,
    "max_weight": 200.0,
    "weight_step": 2.5,
    "default_reps": 10,
    "min_reps": 1,
    "max_reps": 50,
    "reps_step": 1,
}
MEASUREMENT_TYPE_DEFAULT = "weighted_reps"
VALID_MEASUREMENT_TYPES = {
    "weighted_reps",
    "bodyweight_reps",
    "loaded_carry_time",
    "loaded_carry_distance",
    "reps_only",
}
REPS_UNIT_DEFAULTS = {
    "weighted_reps": "reps",
    "bodyweight_reps": "reps",
    "loaded_carry_time": "sec",
    "loaded_carry_distance": "m",
    "reps_only": "reps",
}


def normalize_exercise_name(name: str) -> str:
    return " ".join(name.strip().split())


def default_measurement_settings_for_name(name: str) -> dict[str, str]:
    normalized_name = normalize_exercise_name(name).lower()
    if "carry" in normalized_name:
        return {"measurement_type": "loaded_carry_time", "reps_unit": "sec"}
    if "crunch" in normalized_name:
        return {"measurement_type": "bodyweight_reps", "reps_unit": "reps"}
    return {
        "measurement_type": MEASUREMENT_TYPE_DEFAULT,
        "reps_unit": REPS_UNIT_DEFAULTS[MEASUREMENT_TYPE_DEFAULT],
    }


def normalize_measurement_settings(
    *,
    measurement_type: str | None = None,
    reps_unit: str | None = None,
    exercise_name: str | None = None,
) -> dict[str, str]:
    defaults = (
        default_measurement_settings_for_name(exercise_name)
        if exercise_name
        else {
            "measurement_type": MEASUREMENT_TYPE_DEFAULT,
            "reps_unit": REPS_UNIT_DEFAULTS[MEASUREMENT_TYPE_DEFAULT],
        }
    )
    normalized_type = str(
        measurement_type or defaults["measurement_type"]
    ).strip()
    if normalized_type not in VALID_MEASUREMENT_TYPES:
        raise ValueError("Invalid measurement type.")

    normalized_unit = str(
        reps_unit or REPS_UNIT_DEFAULTS.get(normalized_type, "reps")
    ).strip()
    if not normalized_unit:
        normalized_unit = REPS_UNIT_DEFAULTS.get(normalized_type, "reps")
    if len(normalized_unit) > 16:
        raise ValueError("Reps unit is too long.")

    return {
        "measurement_type": normalized_type,
        "reps_unit": normalized_unit,
    }


def derive_set_metrics(
    sets: list[Any],
    measurement_type: str,
) -> dict[str, float | int]:
    weighted_volume = sum(float(s["weight"]) * int(s["reps"]) for s in sets)
    total_reps = sum(int(s["reps"]) for s in sets)
    if measurement_type == "weighted_reps":
        total_volume_kg = weighted_volume
        bodyweight_reps = 0
        duration_seconds = 0
        distance_m = 0
    elif measurement_type in {"bodyweight_reps", "reps_only"}:
        total_volume_kg = 0.0
        bodyweight_reps = total_reps
        duration_seconds = 0
        distance_m = 0
    elif measurement_type == "loaded_carry_time":
        total_volume_kg = 0.0
        bodyweight_reps = 0
        duration_seconds = total_reps
        distance_m = 0
    elif measurement_type == "loaded_carry_distance":
        total_volume_kg = 0.0
        bodyweight_reps = 0
        duration_seconds = 0
        distance_m = total_reps
    else:
        total_volume_kg = weighted_volume
        bodyweight_reps = 0
        duration_seconds = 0
        distance_m = 0

    return {
        "total_volume_kg": total_volume_kg,
        "bodyweight_reps": bodyweight_reps,
        "duration_seconds": duration_seconds,
        "distance_m": distance_m,
    }


def resolve_profile_key(
    conn: sqlite3.Connection,
    profile_key: str | None,
    exercise_name: str,
) -> str:
    if profile_key is not None and profile_key.strip():
        resolved = profile_key.strip()
        if not active_profile_exists(conn, resolved):
            raise InactiveExerciseProfileError("Exercise profile is not active.")
        return resolved

    inferred = profile_key_for_exercise_name(exercise_name)
    if active_profile_exists(conn, inferred):
        return inferred
    return "accessory"


def normalize_weights(weights: list[float]) -> list[float]:
    normalized: list[float] = []

    for weight in weights:
        value = float(weight)
        if not math.isfinite(value):
            raise ValueError("Weight must be finite.")
        if value < 0:
            raise ValueError("Weight cannot be negative.")
        normalized.append(round(value, 4))

    return sorted(set(normalized))


def value_or_default(value: Any, default: float | int) -> Any:
    return default if value is None else value


def get_float_options(
    min_value: float | None,
    max_value: float | None,
    step: float | None,
    extra_values: list[float] | None = None,
) -> list[float]:
    start = float(min_value if min_value is not None else 0)
    end = float(max_value if max_value is not None else 200)
    increment = float(step if step is not None else 2.5)

    if start < 0:
        start = 0
    if increment <= 0 or not math.isfinite(increment):
        increment = 2.5
    if end < start:
        end = start

    options: set[float] = set()
    value = start
    while value <= end + 0.0001:
        options.add(round(value, 4))
        value += increment
    options.add(round(end, 4))

    for extra_value in extra_values or []:
        value = float(extra_value)
        if math.isfinite(value) and value >= 0:
            options.add(round(value, 4))

    return sorted(options)


def get_int_options(
    min_value: int | None,
    max_value: int | None,
    step: int | None,
    extra_values: list[int] | None = None,
) -> list[int]:
    start = int(min_value if min_value is not None else 1)
    end = int(max_value if max_value is not None else 50)
    increment = int(step if step is not None else 1)

    if start < 1:
        start = 1
    if increment <= 0:
        increment = 1
    if end < start:
        end = start

    options = {start}
    first_step_value = increment
    if first_step_value < start:
        first_step_value = ((start + increment - 1) // increment) * increment
    options.update(range(first_step_value, end + 1, increment))
    options.add(end)
    for extra_value in extra_values or []:
        value = int(extra_value)
        if value > 0:
            options.add(value)

    return sorted(options)


def normalize_exercise_option_settings(
    *,
    default_weight: float | None = None,
    min_weight: float | None = None,
    max_weight: float | None = None,
    weight_step: float | None = None,
    default_reps: int | None = None,
    min_reps: int | None = None,
    max_reps: int | None = None,
    reps_step: int | None = None,
) -> dict[str, float | int]:
    normalized_min_weight = float(
        EXERCISE_OPTION_SETTING_DEFAULTS["min_weight"]
        if min_weight is None
        else min_weight
    )
    normalized_max_weight = float(
        EXERCISE_OPTION_SETTING_DEFAULTS["max_weight"]
        if max_weight is None
        else max_weight
    )
    normalized_weight_step = float(
        EXERCISE_OPTION_SETTING_DEFAULTS["weight_step"]
        if weight_step is None
        else weight_step
    )
    normalized_default_weight = float(
        EXERCISE_OPTION_SETTING_DEFAULTS["default_weight"]
        if default_weight is None
        else default_weight
    )

    if not math.isfinite(normalized_min_weight) or normalized_min_weight < 0:
        normalized_min_weight = 0
    if not math.isfinite(normalized_max_weight):
        normalized_max_weight = normalized_min_weight
    if not math.isfinite(normalized_weight_step) or normalized_weight_step <= 0:
        normalized_weight_step = 2.5
    if not math.isfinite(normalized_default_weight):
        normalized_default_weight = EXERCISE_OPTION_SETTING_DEFAULTS["default_weight"]
    if normalized_default_weight < 0:
        normalized_default_weight = 0
    if normalized_default_weight < normalized_min_weight:
        normalized_min_weight = normalized_default_weight
    if normalized_max_weight < normalized_min_weight:
        normalized_max_weight = normalized_min_weight
    if normalized_default_weight > normalized_max_weight:
        normalized_max_weight = normalized_default_weight

    normalized_min_reps = int(
        EXERCISE_OPTION_SETTING_DEFAULTS["min_reps"]
        if min_reps is None
        else min_reps
    )
    normalized_max_reps = int(
        EXERCISE_OPTION_SETTING_DEFAULTS["max_reps"]
        if max_reps is None
        else max_reps
    )
    normalized_reps_step = int(
        EXERCISE_OPTION_SETTING_DEFAULTS["reps_step"]
        if reps_step is None
        else reps_step
    )
    normalized_default_reps = int(
        EXERCISE_OPTION_SETTING_DEFAULTS["default_reps"]
        if default_reps is None
        else default_reps
    )

    if normalized_min_reps < 1:
        normalized_min_reps = 1
    if normalized_reps_step <= 0:
        normalized_reps_step = 1
    if normalized_default_reps < 1:
        normalized_default_reps = 1
    if normalized_default_reps < normalized_min_reps:
        normalized_min_reps = normalized_default_reps
    if normalized_max_reps < normalized_min_reps:
        normalized_max_reps = normalized_min_reps
    if normalized_default_reps > normalized_max_reps:
        normalized_max_reps = normalized_default_reps

    return {
        "default_weight": round(normalized_default_weight, 4),
        "min_weight": round(normalized_min_weight, 4),
        "max_weight": round(normalized_max_weight, 4),
        "weight_step": round(normalized_weight_step, 4),
        "default_reps": normalized_default_reps,
        "min_reps": normalized_min_reps,
        "max_reps": normalized_max_reps,
        "reps_step": normalized_reps_step,
    }


def get_weight_options_by_exercise_ids(
    exercise_ids: list[int],
) -> dict[int, list[float]]:
    unique_ids = sorted({int(exercise_id) for exercise_id in exercise_ids})
    if not unique_ids:
        return {}

    placeholders = ", ".join("?" for _ in unique_ids)
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT exercise_id, weight
            FROM exercise_weight_options
            WHERE exercise_id IN ({placeholders})
            ORDER BY exercise_id ASC, sort_order ASC, weight ASC
            """,
            unique_ids,
        ).fetchall()

    weights_by_exercise = {exercise_id: [] for exercise_id in unique_ids}
    for row in rows:
        weights_by_exercise[int(row["exercise_id"])].append(float(row["weight"]))

    return weights_by_exercise


def hydrate_exercises(
    rows: list[sqlite3.Row],
    *,
    include_weights: bool = True,
) -> list[dict[str, Any]]:
    exercises = [
        {
            "id": int(row["id"]),
            "name": row["name"],
            "is_active": bool(row["is_active"]),
            "sort_order": int(row["sort_order"]),
            "profile_key": row["profile_key"] or "accessory",
            "measurement_type": row["measurement_type"] or MEASUREMENT_TYPE_DEFAULT,
            "reps_unit": (
                row["reps_unit"]
                or REPS_UNIT_DEFAULTS[MEASUREMENT_TYPE_DEFAULT]
            ),
            "default_weight": float(value_or_default(row["default_weight"], 0)),
            "min_weight": float(value_or_default(row["min_weight"], 0)),
            "max_weight": float(value_or_default(row["max_weight"], 200)),
            "weight_step": float(value_or_default(row["weight_step"], 2.5)),
            "default_reps": int(value_or_default(row["default_reps"], 10)),
            "min_reps": int(value_or_default(row["min_reps"], 1)),
            "max_reps": int(value_or_default(row["max_reps"], 50)),
            "reps_step": int(value_or_default(row["reps_step"], 1)),
            "weights": [],
        }
        for row in rows
    ]

    if include_weights:
        weights_by_exercise = get_weight_options_by_exercise_ids(
            [exercise["id"] for exercise in exercises]
        )
        for exercise in exercises:
            exercise["weights"] = weights_by_exercise.get(exercise["id"], [])

    return exercises


def list_exercises(
    *,
    include_inactive: bool = False,
    include_weights: bool = True,
) -> list[dict[str, Any]]:
    where_sql = "" if include_inactive else "WHERE is_active = 1"

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT
                id,
                name,
                is_active,
                sort_order,
                profile_key,
                measurement_type,
                reps_unit,
                default_weight,
                min_weight,
                max_weight,
                weight_step,
                default_reps,
                min_reps,
                max_reps,
                reps_step
            FROM exercises
            {where_sql}
            ORDER BY sort_order ASC, name COLLATE NOCASE ASC, id ASC
            """
        ).fetchall()

    return hydrate_exercises(rows, include_weights=include_weights)


def get_exercise(
    exercise_id: int,
    *,
    include_weights: bool = True,
) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                id,
                name,
                is_active,
                sort_order,
                profile_key,
                measurement_type,
                reps_unit,
                default_weight,
                min_weight,
                max_weight,
                weight_step,
                default_reps,
                min_reps,
                max_reps,
                reps_step
            FROM exercises
            WHERE id = ?
            """,
            (exercise_id,),
        ).fetchone()

    if row is None:
        return None

    return hydrate_exercises([row], include_weights=include_weights)[0]


def get_exercise_by_name(name: str) -> dict[str, Any] | None:
    normalized_name = normalize_exercise_name(name)

    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                id,
                name,
                is_active,
                sort_order,
                profile_key,
                measurement_type,
                reps_unit,
                default_weight,
                min_weight,
                max_weight,
                weight_step,
                default_reps,
                min_reps,
                max_reps,
                reps_step
            FROM exercises
            WHERE lower(name) = lower(?)
            """,
            (normalized_name,),
        ).fetchone()

    if row is None:
        return None

    return hydrate_exercises([row])[0]


def next_sort_order(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 10 FROM exercises"
        ).fetchone()[0]
    )


def create_exercise(
    name: str,
    *,
    is_active: bool = True,
    profile_key: str | None = None,
    weights: list[float] | None = None,
    option_settings: dict[str, float | int | None] | None = None,
    measurement_settings: dict[str, str | None] | None = None,
) -> tuple[dict[str, Any], bool]:
    normalized_name = normalize_exercise_name(name)
    normalized_weights = normalize_weights(weights or [])
    settings = normalize_exercise_option_settings(**(option_settings or {}))
    measurement = normalize_measurement_settings(
        **(measurement_settings or {}),
        exercise_name=normalized_name,
    )

    if is_active and not normalized_weights:
        raise ActiveExerciseWeightError("Active exercise must have at least one weight.")

    with get_db() as conn:
        resolved_profile_key = resolve_profile_key(conn, profile_key, normalized_name)
        existing = conn.execute(
            """
            SELECT id
            FROM exercises
            WHERE lower(name) = lower(?)
            """,
            (normalized_name,),
        ).fetchone()
        if existing is not None:
            raise sqlite3.IntegrityError("Exercise name already exists.")

        try:
            cursor = conn.execute(
                """
                INSERT INTO exercises (
                    name,
                    is_active,
                    sort_order,
                    profile_key,
                    measurement_type,
                    reps_unit,
                    default_weight,
                    min_weight,
                    max_weight,
                    weight_step,
                    default_reps,
                    min_reps,
                    max_reps,
                    reps_step
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_name,
                    1 if is_active else 0,
                    next_sort_order(conn),
                    resolved_profile_key,
                    measurement["measurement_type"],
                    measurement["reps_unit"],
                    settings["default_weight"],
                    settings["min_weight"],
                    settings["max_weight"],
                    settings["weight_step"],
                    settings["default_reps"],
                    settings["min_reps"],
                    settings["max_reps"],
                    settings["reps_step"],
                ),
            )
        except sqlite3.IntegrityError:
            raise

        exercise_id = int(cursor.lastrowid)
        for index, weight in enumerate(normalized_weights, start=1):
            conn.execute(
                """
                INSERT INTO exercise_weight_options (
                    exercise_id,
                    weight,
                    sort_order
                )
                VALUES (?, ?, ?)
                """,
                (exercise_id, weight, index * 10),
            )

    exercise = get_exercise(exercise_id)
    if exercise is None:
        raise RuntimeError("Created exercise could not be loaded.")

    return exercise, True


def update_exercise(
    exercise_id: int,
    *,
    name: str | None = None,
    is_active: bool | None = None,
    profile_key: str | None = None,
    option_settings: dict[str, float | int | None] | None = None,
    measurement_settings: dict[str, str | None] | None = None,
) -> dict[str, Any] | None:
    current = get_exercise(exercise_id, include_weights=False)
    if current is None:
        return None

    updated_name = current["name"] if name is None else normalize_exercise_name(name)
    updated_active = current["is_active"] if is_active is None else is_active
    updated_profile_key = current["profile_key"]
    settings = None
    if option_settings is not None:
        current_settings = {
            key: current[key]
            for key in EXERCISE_OPTION_SETTING_DEFAULTS
        }
        current_settings.update(option_settings)
        settings = normalize_exercise_option_settings(**current_settings)
    measurement = None
    if measurement_settings is not None:
        current_measurement = {
            "measurement_type": current["measurement_type"],
            "reps_unit": current["reps_unit"],
        }
        current_measurement.update(measurement_settings)
        measurement = normalize_measurement_settings(**current_measurement)

    with get_db() as conn:
        if profile_key is not None:
            updated_profile_key = resolve_profile_key(conn, profile_key, updated_name)

        existing = conn.execute(
            """
            SELECT id
            FROM exercises
            WHERE lower(name) = lower(?)
              AND id != ?
            """,
            (updated_name, exercise_id),
        ).fetchone()
        if existing is not None:
            raise sqlite3.IntegrityError("Exercise name already exists.")

        if updated_active:
            weight_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM exercise_weight_options
                WHERE exercise_id = ?
                """,
                (exercise_id,),
            ).fetchone()[0]
            if int(weight_count) == 0:
                raise ActiveExerciseWeightError(
                    "Active exercise must have at least one weight."
                )

        try:
            cursor = conn.execute(
                """
                UPDATE exercises
                SET name = ?,
                    is_active = ?,
                    profile_key = ?,
                    measurement_type = COALESCE(?, measurement_type),
                    reps_unit = COALESCE(?, reps_unit),
                    default_weight = COALESCE(?, default_weight),
                    min_weight = COALESCE(?, min_weight),
                    max_weight = COALESCE(?, max_weight),
                    weight_step = COALESCE(?, weight_step),
                    default_reps = COALESCE(?, default_reps),
                    min_reps = COALESCE(?, min_reps),
                    max_reps = COALESCE(?, max_reps),
                    reps_step = COALESCE(?, reps_step)
                WHERE id = ?
                """,
                (
                    updated_name,
                    1 if updated_active else 0,
                    updated_profile_key,
                    None if measurement is None else measurement["measurement_type"],
                    None if measurement is None else measurement["reps_unit"],
                    None if settings is None else settings["default_weight"],
                    None if settings is None else settings["min_weight"],
                    None if settings is None else settings["max_weight"],
                    None if settings is None else settings["weight_step"],
                    None if settings is None else settings["default_reps"],
                    None if settings is None else settings["min_reps"],
                    None if settings is None else settings["max_reps"],
                    None if settings is None else settings["reps_step"],
                    exercise_id,
                ),
            )
        except sqlite3.IntegrityError:
            raise

        if cursor.rowcount == 0:
            return None

    return get_exercise(exercise_id)


def get_exercise_usage_counts(
    conn: sqlite3.Connection,
    exercise_id: int,
) -> dict[str, int]:
    workout_count = conn.execute(
        """
        SELECT COUNT(DISTINCT workout_id)
        FROM workout_exercises
        WHERE exercise_id = ?
        """,
        (exercise_id,),
    ).fetchone()[0]
    set_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM workout_exercises we
        JOIN set_entries se ON se.workout_exercise_id = we.id
        WHERE we.exercise_id = ?
        """,
        (exercise_id,),
    ).fetchone()[0]
    draft_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM active_draft_exercises
        WHERE exercise_id = ?
        """,
        (exercise_id,),
    ).fetchone()[0]

    return {
        "workout_count": int(workout_count),
        "set_count": int(set_count),
        "draft_count": int(draft_count),
    }


def delete_exercise_by_id(exercise_id: int) -> dict[str, Any] | None:
    with get_db() as conn:
        exercise = conn.execute(
            """
            SELECT id, name, is_active, sort_order, profile_key
            FROM exercises
            WHERE id = ?
            """,
            (exercise_id,),
        ).fetchone()

        if exercise is None:
            return None

        usage = get_exercise_usage_counts(conn, exercise_id)
        if usage["workout_count"] > 0 or usage["draft_count"] > 0:
            raise ExerciseInUseError(
                "Exercise has workout history or active draft usage and cannot be deleted. Deactivate it instead."
            )

        conn.execute(
            "DELETE FROM exercises WHERE id = ?",
            (exercise_id,),
        )

    deleted = {
        "id": int(exercise["id"]),
        "name": str(exercise["name"]),
        "is_active": bool(exercise["is_active"]),
        "sort_order": int(exercise["sort_order"]),
        "profile_key": exercise["profile_key"] or "accessory",
        "usage": usage,
    }
    return deleted


def get_option_settings_by_exercise_ids(
    exercise_ids: list[int],
) -> dict[int, dict[str, float | int]]:
    unique_ids = sorted({int(exercise_id) for exercise_id in exercise_ids})
    if not unique_ids:
        return {}

    placeholders = ", ".join("?" for _ in unique_ids)
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT
                id,
                default_weight,
                min_weight,
                max_weight,
                weight_step,
                default_reps,
                min_reps,
                max_reps,
                reps_step
            FROM exercises
            WHERE id IN ({placeholders})
            """,
            unique_ids,
        ).fetchall()

    return {
        int(row["id"]): normalize_exercise_option_settings(
            default_weight=float(value_or_default(row["default_weight"], 0)),
            min_weight=float(value_or_default(row["min_weight"], 0)),
            max_weight=float(value_or_default(row["max_weight"], 200)),
            weight_step=float(value_or_default(row["weight_step"], 2.5)),
            default_reps=int(value_or_default(row["default_reps"], 10)),
            min_reps=int(value_or_default(row["min_reps"], 1)),
            max_reps=int(value_or_default(row["max_reps"], 50)),
            reps_step=int(value_or_default(row["reps_step"], 1)),
        )
        for row in rows
    }


def get_measurement_settings_by_exercise_ids(
    exercise_ids: list[int],
) -> dict[int, dict[str, str]]:
    unique_ids = sorted({int(exercise_id) for exercise_id in exercise_ids})
    if not unique_ids:
        return {}

    placeholders = ", ".join("?" for _ in unique_ids)
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT id, name, measurement_type, reps_unit
            FROM exercises
            WHERE id IN ({placeholders})
            """,
            unique_ids,
        ).fetchall()

    return {
        int(row["id"]): normalize_measurement_settings(
            measurement_type=row["measurement_type"],
            reps_unit=row["reps_unit"],
            exercise_name=row["name"],
        )
        for row in rows
    }


def update_exercise_name(exercise_id: int, name: str) -> dict[str, Any] | None:
    return update_exercise(exercise_id, name=name)


def replace_exercise_weights(
    exercise_id: int,
    weights: list[float],
) -> list[float]:
    normalized_weights = normalize_weights(weights)

    with get_db() as conn:
        exercise = conn.execute(
            "SELECT id, is_active FROM exercises WHERE id = ?",
            (exercise_id,),
        ).fetchone()
        if exercise is None:
            raise KeyError("Exercise not found.")
        if bool(exercise["is_active"]) and not normalized_weights:
            raise ActiveExerciseWeightError(
                "Active exercise must have at least one weight."
            )

        conn.execute(
            "DELETE FROM exercise_weight_options WHERE exercise_id = ?",
            (exercise_id,),
        )
        for index, weight in enumerate(normalized_weights, start=1):
            conn.execute(
                """
                INSERT INTO exercise_weight_options (
                    exercise_id,
                    weight,
                    sort_order
                )
                VALUES (?, ?, ?)
                """,
                (exercise_id, weight, index * 10),
            )

    return normalized_weights


def reorder_exercises(exercise_ids: list[int]) -> list[dict[str, Any]]:
    if len(exercise_ids) != len(set(exercise_ids)):
        raise ValueError("Exercise order contains duplicate IDs.")

    with get_db() as conn:
        existing_ids = [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM exercises ORDER BY id ASC"
            ).fetchall()
        ]

        if set(exercise_ids) != set(existing_ids):
            raise ValueError("Exercise order must include every exercise.")

        for index, exercise_id in enumerate(exercise_ids, start=1):
            conn.execute(
                """
                UPDATE exercises
                SET sort_order = ?
                WHERE id = ?
                """,
                (index * 10, int(exercise_id)),
            )

    return list_exercises(include_inactive=True)
