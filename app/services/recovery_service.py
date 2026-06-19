from datetime import datetime, timedelta
from statistics import median
from typing import Any

from app.db import get_db
from app.repositories.workouts import get_workout_details_batch
from app.services.stats_service import (
    build_e1rm_baselines_by_workout,
    calculate_workout_load_metrics,
)


NON_EMPTY_WORKOUT_EXISTS_SQL = """
EXISTS (
    SELECT 1
    FROM workout_exercises we
    JOIN set_entries se ON se.workout_exercise_id = we.id
    WHERE we.workout_id = w.id
)
"""


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


def relative_load_label(
    ratio: float | None,
    fallback_load: float,
) -> str:
    if ratio is None:
        return rolling_load_label(fallback_load)

    if ratio < 0.75:
        return "Below usual"

    if ratio <= 1.25:
        return "Normal"

    if ratio <= 1.50:
        return "Elevated"

    return "High"


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


def get_non_empty_workouts_between(
    start_at: datetime,
    end_at: datetime,
    exclude_workout_id: int | None = None,
) -> list[Any]:
    exclude_sql = ""
    params: list[Any] = [
        start_at.isoformat(timespec="seconds"),
        end_at.isoformat(timespec="seconds"),
    ]

    if exclude_workout_id is not None:
        exclude_sql = "AND w.id != ?"
        params.append(exclude_workout_id)

    with get_db() as conn:
        return conn.execute(
            f"""
            SELECT
                w.id,
                w.created_at,
                w.session_rpe,
                w.lower_back_pain
            FROM workouts w
            WHERE w.created_at >= ?
              AND w.created_at < ?
              AND {NON_EMPTY_WORKOUT_EXISTS_SQL}
              {exclude_sql}
            ORDER BY w.created_at ASC, w.id ASC
            """,
            params,
        ).fetchall()


def summarize_workouts(
    workouts: list[Any],
    window_days: int,
    *,
    details_by_workout: dict[int, list[dict[str, Any]]] | None = None,
    e1rm_baselines_by_workout: dict[int, dict[int, float]] | None = None,
) -> dict[str, Any]:
    workout_ids = [int(workout["id"]) for workout in workouts]
    if details_by_workout is None:
        details_by_workout = get_workout_details_batch(workout_ids)
    if e1rm_baselines_by_workout is None:
        e1rm_baselines_by_workout = build_e1rm_baselines_by_workout(
            workouts=workouts,
            details_by_workout=details_by_workout,
        )

    total_load_score = 0.0
    total_compound_score = 0.0
    total_back_stress_score = 0.0
    rpe_values: list[int] = []
    back_values: list[int] = []
    workout_datetimes: list[datetime] = []

    for workout in workouts:
        workout_id = int(workout["id"])
        details = details_by_workout.get(workout_id, [])
        workout_dt = parse_iso_datetime(str(workout["created_at"]))
        if workout_dt is not None:
            workout_datetimes.append(workout_dt)

        load_metrics = calculate_workout_load_metrics(
            workout_exercises=details,
            session_rpe=workout["session_rpe"],
            as_of_created_at=workout["created_at"],
            as_of_workout_id=workout_id,
            best_e1rm_by_exercise=e1rm_baselines_by_workout.get(
                workout_id,
                {},
            ),
        )

        total_load_score += float(load_metrics["load_score"])
        total_compound_score += float(load_metrics["compound_score"])
        total_back_stress_score += float(load_metrics["back_stress_score"])

        if workout["session_rpe"] is not None:
            rpe_values.append(int(workout["session_rpe"]))

        if workout["lower_back_pain"] is not None:
            back_values.append(int(workout["lower_back_pain"]))

    weeks = window_days / 7
    workout_count = len(workouts)
    sorted_datetimes = sorted(workout_datetimes)

    first_workout_at = (
        sorted_datetimes[0].isoformat(timespec="seconds")
        if sorted_datetimes
        else None
    )
    last_workout_at = (
        sorted_datetimes[-1].isoformat(timespec="seconds")
        if sorted_datetimes
        else None
    )
    coverage_days = 0
    active_week_count = 0

    if sorted_datetimes:
        coverage_days = (
            sorted_datetimes[-1].date() - sorted_datetimes[0].date()
        ).days + 1
        active_week_count = len(
            {
                workout_week_start_from_datetime(workout_dt)
                for workout_dt in sorted_datetimes
            }
        )

    return {
        "days": window_days,
        "workout_count": workout_count,
        "load_score": total_load_score,
        "load_label": rolling_load_label(total_load_score),
        "compound_score": total_compound_score,
        "back_stress_score": total_back_stress_score,
        "avg_rpe": sum(rpe_values) / len(rpe_values) if rpe_values else None,
        "avg_back_pain": sum(back_values) / len(back_values) if back_values else None,
        "weekly_load_equivalent": total_load_score / weeks if weeks > 0 else 0,
        "weekly_back_stress_equivalent": (
            total_back_stress_score / weeks
            if weeks > 0
            else 0
        ),
        "weekly_workout_average": workout_count / weeks if weeks > 0 else 0,
        "first_workout_at": first_workout_at,
        "last_workout_at": last_workout_at,
        "coverage_days": coverage_days,
        "active_week_count": active_week_count,
        "avg_load_per_workout": (
            total_load_score / workout_count
            if workout_count
            else 0
        ),
        "avg_back_stress_per_workout": (
            total_back_stress_score / workout_count
            if workout_count
            else 0
        ),
    }



