import sqlite3
from datetime import datetime
from statistics import median
from typing import Any

from app.db import get_db
from app.repositories.workouts import get_workout_details
from app.services.analysis_service import estimated_1rm, get_exercise_load_profile
from app.services.recovery_service import (
    NON_EMPTY_WORKOUT_EXISTS_SQL,
    build_recovery_context,
    format_time_gap,
    parse_iso_datetime,
)
from app.services.stats_service import calculate_workout_load_metrics


RECOMMENDATION_STATUS_TITLES: dict[str, str] = {
    "progress": "Progress",
    "progress_carefully": "Careful progress",
    "repeat": "Repeat",
    "deload": "Deload",
    "recovery": "Recovery",
}


def format_weight(value: float) -> str:
    if value == int(value):
        return str(int(value))

    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_training_target(weight: float, reps: int) -> str:
    if weight <= 0:
        return f"{reps} reps"

    return f"{format_weight(weight)} kg × {reps}"


def exercise_gap_status(
    days_since_same_exercise: float | None,
    usual_interval_days: float | None,
) -> str:
    if days_since_same_exercise is None:
        return "unknown"

    if usual_interval_days is None or usual_interval_days <= 0:
        if days_since_same_exercise < 1:
            return "very_short"
        if days_since_same_exercise <= 7:
            return "unknown"
        return "long"

    ratio = days_since_same_exercise / usual_interval_days

    if ratio < 0.55:
        return "shorter_than_usual"

    if ratio <= 1.5:
        return "normal"

    if ratio <= 2.5:
        return "longer_than_usual"

    return "much_longer_than_usual"


def exercise_gap_label(status: str) -> str:
    labels = {
        "very_short": "Very short",
        "shorter_than_usual": "Shorter than usual",
        "normal": "Normal",
        "longer_than_usual": "Longer than usual",
        "much_longer_than_usual": "Much longer than usual",
        "long": "Long",
        "unknown": "Unknown",
    }

    return labels.get(status, "Unknown")


def percent_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous <= 0:
        return None

    return (current - previous) / previous * 100


def format_percent_change(value: float | None) -> str:
    if value is None:
        return "—"

    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def get_best_reps_at_weight(
    sets: list[dict[str, Any]],
    target_weight: float,
) -> int | None:
    matching_reps = [
        int(set_row["reps"])
        for set_row in sets
        if abs(float(set_row["weight"]) - target_weight) < 0.001
    ]

    if not matching_reps:
        return None

    return max(matching_reps)


def get_recommendation_top_set(sets: list[Any]) -> dict[str, Any] | None:
    best_set: dict[str, Any] | None = None
    best_score = -1.0

    for set_row in sets:
        weight = float(set_row["weight"])
        reps = int(set_row["reps"])

        if reps <= 0:
            continue

        e1rm = estimated_1rm(weight, reps)

        if e1rm is not None:
            score = e1rm
        elif weight > 0:
            score = weight * reps
        else:
            score = reps

        if score > best_score:
            best_score = score
            best_set = {
                "weight": weight,
                "reps": reps,
                "e1rm": e1rm,
                "score": score,
            }

    return best_set


