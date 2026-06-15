import sqlite3
from typing import Any

from app.db import get_db


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
