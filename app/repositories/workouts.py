import sqlite3
from typing import Any

from app.db import get_db


def list_recent_workouts(limit: int = 30) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM workouts
            ORDER BY id DESC
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
                e.name AS exercise_name
            FROM workout_exercises we
            JOIN exercises e ON e.id = we.exercise_id
            WHERE we.id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def add_workout_exercise(workout_id: int, exercise_id: int) -> int:
    with get_db() as conn:
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
            INSERT INTO workout_exercises (workout_id, exercise_id, position)
            VALUES (?, ?, ?)
            """,
            (workout_id, exercise_id, next_position),
        )

    return int(cursor.lastrowid)


def delete_workout_exercise(
    workout_id: int,
    workout_exercise_id: int,
) -> bool:
    with get_db() as conn:
        cursor = conn.execute(
            """
            DELETE FROM workout_exercises
            WHERE id = ?
              AND workout_id = ?
            """,
            (workout_exercise_id, workout_id),
        )

    return cursor.rowcount > 0


def get_previous_set_for_exercise(
    exercise_id: int,
    current_workout_id: int,
) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute(
            """
            SELECT se.weight, se.reps
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            JOIN workouts w ON w.id = we.workout_id
            WHERE we.exercise_id = ?
              AND w.id != ?
            ORDER BY w.workout_date DESC, w.id DESC, se.set_number DESC, se.id DESC
            LIMIT 1
            """,
            (exercise_id, current_workout_id),
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
    with get_db() as conn:
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

    return get_set_entry(int(cursor.lastrowid))


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
            source_set = conn.execute(
                """
                SELECT se.weight, se.reps
                FROM set_entries se
                JOIN workout_exercises we ON we.id = se.workout_exercise_id
                JOIN workouts w ON w.id = we.workout_id
                WHERE we.exercise_id = ?
                  AND w.id != ?
                ORDER BY w.workout_date DESC, w.id DESC, se.set_number DESC, se.id DESC
                LIMIT 1
                """,
                (
                    workout_exercise["exercise_id"],
                    workout_exercise["workout_id"],
                ),
            ).fetchone()

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


def get_workout_details(workout_id: int) -> list[dict[str, Any]]:
    with get_db() as conn:
        exercise_rows = conn.execute(
            """
            SELECT
                we.id AS workout_exercise_id,
                we.position,
                e.id AS exercise_id,
                e.name AS exercise_name
            FROM workout_exercises we
            JOIN exercises e ON e.id = we.exercise_id
            WHERE we.workout_id = ?
            ORDER BY we.position ASC, we.id ASC
            """,
            (workout_id,),
        ).fetchall()

        result: list[dict[str, Any]] = []

        for row in exercise_rows:
            sets = conn.execute(
                """
                SELECT *
                FROM set_entries
                WHERE workout_exercise_id = ?
                ORDER BY set_number ASC, id ASC
                """,
                (row["workout_exercise_id"],),
            ).fetchall()

            total_volume = sum(float(s["weight"]) * int(s["reps"]) for s in sets)
            total_reps = sum(int(s["reps"]) for s in sets)

            if sets:
                last_set = sets[-1]
                default_weight = float(last_set["weight"])
                default_reps = int(last_set["reps"])
            else:
                previous_set = get_previous_set_for_exercise(
                    exercise_id=row["exercise_id"],
                    current_workout_id=workout_id,
                )

                if previous_set:
                    default_weight = float(previous_set["weight"])
                    default_reps = int(previous_set["reps"])
                else:
                    default_weight = 0.0
                    default_reps = 10

            result.append(
                {
                    "workout_exercise_id": row["workout_exercise_id"],
                    "exercise_id": row["exercise_id"],
                    "exercise_name": row["exercise_name"],
                    "position": row["position"],
                    "sets": sets,
                    "total_volume": total_volume,
                    "total_reps": total_reps,
                    "default_weight": default_weight,
                    "default_reps": default_reps,
                }
            )

        return result
