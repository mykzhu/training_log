from datetime import datetime
from typing import Any

from app.db import get_db


VALID_RESPONSES = {"helped", "same", "worse", "unknown"}


def current_timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def derive_response(
    *,
    back_pain_before: int | None,
    back_pain_after: int | None,
    explicit_response: str | None,
) -> str:
    if explicit_response in VALID_RESPONSES:
        return explicit_response

    if back_pain_before is None or back_pain_after is None:
        return "unknown"

    if back_pain_after < back_pain_before:
        return "helped"
    if back_pain_after > back_pain_before:
        return "worse"
    return "same"


def serialize_feedback(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None

    return {
        "back_pain_before": row["back_pain_before"],
        "back_pain_after": row["back_pain_after"],
        "response": row["response"] or "unknown",
        "notes": row["notes"],
        "updated_at": row["updated_at"],
    }


def build_feedback_values(
    existing: Any | None,
    *,
    changed_fields: set[str],
    back_pain_before: int | None,
    back_pain_after: int | None,
    response: str | None,
    notes: str | None,
) -> dict[str, Any]:
    next_before = (
        back_pain_before
        if "back_pain_before" in changed_fields
        else existing["back_pain_before"] if existing is not None else None
    )
    next_after = (
        back_pain_after
        if "back_pain_after" in changed_fields
        else existing["back_pain_after"] if existing is not None else None
    )
    next_notes = (
        notes
        if "notes" in changed_fields
        else existing["notes"] if existing is not None else None
    )
    existing_response = (
        existing["response"]
        if existing is not None and existing["response"] in VALID_RESPONSES
        else None
    )
    score_changed = bool({"back_pain_before", "back_pain_after"} & changed_fields)
    explicit_response = response if "response" in changed_fields else None
    next_response = (
        derive_response(
            back_pain_before=next_before,
            back_pain_after=next_after,
            explicit_response=explicit_response,
        )
        if "response" in changed_fields or score_changed or existing_response is None
        else existing_response
    )

    return {
        "back_pain_before": next_before,
        "back_pain_after": next_after,
        "response": next_response,
        "notes": next_notes,
        "updated_at": current_timestamp(),
    }


def active_draft_feedback_by_exercise_ids(
    draft_exercise_ids: list[int],
) -> dict[int, dict[str, Any]]:
    if not draft_exercise_ids:
        return {}

    placeholders = ", ".join("?" for _ in draft_exercise_ids)
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM active_draft_exercise_feedback
            WHERE draft_exercise_id IN ({placeholders})
            """,
            draft_exercise_ids,
        ).fetchall()

    return {
        int(row["draft_exercise_id"]): serialize_feedback(row)
        for row in rows
    }


def workout_feedback_by_exercise_ids(
    workout_exercise_ids: list[int],
) -> dict[int, dict[str, Any]]:
    if not workout_exercise_ids:
        return {}

    placeholders = ", ".join("?" for _ in workout_exercise_ids)
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM workout_exercise_feedback
            WHERE workout_exercise_id IN ({placeholders})
            """,
            workout_exercise_ids,
        ).fetchall()

    return {
        int(row["workout_exercise_id"]): serialize_feedback(row)
        for row in rows
    }


def upsert_active_draft_exercise_feedback(
    draft_exercise_id: int,
    *,
    changed_fields: set[str],
    back_pain_before: int | None,
    back_pain_after: int | None,
    response: str | None,
    notes: str | None,
) -> dict[str, Any]:
    with get_db() as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM active_draft_exercise_feedback
            WHERE draft_exercise_id = ?
            """,
            (draft_exercise_id,),
        ).fetchone()
        values = build_feedback_values(
            existing,
            changed_fields=changed_fields,
            back_pain_before=back_pain_before,
            back_pain_after=back_pain_after,
            response=response,
            notes=notes,
        )
        conn.execute(
            """
            INSERT INTO active_draft_exercise_feedback (
                draft_exercise_id,
                back_pain_before,
                back_pain_after,
                response,
                notes,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(draft_exercise_id) DO UPDATE SET
                back_pain_before = excluded.back_pain_before,
                back_pain_after = excluded.back_pain_after,
                response = excluded.response,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                draft_exercise_id,
                values["back_pain_before"],
                values["back_pain_after"],
                values["response"],
                values["notes"],
                values["updated_at"],
            ),
        )

    return values


def upsert_workout_exercise_feedback(
    workout_exercise_id: int,
    *,
    changed_fields: set[str],
    back_pain_before: int | None,
    back_pain_after: int | None,
    response: str | None,
    notes: str | None,
) -> dict[str, Any]:
    with get_db() as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM workout_exercise_feedback
            WHERE workout_exercise_id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()
        values = build_feedback_values(
            existing,
            changed_fields=changed_fields,
            back_pain_before=back_pain_before,
            back_pain_after=back_pain_after,
            response=response,
            notes=notes,
        )
        conn.execute(
            """
            INSERT INTO workout_exercise_feedback (
                workout_exercise_id,
                back_pain_before,
                back_pain_after,
                response,
                notes,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(workout_exercise_id) DO UPDATE SET
                back_pain_before = excluded.back_pain_before,
                back_pain_after = excluded.back_pain_after,
                response = excluded.response,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                workout_exercise_id,
                values["back_pain_before"],
                values["back_pain_after"],
                values["response"],
                values["notes"],
                values["updated_at"],
            ),
        )

    return values
