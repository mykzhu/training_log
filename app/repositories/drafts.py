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
            e.profile_key,
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
                "profile_key": row["profile_key"] or "accessory",
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


def create_active_draft(started_at: str) -> dict[str, Any]:
    updated_at = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:
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
                started_at,
                None,
                None,
                1,
                1,
                updated_at,
            ),
        )
        draft = load_active_draft(conn)

    if draft is None:
        raise RuntimeError("Created draft could not be loaded.")

    return draft


def update_active_draft_metadata(updates: dict[str, int | None]) -> bool:
    allowed = {"session_rpe", "lower_back_pain"}
    unexpected = set(updates) - allowed
    if unexpected:
        raise ValueError(f"Unexpected draft metadata fields: {sorted(unexpected)}")
    if not updates:
        return True

    updated_at = datetime.now().isoformat(timespec="seconds")
    assignments = [f"{key} = ?" for key in updates]
    values = list(updates.values())
    assignments.append("updated_at = ?")
    values.append(updated_at)

    with get_db() as conn:
        cursor = conn.execute(
            f"""
            UPDATE active_workout_draft
            SET {", ".join(assignments)}
            WHERE id = 1
            """,
            values,
        )

    return cursor.rowcount > 0


def insert_draft_exercise(
    exercise_id: int,
) -> dict[str, Any] | None:
    updated_at = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:
        draft = conn.execute(
            """
            SELECT next_workout_exercise_id
            FROM active_workout_draft
            WHERE id = 1
            """
        ).fetchone()
        if draft is None:
            return None

        draft_exercise_id = int(draft["next_workout_exercise_id"])
        position = int(
            conn.execute(
                """
                SELECT COALESCE(MAX(position), 0) + 1
                FROM active_draft_exercises
                WHERE draft_id = 1
                """
            ).fetchone()[0]
        )
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
            (draft_exercise_id, exercise_id, position),
        )
        conn.execute(
            """
            UPDATE active_workout_draft
            SET next_workout_exercise_id = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (draft_exercise_id + 1, updated_at),
        )

        return load_active_draft(conn)


def insert_draft_set(
    draft_exercise_id: int,
    *,
    weight: float,
    reps: int,
    created_at: str,
) -> dict[str, Any] | None:
    updated_at = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:
        draft = conn.execute(
            """
            SELECT next_set_id
            FROM active_workout_draft
            WHERE id = 1
            """
        ).fetchone()
        if draft is None:
            return None

        draft_exercise = conn.execute(
            """
            SELECT id
            FROM active_draft_exercises
            WHERE id = ? AND draft_id = 1
            """,
            (draft_exercise_id,),
        ).fetchone()
        if draft_exercise is None:
            return None

        set_id = int(draft["next_set_id"])
        set_number = int(
            conn.execute(
                """
                SELECT COALESCE(MAX(set_number), 0) + 1
                FROM active_draft_sets
                WHERE draft_exercise_id = ?
                """,
                (draft_exercise_id,),
            ).fetchone()[0]
        )

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
            (set_id, draft_exercise_id, set_number, weight, reps, created_at),
        )
        conn.execute(
            """
            UPDATE active_workout_draft
            SET next_set_id = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (set_id + 1, updated_at),
        )

        return load_active_draft(conn)


def update_draft_set(
    draft_set_id: int,
    *,
    weight: float | None = None,
    reps: int | None = None,
) -> bool:
    assignments = []
    params: list[Any] = []
    if weight is not None:
        assignments.append("weight = ?")
        params.append(weight)
    if reps is not None:
        assignments.append("reps = ?")
        params.append(reps)

    if not assignments:
        return False

    updated_at = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:
        cursor = conn.execute(
            f"""
            UPDATE active_draft_sets
            SET {", ".join(assignments)}
            WHERE id = ?
            """,
            (*params, draft_set_id),
        )
        if cursor.rowcount:
            conn.execute(
                """
                UPDATE active_workout_draft
                SET updated_at = ?
                WHERE id = 1
                """,
                (updated_at,),
            )

    return cursor.rowcount > 0


def renumber_sets_for_draft_exercise(
    conn,
    draft_exercise_id: int,
) -> None:
    rows = conn.execute(
        """
        SELECT id
        FROM active_draft_sets
        WHERE draft_exercise_id = ?
        ORDER BY set_number ASC, id ASC
        """,
        (draft_exercise_id,),
    ).fetchall()

    for index, row in enumerate(rows, start=1):
        conn.execute(
            """
            UPDATE active_draft_sets
            SET set_number = ?
            WHERE id = ?
            """,
            (index, int(row["id"])),
        )


def delete_draft_set(draft_set_id: int) -> bool:
    updated_at = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:
        row = conn.execute(
            """
            SELECT draft_exercise_id
            FROM active_draft_sets
            WHERE id = ?
            """,
            (draft_set_id,),
        ).fetchone()
        if row is None:
            return False

        draft_exercise_id = int(row["draft_exercise_id"])
        conn.execute("DELETE FROM active_draft_sets WHERE id = ?", (draft_set_id,))
        renumber_sets_for_draft_exercise(conn, draft_exercise_id)
        conn.execute(
            """
            UPDATE active_workout_draft
            SET updated_at = ?
            WHERE id = 1
            """,
            (updated_at,),
        )

    return True


def delete_draft_exercise(draft_exercise_id: int) -> bool:
    updated_at = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:
        cursor = conn.execute(
            """
            DELETE FROM active_draft_exercises
            WHERE id = ? AND draft_id = 1
            """,
            (draft_exercise_id,),
        )
        if cursor.rowcount == 0:
            return False

        rows = conn.execute(
            """
            SELECT id
            FROM active_draft_exercises
            WHERE draft_id = 1
            ORDER BY position ASC, id ASC
            """
        ).fetchall()
        for index, row in enumerate(rows, start=1):
            conn.execute(
                """
                UPDATE active_draft_exercises
                SET position = ?
                WHERE id = ?
                """,
                (index, int(row["id"])),
            )
        conn.execute(
            """
            UPDATE active_workout_draft
            SET updated_at = ?
            WHERE id = 1
            """,
            (updated_at,),
        )

    return True


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
