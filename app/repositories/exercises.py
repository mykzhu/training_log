import math
import sqlite3
from typing import Any

from app.db import get_db
from app.services.analysis_service import profile_key_for_exercise_name


def normalize_exercise_name(name: str) -> str:
    return " ".join(name.strip().split())


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
            WHERE name = ?
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
    profile_key: str = "accessory",
    weights: list[float] | None = None,
) -> tuple[dict[str, Any], bool]:
    normalized_name = normalize_exercise_name(name)
    normalized_weights = normalize_weights(weights or [])
    resolved_profile_key = profile_key or profile_key_for_exercise_name(normalized_name)

    with get_db() as conn:
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
    updated_profile_key = current["profile_key"] if profile_key is None else profile_key

    with get_db() as conn:
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
            "SELECT id FROM exercises WHERE id = ?",
            (exercise_id,),
        ).fetchone()
        if exercise is None:
            raise KeyError("Exercise not found.")

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
