import sqlite3
from typing import Any

from app.db import get_db


def list_exercises() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, name
            FROM exercises
            ORDER BY name ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_exercise(exercise_id: int) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id, name
            FROM exercises
            WHERE id = ?
            """,
            (exercise_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def get_exercise_by_name(name: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id, name
            FROM exercises
            WHERE name = ?
            """,
            (name,),
        ).fetchone()

    return dict(row) if row is not None else None


def create_exercise(name: str) -> tuple[dict[str, Any], bool]:
    existing = get_exercise_by_name(name)
    if existing is not None:
        return existing, False

    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO exercises (name)
            VALUES (?)
            """,
            (name,),
        )
        exercise_id = int(cursor.lastrowid)

    exercise = get_exercise(exercise_id)
    if exercise is None:
        raise RuntimeError("Created exercise could not be loaded.")

    return exercise, True


def update_exercise_name(exercise_id: int, name: str) -> dict[str, Any] | None:
    with get_db() as conn:
        try:
            cursor = conn.execute(
                """
                UPDATE exercises
                SET name = ?
                WHERE id = ?
                """,
                (name, exercise_id),
            )
        except sqlite3.IntegrityError:
            raise

        if cursor.rowcount == 0:
            return None

    return get_exercise(exercise_id)
