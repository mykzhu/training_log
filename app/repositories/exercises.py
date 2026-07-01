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


def normalize_exercise_name(name: str) -> str:
    return " ".join(name.strip().split())


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
            SELECT id, name, is_active, sort_order, profile_key
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
            SELECT id, name, is_active, sort_order, profile_key
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
            SELECT id, name, is_active, sort_order, profile_key
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
) -> tuple[dict[str, Any], bool]:
    normalized_name = normalize_exercise_name(name)
    normalized_weights = normalize_weights(weights or [])

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
                    profile_key
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    normalized_name,
                    1 if is_active else 0,
                    next_sort_order(conn),
                    resolved_profile_key,
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
) -> dict[str, Any] | None:
    current = get_exercise(exercise_id, include_weights=False)
    if current is None:
        return None

    updated_name = current["name"] if name is None else normalize_exercise_name(name)
    updated_active = current["is_active"] if is_active is None else is_active
    updated_profile_key = current["profile_key"]

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
                    profile_key = ?
                WHERE id = ?
                """,
                (
                    updated_name,
                    1 if updated_active else 0,
                    updated_profile_key,
                    exercise_id,
                ),
            )
        except sqlite3.IntegrityError:
            raise

        if cursor.rowcount == 0:
            return None

    return get_exercise(exercise_id)


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