def build_exercise_progression_trend(
    last_summary: dict[str, Any] | None,
    previous_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    if not last_summary or not previous_summary:
        return {
            "status": "unknown",
            "label": "Unknown",
            "e1rm_change_percent": None,
            "volume_change_percent": None,
            "same_weight_rep_delta": None,
            "summary": "Not enough history to compare this exercise.",
        }

    last_top_weight = last_summary.get("top_weight")
    last_top_reps = last_summary.get("top_reps")

    previous_sets = previous_summary.get("sets") or []
    same_weight_previous_reps = None
    same_weight_rep_delta = None

    if last_top_weight is not None and last_top_reps is not None:
        same_weight_previous_reps = get_best_reps_at_weight(
            previous_sets,
            float(last_top_weight),
        )

        if same_weight_previous_reps is not None:
            same_weight_rep_delta = int(last_top_reps) - int(same_weight_previous_reps)

    e1rm_change_percent = percent_change(
        last_summary.get("best_e1rm"),
        previous_summary.get("best_e1rm"),
    )
    volume_change_percent = percent_change(
        float(last_summary.get("total_volume") or 0),
        float(previous_summary.get("total_volume") or 0),
    )

    recent_jump = False
    small_progress = False
    regression = False

    if e1rm_change_percent is not None:
        if e1rm_change_percent >= 4:
            recent_jump = True
        elif e1rm_change_percent >= 1:
            small_progress = True
        elif e1rm_change_percent <= -5:
            regression = True

    if volume_change_percent is not None:
        if volume_change_percent >= 20:
            recent_jump = True
        elif volume_change_percent >= 8:
            small_progress = True
        elif volume_change_percent <= -20:
            regression = True

    if same_weight_rep_delta is not None:
        if same_weight_rep_delta >= 2:
            recent_jump = True
        elif same_weight_rep_delta == 1:
            small_progress = True
        elif same_weight_rep_delta <= -2:
            regression = True

    if recent_jump:
        status = "recent_jump"
        label = "Recent jump"
        summary = "Last time already improved noticeably; repeating can help consolidate progress."
    elif small_progress:
        status = "small_progress"
        label = "Small progress"
        summary = "Last time improved slightly; small progression or repeat can both be reasonable."
    elif regression:
        status = "regression"
        label = "Regression"
        summary = "Last result was lower than previous; repeat or deload may be safer."
    else:
        status = "stable"
        label = "Stable"
        summary = "Recent performance is stable; progression may be possible if recovery is good."

    return {
        "status": status,
        "label": label,
        "e1rm_change_percent": e1rm_change_percent,
        "volume_change_percent": volume_change_percent,
        "same_weight_rep_delta": same_weight_rep_delta,
        "summary": summary,
    }


def build_exercise_occurrence_summary(
    exercise_id: int,
    workout_id: int,
) -> dict[str, Any] | None:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                se.weight,
                se.reps
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            WHERE we.exercise_id = ?
              AND we.workout_id = ?
            ORDER BY se.set_number ASC, se.id ASC
            """,
            (
                exercise_id,
                workout_id,
            ),
        ).fetchall()

    if not rows:
        return None

    sets = [
        {
            "weight": float(row["weight"]),
            "reps": int(row["reps"]),
        }
        for row in rows
    ]

    top_set = get_recommendation_top_set(sets)

    total_volume = sum(
        float(set_row["weight"]) * int(set_row["reps"])
        for set_row in sets
    )
    total_reps = sum(int(set_row["reps"]) for set_row in sets)

    return {
        "sets": sets,
        "top_set": top_set,
        "top_weight": float(top_set["weight"]) if top_set else None,
        "top_reps": int(top_set["reps"]) if top_set else None,
        "best_e1rm": float(top_set["e1rm"]) if top_set and top_set["e1rm"] is not None else None,
        "total_volume": total_volume,
        "total_reps": total_reps,
        "total_sets": len(sets),
    }


def build_exercise_history_context(
    exercise_id: int,
    as_of: str | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    as_of_dt = parse_iso_datetime(as_of) or datetime.now()
    as_of_value = as_of_dt.isoformat(timespec="seconds")

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                w.id AS workout_id,
                w.created_at,
                SUM(se.weight * se.reps) AS total_volume,
                SUM(se.reps) AS total_reps,
                COUNT(se.id) AS total_sets
            FROM workouts w
            JOIN workout_exercises we ON we.workout_id = w.id
            JOIN set_entries se ON se.workout_exercise_id = we.id
            WHERE we.exercise_id = ?
              AND w.created_at < ?
            GROUP BY w.id, w.created_at
            ORDER BY w.created_at DESC, w.id DESC
            LIMIT ?
            """,
            (
                exercise_id,
                as_of_value,
                limit,
            ),
        ).fetchall()

    if not rows:
        return {
            "has_history": False,
            "last_workout_id": None,
            "last_workout_at": None,
            "previous_workout_id": None,
            "previous_workout_at": None,
            "hours_since_same_exercise": None,
            "days_since_same_exercise": None,
            "same_exercise_gap_label": "—",
            "usual_interval_days": None,
            "usual_interval_label": "—",
            "gap_status": "unknown",
            "gap_status_label": "Unknown",
            "occurrence_count": 0,
            "last_total_volume": None,
            "last_total_reps": None,
            "last_total_sets": None,
            "last_summary": None,
            "previous_summary": None,
            "progression_trend": {
                "status": "unknown",
                "label": "Unknown",
                "e1rm_change_percent": None,
                "volume_change_percent": None,
                "same_weight_rep_delta": None,
                "summary": "Not enough history to compare this exercise.",
            },
        }

    occurrences = [dict(row) for row in rows]
    last_occurrence = occurrences[0]
    previous_occurrence = occurrences[1] if len(occurrences) > 1 else None

    last_summary = build_exercise_occurrence_summary(
        exercise_id=exercise_id,
        workout_id=int(last_occurrence["workout_id"]),
    )

    previous_summary = (
        build_exercise_occurrence_summary(
            exercise_id=exercise_id,
            workout_id=int(previous_occurrence["workout_id"]),
        )
        if previous_occurrence
        else None
    )

    progression_trend = build_exercise_progression_trend(
        last_summary=last_summary,
        previous_summary=previous_summary,
    )

    last_dt = parse_iso_datetime(str(last_occurrence["created_at"]))

    hours_since_same_exercise = None
    days_since_same_exercise = None

    if last_dt is not None:
        hours_since_same_exercise = max(
            0.0,
            (as_of_dt - last_dt).total_seconds() / 3600,
        )
        days_since_same_exercise = hours_since_same_exercise / 24

    chronological = list(reversed(occurrences))
    intervals: list[float] = []

    for previous, current in zip(chronological, chronological[1:]):
        previous_dt = parse_iso_datetime(str(previous["created_at"]))
        current_dt = parse_iso_datetime(str(current["created_at"]))

        if previous_dt is None or current_dt is None:
            continue

        interval_days = (current_dt - previous_dt).total_seconds() / 86400

        if interval_days > 0:
            intervals.append(interval_days)

    usual_interval_days = median(intervals) if intervals else None
    gap_status = exercise_gap_status(
        days_since_same_exercise=days_since_same_exercise,
        usual_interval_days=usual_interval_days,
    )

    return {
        "has_history": True,
        "last_workout_id": int(last_occurrence["workout_id"]),
        "last_workout_at": last_occurrence["created_at"],
        "previous_workout_id": (
            int(previous_occurrence["workout_id"])
            if previous_occurrence
            else None
        ),
        "previous_workout_at": (
            previous_occurrence["created_at"]
            if previous_occurrence
            else None
        ),
        "hours_since_same_exercise": hours_since_same_exercise,
        "days_since_same_exercise": days_since_same_exercise,
        "same_exercise_gap_label": format_time_gap(hours_since_same_exercise),
        "usual_interval_days": usual_interval_days,
        "usual_interval_label": (
            f"{usual_interval_days:.1f}d"
            if usual_interval_days is not None
            else "—"
        ),
        "gap_status": gap_status,
        "gap_status_label": exercise_gap_label(gap_status),
        "occurrence_count": len(occurrences),
        "last_total_volume": float(last_occurrence["total_volume"] or 0),
        "last_total_reps": int(last_occurrence["total_reps"] or 0),
        "last_total_sets": int(last_occurrence["total_sets"] or 0),
        "last_summary": last_summary,
        "previous_summary": previous_summary,
        "progression_trend": progression_trend,
    }


