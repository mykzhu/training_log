from datetime import datetime
from typing import Any

from app.db import get_db


class NoActiveDraftError(Exception):
    pass


class EmptyDraftError(Exception):
    pass


def load_active_draft(conn) -> dict[str, Any] | None:
    draft = conn.execute(
        """
        SELECT *
        FROM active_workout_draft
        WHERE id = 1
        """
    ).fetchone()

    if draft is None:
        return None

    exercise_rows = conn.execute(
        """
        SELECT
            ade.id,
            ade.exercise_id,
            e.name AS exercise_name,
            ade.position
        FROM active_draft_exercises ade
        JOIN exercises e ON e.id = ade.exercise_id
        WHERE ade.draft_id = 1
        ORDER BY ade.position ASC, ade.id ASC
        """
    ).fetchall()

    set_rows = conn.execute(
        """
        SELECT *
        FROM active_draft_sets
        ORDER BY set_number ASC, id ASC
        """
    ).fetchall()

    sets_by_exercise: dict[int, list[dict[str, Any]]] = {}
    for row in set_rows:
        draft_exercise_id = int(row["draft_exercise_id"])
        sets_by_exercise.setdefault(draft_exercise_id, []).append(
            {
                "id": int(row["id"]),
                "set_number": int(row["set_number"]),
                "weight": float(row["weight"]),
                "reps": int(row["reps"]),
                "created_at": row["created_at"],
            }
        )

    return {
        "started_at": draft["started_at"],
        "session_rpe": draft["session_rpe"],
        "lower_back_pain": draft["lower_back_pain"],
        "workout_exercises": [
            {
                "id": int(row["id"]),
                "exercise_id": int(row["exercise_id"]),
                "exercise_name": row["exercise_name"],
                "position": int(row["position"]),
                "sets": sets_by_exercise.get(int(row["id"]), []),
            }
            for row in exercise_rows
        ],
        "next_workout_exercise_id": int(draft["next_workout_exercise_id"]),
        "next_set_id": int(draft["next_set_id"]),
    }


def get_active_draft() -> dict[str, Any] | None:
    with get_db() as conn:
        return load_active_draft(conn)


def replace_active_draft(draft: dict[str, Any]) -> None:
    updated_at = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:
        conn.execute("DELETE FROM active_workout_draft WHERE id = 1")
        conn.execute(
            """
            INSERT INTO active_workout_draft (
                id,
                started_at,
                session_rpe,
                lower_back_pain,
                next_workout_exercise_id,
                next_set_id,
                updated_at
            )
            VALUES (1, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(draft["started_at"]),
                draft.get("session_rpe"),
                draft.get("lower_back_pain"),
                int(draft["next_workout_exercise_id"]),
                int(draft["next_set_id"]),
                updated_at,
            ),
        )

        for draft_exercise in sorted(
            draft["workout_exercises"],
            key=lambda item: (item["position"], item["id"]),
        ):
            conn.execute(
                """
                INSERT INTO active_draft_exercises (
                    id,
                    draft_id,
                    exercise_id,
                    position
                )
                VALUES (?, 1, ?, ?)
                """,
                (
                    int(draft_exercise["id"]),
                    int(draft_exercise["exercise_id"]),
                    int(draft_exercise["position"]),
                ),
            )

            for set_entry in sorted(
                draft_exercise["sets"],
                key=lambda item: (item["set_number"], item["id"]),
            ):
                conn.execute(
                    """
                    INSERT INTO active_draft_sets (
                        id,
                        draft_exercise_id,
                        set_number,
                        weight,
                        reps,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(set_entry["id"]),
                        int(draft_exercise["id"]),
                        int(set_entry["set_number"]),
                        float(set_entry["weight"]),
                        int(set_entry["reps"]),
                        str(set_entry["created_at"]),
                    ),
                )


def clear_active_draft() -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM active_workout_draft WHERE id = 1")


def count_draft_sets(draft: dict[str, Any]) -> int:
    return sum(
        len(draft_exercise["sets"])
        for draft_exercise in draft["workout_exercises"]
    )


def insert_completed_workout(
    conn,
    draft: dict[str, Any],
    *,
    finished_at: str,
    duration_seconds: int | None,
) -> int:
    started_at_raw = str(draft["started_at"])
    workout_cursor = conn.execute(
        """
        INSERT INTO workouts (
            workout_date,
            created_at,
            finished_at,
            session_rpe,
            lower_back_pain,
            duration_seconds
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            started_at_raw[:10],
            started_at_raw,
            finished_at,
            draft.get("session_rpe"),
            draft.get("lower_back_pain"),
            duration_seconds,
        ),
    )

    return int(workout_cursor.lastrowid)


def insert_completed_exercises_and_sets(
    conn,
    workout_id: int,
    draft: dict[str, Any],
) -> None:
    for draft_exercise in sorted(
        draft["workout_exercises"],
        key=lambda item: (item["position"], item["id"]),
    ):
        workout_exercise_cursor = conn.execute(
            """
            INSERT INTO workout_exercises (workout_id, exercise_id, position)
            VALUES (?, ?, ?)
            """,
            (
                workout_id,
                int(draft_exercise["exercise_id"]),
                int(draft_exercise["position"]),
            ),
        )

        workout_exercise_id = int(workout_exercise_cursor.lastrowid)

        for set_entry in draft_exercise["sets"]:
            conn.execute(
                """
                INSERT INTO set_entries
                    (workout_exercise_id, set_number, weight, reps, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    workout_exercise_id,
                    int(set_entry["set_number"]),
                    float(set_entry["weight"]),
                    int(set_entry["reps"]),
                    str(set_entry["created_at"]),
                ),
            )


def finalize_active_draft() -> int:
    finished_at = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:
        draft = load_active_draft(conn)
        if draft is None:
            raise NoActiveDraftError()

        if count_draft_sets(draft) == 0:
            raise EmptyDraftError()

        started_at_raw = str(draft["started_at"])
        try:
            started_at_dt = datetime.fromisoformat(started_at_raw)
            finished_at_dt = datetime.fromisoformat(finished_at)
            duration_seconds = max(
                0,
                int((finished_at_dt - started_at_dt).total_seconds()),
            )
        except ValueError:
            duration_seconds = None

        workout_id = insert_completed_workout(
            conn,
            draft,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
        )
        insert_completed_exercises_and_sets(conn, workout_id, draft)
        conn.execute("DELETE FROM active_workout_draft WHERE id = 1")

    return workout_id
