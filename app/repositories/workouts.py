import sqlite3
from typing import Any

from app.db import get_db
from app.repositories.exercises import (
    build_effective_weight_options,
    derive_set_metrics,
    get_int_options,
    get_weight_options_by_exercise_ids,
    normalize_measurement_settings,
    value_or_default,
)

MAX_NUMBERING_RETRIES = 2


class NumberingConflictError(RuntimeError):
    pass


def _begin_immediate(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")


def _is_unique_constraint_error(
    exc: sqlite3.IntegrityError,
    columns: tuple[str, ...],
) -> bool:
    message = str(exc).lower()
    return (
        "unique constraint failed" in message
        and all(column.lower() in message for column in columns)
    )


def list_recent_workouts(limit: int = 30) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM workouts
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_workout(workout_id: int) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM workouts
            WHERE id = ?
            """,
            (workout_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def update_workout(
    workout_id: int,
    *,
    workout_date: str,
    created_at: str,
    session_rpe: int | None,
    lower_back_pain: int | None,
    duration_seconds: int | None,
) -> dict[str, Any] | None:
    with get_db() as conn:
        cursor = conn.execute(
            """
            UPDATE workouts
            SET workout_date = ?,
                created_at = ?,
                session_rpe = ?,
                lower_back_pain = ?,
                duration_seconds = ?
            WHERE id = ?
            """,
            (
                workout_date,
                created_at,
                session_rpe,
                lower_back_pain,
                duration_seconds,
                workout_id,
            ),
        )

    if cursor.rowcount == 0:
        return None

    return get_workout(workout_id)


def delete_workout(workout_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.execute(
            """
            DELETE FROM workouts
            WHERE id = ?
            """,
            (workout_id,),
        )

    return cursor.rowcount > 0


def get_workout_exercise(workout_exercise_id: int) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                we.id,
                we.workout_id,
                we.exercise_id,
                we.position,
                e.name AS exercise_name,
                e.profile_key
            FROM workout_exercises we
            JOIN exercises e ON e.id = we.exercise_id
            WHERE we.id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def add_workout_exercise(workout_id: int, exercise_id: int) -> int:
    for attempt in range(MAX_NUMBERING_RETRIES + 1):
        try:
            with get_db() as conn:
                _begin_immediate(conn)
                next_position = conn.execute(
                    """
                    SELECT COALESCE(MAX(position), 0) + 1
                    FROM workout_exercises
                    WHERE workout_id = ?
                    """,
                    (workout_id,),
                ).fetchone()[0]

                cursor = conn.execute(
                    """
                    INSERT INTO workout_exercises (
                        workout_id,
                        exercise_id,
                        position,
                        measurement_type,
                        reps_unit
                    )
                    SELECT
                        ?,
                        e.id,
                        ?,
                        COALESCE(e.measurement_type, 'weighted_reps'),
                        COALESCE(e.reps_unit, 'reps')
                    FROM exercises e
                    WHERE e.id = ?
                    """,
                    (workout_id, next_position, exercise_id),
                )
                if cursor.rowcount == 0:
                    raise sqlite3.IntegrityError("Exercise does not exist.")

                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            if not _is_unique_constraint_error(
                exc,
                ("workout_exercises.workout_id", "workout_exercises.position"),
            ):
                raise
            if attempt >= MAX_NUMBERING_RETRIES:
                raise NumberingConflictError(
                    "Could not assign a unique exercise position."
                ) from exc

    raise NumberingConflictError("Could not assign a unique exercise position.")


def delete_workout_exercise(
    workout_id: int,
    workout_exercise_id: int,
) -> bool:
    with get_db() as conn:
        _begin_immediate(conn)
        cursor = conn.execute(
            """
            DELETE FROM workout_exercises
            WHERE id = ?
              AND workout_id = ?
            """,
            (workout_exercise_id, workout_id),
        )
        if cursor.rowcount == 0:
            return False

        renumber_workout_exercises(conn, workout_id)

    return True


def get_previous_set_for_exercise(
    exercise_id: int,
    current_workout_id: int | None = None,
    *,
    as_of_created_at: str | None = None,
    as_of_workout_id: int | None = None,
) -> sqlite3.Row | None:
    if as_of_workout_id is None and current_workout_id not in (None, 0):
        as_of_workout_id = current_workout_id

    if as_of_created_at is None and as_of_workout_id is not None:
        with get_db() as conn:
            workout = conn.execute(
                """
                SELECT created_at
                FROM workouts
                WHERE id = ?
                """,
                (as_of_workout_id,),
            ).fetchone()

        if workout is not None:
            as_of_created_at = str(workout["created_at"])

    workout_filter = ""
    params: list[Any] = [exercise_id]

    if as_of_created_at is not None and as_of_workout_id is not None:
        workout_filter = """
              AND (
                    w.created_at < ?
                    OR (w.created_at = ? AND w.id < ?)
              )
        """
        params.extend([as_of_created_at, as_of_created_at, as_of_workout_id])
    elif as_of_created_at is not None:
        workout_filter = "AND w.created_at < ?"
        params.append(as_of_created_at)
    elif current_workout_id not in (None, 0):
        workout_filter = "AND w.id != ?"
        params.append(current_workout_id)

    with get_db() as conn:
        return conn.execute(
            f"""
            SELECT se.weight, se.reps
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            JOIN workouts w ON w.id = we.workout_id
            WHERE we.exercise_id = ?
              {workout_filter}
            ORDER BY w.created_at DESC, w.id DESC, se.set_number DESC, se.id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()


def renumber_sets(conn: sqlite3.Connection, workout_exercise_id: int) -> None:
    sets = conn.execute(
        """
        SELECT id
        FROM set_entries
        WHERE workout_exercise_id = ?
        ORDER BY set_number ASC, id ASC
        """,
        (workout_exercise_id,),
    ).fetchall()

    for index, set_row in enumerate(sets, start=1):
        conn.execute(
            """
            UPDATE set_entries
            SET set_number = ?
            WHERE id = ?
            """,
            (index, set_row["id"]),
        )


def renumber_workout_exercises(conn: sqlite3.Connection, workout_id: int) -> None:
    workout_exercises = conn.execute(
        """
        SELECT id
        FROM workout_exercises
        WHERE workout_id = ?
        ORDER BY position ASC, id ASC
        """,
        (workout_id,),
    ).fetchall()

    for index, row in enumerate(workout_exercises, start=1):
        conn.execute(
            """
            UPDATE workout_exercises
            SET position = ?
            WHERE id = ?
            """,
            (-index, row["id"]),
        )

    for index, row in enumerate(workout_exercises, start=1):
        conn.execute(
            """
            UPDATE workout_exercises
            SET position = ?
            WHERE id = ?
            """,
            (index, row["id"]),
        )


def get_set_entry(set_id: int) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                se.id,
                se.workout_exercise_id,
                se.set_number,
                se.weight,
                se.reps,
                se.created_at,
                we.workout_id
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            WHERE se.id = ?
            """,
            (set_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def add_set_to_workout_exercise(
    workout_exercise_id: int,
    *,
    weight: float,
    reps: int,
    created_at: str,
) -> dict[str, Any] | None:
    for attempt in range(MAX_NUMBERING_RETRIES + 1):
        try:
            with get_db() as conn:
                _begin_immediate(conn)
                workout_exercise = conn.execute(
                    """
                    SELECT id
                    FROM workout_exercises
                    WHERE id = ?
                    """,
                    (workout_exercise_id,),
                ).fetchone()

                if workout_exercise is None:
                    return None

                next_set_number = conn.execute(
                    """
                    SELECT COALESCE(MAX(set_number), 0) + 1
                    FROM set_entries
                    WHERE workout_exercise_id = ?
                    """,
                    (workout_exercise_id,),
                ).fetchone()[0]

                cursor = conn.execute(
                    """
                    INSERT INTO set_entries (
                        workout_exercise_id,
                        set_number,
                        weight,
                        reps,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        workout_exercise_id,
                        next_set_number,
                        weight,
                        reps,
                        created_at,
                    ),
                )
                set_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            if not _is_unique_constraint_error(
                exc,
                ("set_entries.workout_exercise_id", "set_entries.set_number"),
            ):
                raise
            if attempt >= MAX_NUMBERING_RETRIES:
                raise NumberingConflictError(
                    "Could not assign a unique set number."
                ) from exc
        else:
            return get_set_entry(set_id)

    raise NumberingConflictError("Could not assign a unique set number.")