def calculate_readiness_status(
    recovery_context: dict[str, Any],
    last_workout: sqlite3.Row,
    last_load_metrics: dict[str, Any],
) -> dict[str, Any]:
    score = 50
    reasons: list[str] = []

    hours_since_previous = recovery_context.get("hours_since_previous_workout")
    last_7d = recovery_context.get("last_7d", {})
    relative_load = recovery_context.get("relative_load", {})
    confidence = relative_load.get("baseline_confidence", "low")
    acute_ratio = relative_load.get("acute_to_baseline")
    acute_back_ratio = relative_load.get("acute_back_to_baseline")

    if hours_since_previous is None:
        reasons.append("No previous workout gap available yet.")
    elif hours_since_previous < 24:
        score -= 25
        reasons.append("Last workout was less than 24h ago.")
    elif hours_since_previous < 48:
        score -= 10
        reasons.append("Short gap since the last workout.")
    elif hours_since_previous <= 120:
        score += 15
        reasons.append("Recovery gap is in a normal range.")
    elif hours_since_previous <= 240:
        score += 5
        reasons.append("Longer gap, so progress should stay conservative.")
    else:
        score -= 5
        reasons.append("Long gap since last workout; rebuild before chasing PRs.")

    session_rpe = last_workout["session_rpe"]
    if session_rpe is not None:
        session_rpe = int(session_rpe)

        if session_rpe <= 4:
            score += 10
            reasons.append("Last RPE was low.")
        elif session_rpe <= 6:
            score += 5
            reasons.append("Last RPE was moderate.")
        elif session_rpe >= 8:
            score -= 20
            reasons.append("Last RPE was high.")
        elif session_rpe >= 7:
            score -= 10
            reasons.append("Last RPE was elevated.")

    lower_back_pain = last_workout["lower_back_pain"]
    if lower_back_pain is not None:
        lower_back_pain = int(lower_back_pain)

        if lower_back_pain <= 2:
            score += 10
            reasons.append("Lower back pain was low.")
        elif lower_back_pain <= 4:
            reasons.append("Lower back pain was present, so back-heavy work needs caution.")
        elif lower_back_pain <= 6:
            score -= 20
            reasons.append("Lower back pain was elevated.")
        else:
            score -= 35
            reasons.append("Lower back pain was high.")

    use_personal_load_baseline = (
        confidence in {"medium", "high"}
        and acute_ratio is not None
    )

    if use_personal_load_baseline:
        acute_ratio = float(acute_ratio)
        if acute_ratio > 1.50:
            score -= 15
            reasons.append("7-day load is much higher than your recent baseline.")
        elif acute_ratio > 1.25:
            score -= 7
            reasons.append("7-day load is above your recent baseline.")
        elif acute_ratio < 0.75:
            score += 3
            reasons.append("7-day load is below your recent baseline.")
        else:
            reasons.append("7-day load is close to your recent baseline.")
    else:
        load_7d = float(last_7d.get("load_score") or 0)
        if load_7d >= 32:
            score -= 15
            reasons.append("7-day load is very high.")
        elif load_7d >= 18:
            score -= 7
            reasons.append("7-day load is already significant.")
        elif load_7d < 8:
            score += 5
            reasons.append("7-day load is low.")

    use_personal_back_baseline = (
        confidence in {"medium", "high"}
        and acute_back_ratio is not None
    )

    if use_personal_back_baseline:
        acute_back_ratio = float(acute_back_ratio)
        if acute_back_ratio > 1.50:
            score -= 15
            reasons.append("7-day back stress is much higher than your baseline.")
        elif acute_back_ratio > 1.25:
            score -= 7
            reasons.append("7-day back stress is above your baseline.")
        elif acute_back_ratio < 0.75:
            score += 3
            reasons.append("7-day back stress is below your baseline.")
    else:
        back_stress_7d = float(last_7d.get("back_stress_score") or 0)
        if back_stress_7d >= 12:
            score -= 15
            reasons.append("7-day back stress is high.")
        elif back_stress_7d >= 8:
            score -= 7
            reasons.append("7-day back stress is moderate.")
        elif back_stress_7d < 4:
            score += 5
            reasons.append("7-day back stress is low.")

    # Safety caps.
    if hours_since_previous is not None and hours_since_previous < 24:
        score = min(score, 40)

    if lower_back_pain is not None and lower_back_pain >= 4:
        score = min(score, 55)

    if lower_back_pain is not None and lower_back_pain >= 6:
        score = min(score, 35)

    score = max(0, min(100, score))

    if score >= 75:
        status = "progress"
    elif score >= 60:
        status = "progress_carefully"
    elif score >= 45:
        status = "repeat"
    elif score >= 30:
        status = "deload"
    else:
        status = "recovery"

    return {
        "score": score,
        "status": status,
        "title": RECOMMENDATION_STATUS_TITLES[status],
        "reasons": reasons,
    }


