from typing import Any

from app.services.analysis_service import estimated_1rm


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


def average(values: list[float]) -> float | None:
    if not values:
        return None

    return sum(values) / len(values)


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