def duplicate_set_for_workout_exercise(
    workout_exercise_id: int,
    *,
    created_at: str,
) -> dict[str, Any] | None:
    with get_db() as conn:
        workout_exercise = conn.execute(
            """
            SELECT workout_id, exercise_id
            FROM workout_exercises
            WHERE id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()

        if workout_exercise is None:
            return None

        source_set = conn.execute(
            """
            SELECT weight, reps
            FROM set_entries
            WHERE workout_exercise_id = ?
            ORDER BY set_number DESC, id DESC
            LIMIT 1
            """,
            (workout_exercise_id,),
        ).fetchone()

        if source_set is None:
            source_set = get_previous_set_for_exercise(
                exercise_id=int(workout_exercise["exercise_id"]),
                current_workout_id=int(workout_exercise["workout_id"]),
            )

    if source_set is None:
        return None

    return add_set_to_workout_exercise(
        workout_exercise_id,
        weight=float(source_set["weight"]),
        reps=int(source_set["reps"]),
        created_at=created_at,
    )


def update_set_entry(
    set_id: int,
    *,
    weight: float | None = None,
    reps: int | None = None,
) -> dict[str, Any] | None:
    current_set = get_set_entry(set_id)
    if current_set is None:
        return None

    with get_db() as conn:
        conn.execute(
            """
            UPDATE set_entries
            SET weight = ?,
                reps = ?
            WHERE id = ?
            """,
            (
                float(weight) if weight is not None else float(current_set["weight"]),
                int(reps) if reps is not None else int(current_set["reps"]),
                set_id,
            ),
        )

    return get_set_entry(set_id)


def delete_set_entry(set_id: int) -> dict[str, Any] | None:
    current_set = get_set_entry(set_id)
    if current_set is None:
        return None

    with get_db() as conn:
        conn.execute(
            """
            DELETE FROM set_entries
            WHERE id = ?
            """,
            (set_id,),
        )
        renumber_sets(conn, int(current_set["workout_exercise_id"]))

    return current_set


def sql_placeholders(values: list[int]) -> str:
    return ", ".join("?" for _ in values)


def row_is_before_workout(
    row: sqlite3.Row,
    *,
    workout_id: int,
    created_at: str,
) -> bool:
    row_created_at = str(row["created_at"])
    row_workout_id = int(row["workout_id"])

    return row_created_at < created_at or (
        row_created_at == created_at and row_workout_id < workout_id
    )


def get_previous_sets_for_empty_items(
    conn: sqlite3.Connection,
    empty_items: list[dict[str, Any]],
    workout_created_at_by_id: dict[int, str],
) -> dict[int, sqlite3.Row]:
    exercise_ids = sorted({int(item["exercise_id"]) for item in empty_items})
    if not exercise_ids:
        return {}

    placeholders = sql_placeholders(exercise_ids)
    rows = conn.execute(
        f"""
        SELECT
            we.exercise_id,
            w.id AS workout_id,
            w.created_at,
            se.weight,
            se.reps
        FROM set_entries se
        JOIN workout_exercises we ON we.id = se.workout_exercise_id
        JOIN workouts w ON w.id = we.workout_id
        WHERE we.exercise_id IN ({placeholders})
        ORDER BY
            we.exercise_id ASC,
            w.created_at DESC,
            w.id DESC,
            se.set_number DESC,
            se.id DESC
        """,
        exercise_ids,
    ).fetchall()

    rows_by_exercise: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        rows_by_exercise.setdefault(int(row["exercise_id"]), []).append(row)

    previous_by_item: dict[int, sqlite3.Row] = {}
    for item in empty_items:
        workout_exercise_id = int(item["workout_exercise_id"])
        workout_id = int(item["workout_id"])
        created_at = workout_created_at_by_id.get(workout_id)
        if created_at is None:
            continue

        for row in rows_by_exercise.get(int(item["exercise_id"]), []):
            if row_is_before_workout(
                row,
                workout_id=workout_id,
                created_at=created_at,
            ):
                previous_by_item[workout_exercise_id] = row
                break

    return previous_by_item


def get_workout_details_batch(
    workout_ids: list[int],
) -> dict[int, list[dict[str, Any]]]:
    unique_workout_ids = sorted({int(workout_id) for workout_id in workout_ids})
    if not unique_workout_ids:
        return {}

    placeholders = sql_placeholders(unique_workout_ids)
    details_by_workout: dict[int, list[dict[str, Any]]] = {
        workout_id: []
        for workout_id in unique_workout_ids
    }

    with get_db() as conn:
        workout_rows = conn.execute(
            f"""
            SELECT id, created_at
            FROM workouts
            WHERE id IN ({placeholders})
            """,
            unique_workout_ids,
        ).fetchall()
        workout_created_at_by_id = {
            int(row["id"]): str(row["created_at"])
            for row in workout_rows
        }

        exercise_rows = conn.execute(
            f"""
            SELECT
                we.workout_id,
                we.id AS workout_exercise_id,
                we.position,
                e.id AS exercise_id,
                e.name AS exercise_name,
                e.profile_key,
                COALESCE(we.measurement_type, e.measurement_type, 'weighted_reps') AS measurement_type,
                COALESCE(we.reps_unit, e.reps_unit, 'reps') AS reps_unit,
                e.default_weight,
                e.min_weight,
                e.max_weight,
                e.weight_step,
                e.default_reps,
                e.min_reps,
                e.max_reps,
                e.reps_step
            FROM workout_exercises we
            JOIN exercises e ON e.id = we.exercise_id
            WHERE we.workout_id IN ({placeholders})
            ORDER BY we.workout_id ASC, we.position ASC, we.id ASC
            """,
            unique_workout_ids,
        ).fetchall()

        workout_exercise_ids = [
            int(row["workout_exercise_id"])
            for row in exercise_rows
        ]
        sets_by_workout_exercise: dict[int, list[sqlite3.Row]] = {
            workout_exercise_id: []
            for workout_exercise_id in workout_exercise_ids
        }
        if workout_exercise_ids:
            set_placeholders = sql_placeholders(workout_exercise_ids)
            set_rows = conn.execute(
                f"""
                SELECT *
                FROM set_entries
                WHERE workout_exercise_id IN ({set_placeholders})
                ORDER BY workout_exercise_id ASC, set_number ASC, id ASC
                """,
                workout_exercise_ids,
            ).fetchall()

            for set_row in set_rows:
                sets_by_workout_exercise.setdefault(
                    int(set_row["workout_exercise_id"]),
                    [],
                ).append(set_row)

        empty_items: list[dict[str, Any]] = []
        for row in exercise_rows:
            workout_id = int(row["workout_id"])
            workout_exercise_id = int(row["workout_exercise_id"])
            sets = sets_by_workout_exercise.get(workout_exercise_id, [])

            total_volume = sum(float(s["weight"]) * int(s["reps"]) for s in sets)
            total_reps = sum(int(s["reps"]) for s in sets)
            measurement = normalize_measurement_settings(
                measurement_type=row["measurement_type"],
                reps_unit=row["reps_unit"],
                exercise_name=row["exercise_name"],
            )
            derived_metrics = derive_set_metrics(
                sets,
                measurement["measurement_type"],
            )

            if sets:
                last_set = sets[-1]
                default_weight = float(last_set["weight"])
                default_reps = int(last_set["reps"])
            else:
                default_weight = float(value_or_default(row["default_weight"], 0))
                default_reps = int(value_or_default(row["default_reps"], 10))

            item = {
                "workout_id": workout_id,
                "workout_exercise_id": workout_exercise_id,
                "exercise_id": int(row["exercise_id"]),
                "exercise_name": row["exercise_name"],
                "profile_key": row["profile_key"] or "accessory",
                "measurement_type": measurement["measurement_type"],
                "reps_unit": measurement["reps_unit"],
                "position": int(row["position"]),
                "sets": sets,
                "total_volume": total_volume,
                "total_volume_kg": derived_metrics["total_volume_kg"],
                "bodyweight_reps": derived_metrics["bodyweight_reps"],
                "duration_seconds": derived_metrics["duration_seconds"],
                "distance_m": derived_metrics["distance_m"],
                "total_reps": total_reps,
                "default_weight": default_weight,
                "default_reps": default_reps,
                "min_weight": float(value_or_default(row["min_weight"], 0)),
                "max_weight": float(value_or_default(row["max_weight"], 200)),
                "weight_step": float(value_or_default(row["weight_step"], 2.5)),
                "min_reps": int(value_or_default(row["min_reps"], 1)),
                "max_reps": int(value_or_default(row["max_reps"], 50)),
                "reps_step": int(value_or_default(row["reps_step"], 1)),
            }
            details_by_workout.setdefault(workout_id, []).append(item)
            if not sets:
                empty_items.append(item)

        previous_sets = get_previous_sets_for_empty_items(
            conn,
            empty_items,
            workout_created_at_by_id,
        )
        for item in empty_items:
            previous_set = previous_sets.get(int(item["workout_exercise_id"]))
            if previous_set:
                item["default_weight"] = float(previous_set["weight"])
                item["default_reps"] = int(previous_set["reps"])

    all_details = [
        item
        for details in details_by_workout.values()
        for item in details
    ]
    weights_by_exercise = get_weight_options_by_exercise_ids(
        [int(item["exercise_id"]) for item in all_details]
    )
    for item in all_details:
        configured_weights = weights_by_exercise.get(
            int(item["exercise_id"]),
            [],
        )
        set_weights = [
            float(set_entry["weight"])
            for set_entry in item["sets"]
        ]
        set_reps = [
            int(set_entry["reps"])
            for set_entry in item["sets"]
        ]
        item["configured_weights"] = configured_weights
        item["weight_options"] = build_effective_weight_options(
            measurement_type=str(item["measurement_type"]),
            min_weight=float(item.get("min_weight", 0)),
            max_weight=float(item.get("max_weight", 200)),
            weight_step=float(item.get("weight_step", 2.5)),
            configured_weights=configured_weights,
            set_weights=set_weights,
            default_weight=float(item["default_weight"]),
        )
        item["reps_options"] = get_int_options(
            min_value=int(item.get("min_reps", 1)),
            max_value=int(item.get("max_reps", 50)),
            step=int(item.get("reps_step", 1)),
            extra_values=[
                *set_reps,
                int(item["default_reps"]),
            ],
        )
        item.pop("min_weight", None)
        item.pop("max_weight", None)
        item.pop("weight_step", None)
        item.pop("min_reps", None)
        item.pop("max_reps", None)
        item.pop("reps_step", None)
        item.pop("workout_id", None)

    return details_by_workout


def get_workout_details(workout_id: int) -> list[dict[str, Any]]:
    return get_workout_details_batch([workout_id]).get(workout_id, [])