def build_exercise_recommendation(
    item: dict[str, Any],
    overall_status: str,
    last_back_pain: int | None,
    exercise_context: dict[str, Any],
) -> dict[str, Any]:
    exercise_name = str(item["exercise_name"])
    profile = get_exercise_load_profile(exercise_name)
    back_factor = float(profile["back_factor"])
    top_set = get_recommendation_top_set(item["sets"])

    gap_status = str(exercise_context.get("gap_status") or "unknown")
    gap_status_label = str(exercise_context.get("gap_status_label") or "Unknown")
    same_exercise_gap_label = str(
        exercise_context.get("same_exercise_gap_label") or "—"
    )
    usual_interval_label = str(
        exercise_context.get("usual_interval_label") or "—"
    )

    progression_trend = exercise_context.get("progression_trend") or {}
    progression_status = str(progression_trend.get("status") or "unknown")
    progression_label = str(progression_trend.get("label") or "Unknown")
    progression_summary = str(progression_trend.get("summary") or "")

    def with_context(result: dict[str, Any]) -> dict[str, Any]:
        result.update(
            {
                "gap_label": same_exercise_gap_label,
                "usual_gap_label": usual_interval_label,
                "gap_status_label": gap_status_label,
                "progression_status": progression_status,
                "progression_label": progression_label,
                "progression_summary": progression_summary,
                "e1rm_change_label": format_percent_change(
                    progression_trend.get("e1rm_change_percent")
                ),
                "volume_change_label": format_percent_change(
                    progression_trend.get("volume_change_percent")
                ),
            }
        )
        return result

    if top_set is None:
        return with_context({
            "exercise_name": exercise_name,
            "action": "start_light",
            "action_label": "Start light",
            "target": "No previous set",
            "reason": "No usable set history for this exercise yet.",
        })

    weight = float(top_set["weight"])
    reps = int(top_set["reps"])
    is_back_sensitive = back_factor >= 0.7
    is_high_back = back_factor >= 1.0

    current_target = format_training_target(weight, reps)

    if last_back_pain is not None and last_back_pain >= 4 and is_back_sensitive:
        if weight > 0:
            deload_weight = round(weight * 0.9, 2)
            target = format_training_target(deload_weight, reps)
        else:
            target = format_training_target(weight, max(1, int(reps * 0.8)))

        return with_context({
            "exercise_name": exercise_name,
            "action": "deload_or_skip",
            "action_label": "Deload / skip",
            "target": target,
            "reason": "Back pain was elevated and this exercise loads the back.",
        })

    if gap_status in ("very_short", "shorter_than_usual"):
        if is_back_sensitive or overall_status != "progress":
            return with_context({
                "exercise_name": exercise_name,
                "action": "repeat",
                "action_label": "Repeat",
                "target": current_target,
                "reason": "This exercise is sooner than your usual interval, so progression is capped.",
            })

    if progression_status == "recent_jump":
        return with_context({
            "exercise_name": exercise_name,
            "action": "repeat",
            "action_label": "Repeat",
            "target": current_target,
            "reason": "Last session already had a noticeable jump; repeat to consolidate progress.",
        })

    if progression_status == "regression" and overall_status != "progress":
        if weight > 0:
            target = format_training_target(round(weight * 0.95, 2), reps)
        else:
            target = format_training_target(weight, max(1, int(reps * 0.9)))

        return with_context({
            "exercise_name": exercise_name,
            "action": "repeat_or_small_deload",
            "action_label": "Repeat / small deload",
            "target": target,
            "reason": "Recent performance dropped; avoid adding load until it stabilizes.",
        })

    if gap_status == "much_longer_than_usual":
        if is_high_back and weight > 0:
            return with_context({
                "exercise_name": exercise_name,
                "action": "small_deload",
                "action_label": "Small deload",
                "target": format_training_target(round(weight * 0.9, 2), reps),
                "reason": "This exercise gap is much longer than usual and the movement is back-heavy.",
            })

        return with_context({
            "exercise_name": exercise_name,
            "action": "repeat",
            "action_label": "Repeat",
            "target": current_target,
            "reason": "This exercise gap is much longer than usual, so repeat before pushing progression.",
        })

    if overall_status == "progress":
        if weight <= 0:
            next_reps = reps + max(1, round(reps * 0.1))
            return with_context({
                "exercise_name": exercise_name,
                "action": "add_reps",
                "action_label": "+ reps",
                "target": format_training_target(weight, next_reps),
                "reason": "Readiness is good and exercise timing is acceptable.",
            })

        if reps < 12:
            return with_context({
                "exercise_name": exercise_name,
                "action": "add_reps",
                "action_label": "+1 rep",
                "target": format_training_target(weight, reps + 1),
                "reason": "Readiness is good; add reps before increasing weight.",
            })

        return with_context({
            "exercise_name": exercise_name,
            "action": "small_weight_increase",
            "action_label": "Small weight increase",
            "target": f"{current_target} + small weight increase",
            "reason": "Reps are already high; a small weight increase is reasonable.",
        })

    if overall_status == "progress_carefully":
        if is_high_back:
            return with_context({
                "exercise_name": exercise_name,
                "action": "repeat",
                "action_label": "Repeat",
                "target": current_target,
                "reason": "Overall readiness allows progress, but this is back-heavy.",
            })

        if weight <= 0:
            return with_context({
                "exercise_name": exercise_name,
                "action": "add_reps",
                "action_label": "+ reps",
                "target": format_training_target(
                    weight,
                    reps + max(1, round(reps * 0.05)),
                ),
                "reason": "Careful progress: use a small rep increase.",
            })

        return with_context({
            "exercise_name": exercise_name,
            "action": "add_reps",
            "action_label": "+1 rep",
            "target": format_training_target(weight, reps + 1),
            "reason": "Careful progress: add only one rep.",
        })

    if overall_status == "repeat":
        return with_context({
            "exercise_name": exercise_name,
            "action": "repeat",
            "action_label": "Repeat",
            "target": current_target,
            "reason": "Current readiness favors repeating the last useful target.",
        })

    if overall_status == "deload":
        if weight > 0:
            target = format_training_target(round(weight * 0.9, 2), reps)
        else:
            target = format_training_target(weight, max(1, int(reps * 0.85)))

        return with_context({
            "exercise_name": exercise_name,
            "action": "deload",
            "action_label": "Deload",
            "target": target,
            "reason": "Recent recovery/load signals suggest reducing stress.",
        })

    return with_context({
        "exercise_name": exercise_name,
        "action": "recovery",
        "action_label": "Recovery",
        "target": "Skip or very light technique work",
        "reason": "Readiness is low; avoid chasing progression.",
    })


