from datetime import datetime, timedelta
from typing import Any

from app.db import get_db
from app.repositories.workouts import get_workout_details
from app.services.stats_service import calculate_workout_load_metrics


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def format_time_gap(hours: float | None) -> str:
    if hours is None:
        return "—"

    if hours < 1:
        return "<1h"

    if hours < 24:
        return f"{hours:.0f}h"

    days = hours / 24

    if days < 10:
        return f"{days:.1f}d"

    return f"{days:.0f}d"


def rolling_load_label(load_score: float) -> str:
    # These are intentionally wider than single-workout thresholds.
    # This label is for accumulated 7-day load, not one workout.
    if load_score < 8:
        return "Light"
    if load_score < 18:
        return "Medium"
    if load_score < 32:
        return "Hard"
    return "Very hard"


def recovery_time_hint(hours_since_previous_workout: float | None) -> str:
    if hours_since_previous_workout is None:
        return "No previous workout history yet. Start with a normal baseline session."

    if hours_since_previous_workout < 24:
        return "Very short gap since the last workout. Treat this as recovery context, not a green light for progression."

    if hours_since_previous_workout < 48:
        return "Short gap since the last workout. Repeat or light work is usually safer than chasing progression."

    days = hours_since_previous_workout / 24

    if days <= 5:
        return "Normal recovery gap. Progress still depends on RPE, back pain, and recent load."

    if days <= 10:
        return "Longer gap. Conservative progress or repeat is usually safer than aggressive jumps."

    return "Long gap. Rebuild or repeat before chasing PRs."


def build_recovery_context(
    as_of: str | None = None,
    exclude_workout_id: int | None = None,
) -> dict[str, Any]:
    as_of_dt = parse_iso_datetime(as_of) or datetime.now()
    as_of_value = as_of_dt.isoformat(timespec="seconds")

    exclude_sql = ""
    previous_params: list[Any] = [as_of_value]

    if exclude_workout_id is not None:
        exclude_sql = "AND id != ?"
        previous_params.append(exclude_workout_id)

    with get_db() as conn:
        previous_workout = conn.execute(
            f"""
            SELECT
                id,
                created_at,
                session_rpe,
                lower_back_pain
            FROM workouts
            WHERE created_at < ?
              {exclude_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            previous_params,
        ).fetchone()

        window_start = (as_of_dt - timedelta(days=7)).isoformat(timespec="seconds")
        recent_params: list[Any] = [window_start, as_of_value]

        if exclude_workout_id is not None:
            recent_params.append(exclude_workout_id)

        recent_workouts = conn.execute(
            f"""
            SELECT
                id,
                created_at,
                session_rpe,
                lower_back_pain
            FROM workouts
            WHERE created_at >= ?
              AND created_at < ?
              {exclude_sql}
            ORDER BY created_at ASC, id ASC
            """,
            recent_params,
        ).fetchall()

    previous_created_at = None
    hours_since_previous_workout = None
    days_since_previous_workout = None

    if previous_workout:
        previous_created_at = str(previous_workout["created_at"])
        previous_dt = parse_iso_datetime(previous_created_at)

        if previous_dt is not None:
            hours_since_previous_workout = max(
                0.0,
                (as_of_dt - previous_dt).total_seconds() / 3600,
            )
            days_since_previous_workout = hours_since_previous_workout / 24

    total_load_score = 0.0
    total_compound_score = 0.0
    total_back_stress_score = 0.0
    rpe_values: list[int] = []
    back_values: list[int] = []

    for workout in recent_workouts:
        workout_id = int(workout["id"])
        details = get_workout_details(workout_id)

        load_metrics = calculate_workout_load_metrics(
            workout_exercises=details,
            session_rpe=workout["session_rpe"],
            as_of_created_at=workout["created_at"],
            as_of_workout_id=workout_id,
        )

        total_load_score += float(load_metrics["load_score"])
        total_compound_score += float(load_metrics["compound_score"])
        total_back_stress_score += float(load_metrics["back_stress_score"])

        if workout["session_rpe"] is not None:
            rpe_values.append(int(workout["session_rpe"]))

        if workout["lower_back_pain"] is not None:
            back_values.append(int(workout["lower_back_pain"]))

    return {
        "as_of": as_of_value,
        "has_history": previous_workout is not None,
        "previous_workout_id": int(previous_workout["id"]) if previous_workout else None,
        "previous_workout_at": previous_created_at,
        "hours_since_previous_workout": hours_since_previous_workout,
        "days_since_previous_workout": days_since_previous_workout,
        "previous_gap_label": format_time_gap(hours_since_previous_workout),
        "hint": recovery_time_hint(hours_since_previous_workout),
        "last_7d": {
            "workout_count": len(recent_workouts),
            "load_score": total_load_score,
            "load_label": rolling_load_label(total_load_score),
            "compound_score": total_compound_score,
            "back_stress_score": total_back_stress_score,
            "avg_rpe": sum(rpe_values) / len(rpe_values) if rpe_values else None,
            "avg_back_pain": sum(back_values) / len(back_values) if back_values else None,
        },
    }