def safe_ratio(
    current: float,
    baseline: float,
) -> float | None:
    if baseline <= 0:
        return None

    return current / baseline


def workout_week_start_from_datetime(value: datetime) -> str:
    week_start = value.date() - timedelta(days=value.weekday())
    return week_start.isoformat()


def interval_confidence_from_sample_count(sample_count: int) -> str:
    if sample_count >= 5:
        return "high"
    if sample_count >= 3:
        return "medium"
    return "low"


def overall_interval_status(
    days_since_previous_workout: float | None,
    median_interval_days: float | None,
    confidence: str,
) -> tuple[float | None, str]:
    if days_since_previous_workout is None:
        return None, "unknown"

    if (
        confidence not in {"medium", "high"}
        or median_interval_days is None
        or median_interval_days <= 0
    ):
        if days_since_previous_workout < 1:
            return None, "very_short"
        if days_since_previous_workout <= 10:
            return None, "unknown"
        return None, "long"

    ratio = days_since_previous_workout / median_interval_days

    if ratio < 0.55:
        return ratio, "shorter_than_usual"
    if ratio <= 1.5:
        return ratio, "normal"
    if ratio <= 2.5:
        return ratio, "longer_than_usual"

    return ratio, "much_longer_than_usual"


INTERVAL_STATUS_LABELS = {
    "very_short": "Very short",
    "shorter_than_usual": "Shorter than usual",
    "normal": "Normal",
    "longer_than_usual": "Longer than usual",
    "much_longer_than_usual": "Much longer than usual",
    "long": "Long",
    "unknown": "Unknown",
}


def build_overall_interval_context(
    workouts: list[Any],
    hours_since_previous_workout: float | None,
) -> dict[str, Any]:
    chronological = []
    for workout in workouts:
        workout_dt = parse_iso_datetime(str(workout["created_at"]))
        if workout_dt is not None:
            chronological.append(workout_dt)

    chronological.sort()
    intervals: list[float] = []
    for previous_dt, current_dt in zip(chronological, chronological[1:]):
        interval_days = (current_dt - previous_dt).total_seconds() / 86400
        if interval_days > 0:
            intervals.append(interval_days)

    sample_count = len(intervals)
    confidence = interval_confidence_from_sample_count(sample_count)
    median_interval_days = median(intervals) if intervals else None
    days_since_previous_workout = (
        hours_since_previous_workout / 24
        if hours_since_previous_workout is not None
        else None
    )
    current_ratio, status = overall_interval_status(
        days_since_previous_workout=days_since_previous_workout,
        median_interval_days=median_interval_days,
        confidence=confidence,
    )

    return {
        "median_days": median_interval_days,
        "sample_count": sample_count,
        "confidence": confidence,
        "current_ratio": current_ratio,
        "status": status,
        "status_label": INTERVAL_STATUS_LABELS.get(status, "Unknown"),
    }


def baseline_confidence(
    previous_21d_workouts: int,
    last_42d_workouts: int,
    active_week_count: int,
    coverage_days: float,
) -> str:
    if (
        last_42d_workouts >= 12
        and previous_21d_workouts >= 5
        and active_week_count >= 5
        and coverage_days >= 28
    ):
        return "high"

    if (
        last_42d_workouts >= 6
        and previous_21d_workouts >= 3
        and active_week_count >= 3
        and coverage_days >= 14
    ):
        return "medium"

    return "low"