def build_next_workout_recommendation(
    recovery_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    recovery_context = recovery_context or build_recovery_context()

    with get_db() as conn:
        last_workout = conn.execute(
            f"""
            SELECT w.*
            FROM workouts w
            WHERE {NON_EMPTY_WORKOUT_EXISTS_SQL}
            ORDER BY w.created_at DESC, w.id DESC
            LIMIT 1
            """
        ).fetchone()

    if not last_workout:
        return {
            "status": "repeat",
            "title": "Start baseline",
            "score": 50,
            "summary": "No workout history yet. Start with a comfortable baseline session.",
            "reasons": [
                "No completed workouts found.",
            ],
            "last_workout_id": None,
            "exercise_recommendations": [],
        }

    details = get_workout_details(int(last_workout["id"]))

    if not details:
        return {
            "status": "repeat",
            "title": "Repeat",
            "score": 50,
            "summary": "Last workout has no exercise data, so no exercise-level recommendation is available.",
            "reasons": [
                "Last workout has no logged sets.",
            ],
            "last_workout_id": int(last_workout["id"]),
            "exercise_recommendations": [],
        }

    last_load_metrics = calculate_workout_load_metrics(
        workout_exercises=details,
        session_rpe=last_workout["session_rpe"],
        as_of_created_at=last_workout["created_at"],
        as_of_workout_id=int(last_workout["id"]),
    )

    readiness = calculate_readiness_status(
        recovery_context=recovery_context,
        last_workout=last_workout,
        last_load_metrics=last_load_metrics,
    )

    last_back_pain = (
        int(last_workout["lower_back_pain"])
        if last_workout["lower_back_pain"] is not None
        else None
    )

    recommendation_as_of = str(
        recovery_context.get("as_of")
        or datetime.now().isoformat(timespec="seconds")
    )

    exercise_recommendations = []

    for item in details:
        exercise_context = build_exercise_history_context(
            exercise_id=int(item["exercise_id"]),
            as_of=recommendation_as_of,
        )

        exercise_recommendations.append(
            build_exercise_recommendation(
                item=item,
                overall_status=readiness["status"],
                last_back_pain=last_back_pain,
                exercise_context=exercise_context,
            )
        )

    if readiness["status"] == "progress":
        summary = "Readiness looks good. Prefer small, controlled progression."
    elif readiness["status"] == "progress_carefully":
        summary = "Some progression is possible, but keep back-heavy work conservative."
    elif readiness["status"] == "repeat":
        summary = "Best next step is to repeat the previous useful targets."
    elif readiness["status"] == "deload":
        summary = "Reduce load or volume to control fatigue and back stress."
    else:
        summary = "Use recovery or very light technique work instead of progression."

    return {
        "status": readiness["status"],
        "title": readiness["title"],
        "score": readiness["score"],
        "summary": summary,
        "reasons": readiness["reasons"][:5],
        "last_workout_id": int(last_workout["id"]),
        "last_workout_at": last_workout["created_at"],
        "exercise_recommendations": exercise_recommendations,
    }