def build_recovery_context(
    as_of: str | None = None,
    exclude_workout_id: int | None = None,
) -> dict[str, Any]:
    as_of_dt = parse_iso_datetime(as_of) or datetime.now()
    as_of_value = as_of_dt.isoformat(timespec="seconds")

    exclude_sql = ""
    previous_params: list[Any] = [as_of_value]

    if exclude_workout_id is not None:
        exclude_sql = "AND w.id != ?"
        previous_params.append(exclude_workout_id)

    with get_db() as conn:
        previous_workout = conn.execute(
            f"""
            SELECT
                w.id,
                w.created_at,
                w.session_rpe,
                w.lower_back_pain
            FROM workouts w
            WHERE w.created_at < ?
              AND {NON_EMPTY_WORKOUT_EXISTS_SQL}
              {exclude_sql}
            ORDER BY w.created_at DESC, w.id DESC
            LIMIT 1
            """,
            previous_params,
        ).fetchone()

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

    acute_start = as_of_dt - timedelta(days=7)
    baseline_start = as_of_dt - timedelta(days=28)
    long_start = as_of_dt - timedelta(days=42)

    last_42d_workouts = get_non_empty_workouts_between(
        long_start,
        as_of_dt,
        exclude_workout_id=exclude_workout_id,
    )

    last_7d_workouts = []
    previous_21d_workouts = []
    for workout in last_42d_workouts:
        workout_dt = parse_iso_datetime(str(workout["created_at"]))
        if workout_dt is None:
            continue

        if acute_start <= workout_dt < as_of_dt:
            last_7d_workouts.append(workout)
        elif baseline_start <= workout_dt < acute_start:
            previous_21d_workouts.append(workout)

    workout_ids = [int(workout["id"]) for workout in last_42d_workouts]
    details_by_workout = get_workout_details_batch(workout_ids)
    e1rm_baselines_by_workout = build_e1rm_baselines_by_workout(
        workouts=last_42d_workouts,
        details_by_workout=details_by_workout,
    )

    last_7d = summarize_workouts(
        last_7d_workouts,
        7,
        details_by_workout=details_by_workout,
        e1rm_baselines_by_workout=e1rm_baselines_by_workout,
    )
    previous_21d = summarize_workouts(
        previous_21d_workouts,
        21,
        details_by_workout=details_by_workout,
        e1rm_baselines_by_workout=e1rm_baselines_by_workout,
    )
    last_42d = summarize_workouts(
        last_42d_workouts,
        42,
        details_by_workout=details_by_workout,
        e1rm_baselines_by_workout=e1rm_baselines_by_workout,
    )

    acute_to_baseline = safe_ratio(
        float(last_7d["weekly_load_equivalent"]),
        float(previous_21d["weekly_load_equivalent"]),
    )
    acute_back_to_baseline = safe_ratio(
        float(last_7d["weekly_back_stress_equivalent"]),
        float(previous_21d["weekly_back_stress_equivalent"]),
    )
    confidence = baseline_confidence(
        previous_21d_workouts=int(previous_21d["workout_count"]),
        last_42d_workouts=int(last_42d["workout_count"]),
        active_week_count=int(last_42d["active_week_count"]),
        coverage_days=float(last_42d["coverage_days"]),
    )
    label_ratio = (
        acute_to_baseline
        if confidence in {"medium", "high"}
        else None
    )
    last_7d["load_label"] = relative_load_label(
        label_ratio,
        float(last_7d["load_score"]),
    )
    baseline_is_reliable = confidence in {"medium", "high"}
    display_acute_to_baseline = (
        acute_to_baseline if baseline_is_reliable else None
    )
    display_acute_back_to_baseline = (
        acute_back_to_baseline if baseline_is_reliable else None
    )
    overall_interval = build_overall_interval_context(
        last_42d_workouts,
        hours_since_previous_workout,
    )

    return {
        "as_of": as_of_value,
        "has_history": previous_workout is not None,
        "previous_workout_id": int(previous_workout["id"]) if previous_workout else None,
        "previous_workout_at": previous_created_at,
        "hours_since_previous_workout": hours_since_previous_workout,
        "days_since_previous_workout": days_since_previous_workout,
        "previous_gap_label": format_time_gap(hours_since_previous_workout),
        "hint": recovery_time_hint(hours_since_previous_workout),
        "last_7d": last_7d,
        "previous_21d": previous_21d,
        "last_42d": last_42d,
        "overall_interval": overall_interval,
        "relative_load": {
            "acute_to_baseline": acute_to_baseline,
            "acute_back_to_baseline": acute_back_to_baseline,
            "display_acute_to_baseline": display_acute_to_baseline,
            "display_acute_back_to_baseline": display_acute_back_to_baseline,
            "baseline_confidence": confidence,
            "baseline_is_reliable": baseline_is_reliable,
        },
    }
