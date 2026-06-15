import json
import logging
import sqlite3
import time
from copy import deepcopy
from datetime import datetime, timedelta
from threading import RLock
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app import config
from app.db import get_db, init_db
from app.repositories.workouts import (
    get_previous_set_for_exercise,
    get_workout_details,
)
from app.services.backup_service import (
    build_backup_payload,
    get_table_counts,
    reset_database_data,
    restore_backup_payload,
)
from app.services.analysis_service import (
    estimated_1rm,
    get_exercise_load_profile,
    workout_load_label,
)
from app.services.stats_service import (
    build_stats,
    build_stats2_charts,
    calculate_workout_load_metrics,
    parse_limit,
)


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.DEBUG),
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "[%(name)s] "
            "%(message)s"
        ),
    )


configure_logging()

logger = logging.getLogger("training_log")
access_logger = logging.getLogger("training_log.access")

app = FastAPI(title="Training Log")
templates = Jinja2Templates(directory="app/templates")

def load_label_class(load_label: str | None) -> str:
    if load_label == "Light":
        return "metric-green"
    if load_label == "Medium":
        return "metric-yellow"
    if load_label == "Hard":
        return "metric-orange"
    if load_label == "Very hard":
        return "metric-red"

    return "metric-neutral"

def load_score_status_class(value: int | float | str | None) -> str:
    if value is None or value == "":
        return "metric-neutral"

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return "metric-neutral"

    return load_label_class(workout_load_label(numeric_value))

def recommendation_status_class(status: str | None) -> str:
    if status == "progress":
        return "metric-green"

    if status == "progress_carefully":
        return "metric-lime"

    if status == "repeat":
        return "metric-yellow"

    if status == "deload":
        return "metric-orange"

    if status == "recovery":
        return "metric-red"

    return "metric-neutral"

ACTIVE_WORKOUT_DRAFT: dict[str, Any] | None = None
DRAFT_LOCK = RLock()

def build_workout_analysis(
    workout_id: int,
    workout_exercises: list[dict[str, Any]],
) -> dict[str, Any]:
    exercise_analyses: list[dict[str, Any]] = []
    all_prs: list[dict[str, Any]] = []

    with get_db() as conn:
        current_workout = conn.execute(
            """
            SELECT id, created_at
            FROM workouts
            WHERE id = ?
            """,
            (workout_id,),
        ).fetchone()

        if not current_workout:
            return {
                "exercises": [],
                "prs": [],
            }

        current_created_at = current_workout["created_at"]

        for item in workout_exercises:
            exercise_id = int(item["exercise_id"])
            exercise_name = str(item["exercise_name"])
            sets = item["sets"]

            current_max_weight: float | None = None
            current_max_reps: int | None = None
            current_best_e1rm: float | None = None
            current_best_e1rm_set: dict[str, Any] | None = None
            current_best_set: dict[str, Any] | None = None
            current_best_set_score = -1.0
            current_total_volume = float(item["total_volume"])

            for set_row in sets:
                weight = float(set_row["weight"])
                reps = int(set_row["reps"])
                volume = weight * reps

                if current_max_weight is None or weight > current_max_weight:
                    current_max_weight = weight

                if current_max_reps is None or reps > current_max_reps:
                    current_max_reps = reps

                e1rm = estimated_1rm(weight, reps)
                if e1rm is not None:
                    if current_best_e1rm is None or e1rm > current_best_e1rm:
                        current_best_e1rm = e1rm
                        current_best_e1rm_set = {
                            "weight": weight,
                            "reps": reps,
                        }

                # Best set display:
                # prefer reliable e1RM set for weighted exercises;
                # otherwise fall back to volume/reps.
                if e1rm is not None:
                    score = e1rm
                elif weight > 0:
                    score = volume
                else:
                    score = reps

                if score > current_best_set_score:
                    current_best_set_score = score
                    current_best_set = {
                        "weight": weight,
                        "reps": reps,
                    }

            previous_rows = conn.execute(
                """
                SELECT
                    w.id AS workout_id,
                    w.created_at,
                    se.weight,
                    se.reps
                FROM set_entries se
                JOIN workout_exercises we ON we.id = se.workout_exercise_id
                JOIN workouts w ON w.id = we.workout_id
                WHERE we.exercise_id = ?
                  AND (
                        w.created_at < ?
                        OR (w.created_at = ? AND w.id < ?)
                  )
                ORDER BY w.created_at ASC, w.id ASC, se.set_number ASC, se.id ASC
                """,
                (
                    exercise_id,
                    current_created_at,
                    current_created_at,
                    workout_id,
                ),
            ).fetchall()

            previous_max_weight: float | None = None
            previous_max_reps: int | None = None
            previous_best_e1rm: float | None = None

            for row in previous_rows:
                weight = float(row["weight"])
                reps = int(row["reps"])

                if previous_max_weight is None or weight > previous_max_weight:
                    previous_max_weight = weight

                if previous_max_reps is None or reps > previous_max_reps:
                    previous_max_reps = reps

                e1rm = estimated_1rm(weight, reps)
                if e1rm is not None:
                    if previous_best_e1rm is None or e1rm > previous_best_e1rm:
                        previous_best_e1rm = e1rm

            previous_volume_rows = conn.execute(
                """
                SELECT
                    w.id AS workout_id,
                    SUM(se.weight * se.reps) AS exercise_volume
                FROM set_entries se
                JOIN workout_exercises we ON we.id = se.workout_exercise_id
                JOIN workouts w ON w.id = we.workout_id
                WHERE we.exercise_id = ?
                  AND (
                        w.created_at < ?
                        OR (w.created_at = ? AND w.id < ?)
                  )
                GROUP BY w.id
                """,
                (
                    exercise_id,
                    current_created_at,
                    current_created_at,
                    workout_id,
                ),
            ).fetchall()

            previous_best_volume: float | None = None
            for row in previous_volume_rows:
                volume = float(row["exercise_volume"] or 0)
                if previous_best_volume is None or volume > previous_best_volume:
                    previous_best_volume = volume

            pr_flags: list[str] = []

            if (
                current_max_weight is not None
                and current_max_weight > 0
                and previous_max_weight is not None
                and current_max_weight > previous_max_weight
            ):
                pr_flags.append("Weight PR")

            if (
                current_max_reps is not None
                and previous_max_reps is not None
                and current_max_reps > previous_max_reps
            ):
                pr_flags.append("Rep PR")

            if (
                current_best_e1rm is not None
                and previous_best_e1rm is not None
                and current_best_e1rm > previous_best_e1rm
            ):
                pr_flags.append("e1RM PR")

            if (
                current_total_volume > 0
                and previous_best_volume is not None
                and current_total_volume > previous_best_volume
            ):
                pr_flags.append("Volume PR")

            exercise_analysis = {
                "exercise_id": exercise_id,
                "exercise_name": exercise_name,
                "best_set": current_best_set,
                "best_e1rm": current_best_e1rm,
                "best_e1rm_set": current_best_e1rm_set,
                "pr_flags": pr_flags,
            }

            exercise_analyses.append(exercise_analysis)

            for flag in pr_flags:
                all_prs.append(
                    {
                        "exercise_name": exercise_name,
                        "type": flag,
                    }
                )

    return {
        "exercises": exercise_analyses,
        "prs": all_prs,
    }

def format_datetime(value: str | None) -> str:
    if not value:
        return "—"

    return value.replace("T", " ")[:16]


def datetime_local_value(value: str | None) -> str:
    if not value:
        return ""

    return value[:16]


def format_duration(value: int | str | None) -> str:
    if value is None or value == "":
        return "—"

    try:
        total_seconds = max(0, int(value))
    except (TypeError, ValueError):
        return "—"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    return f"{minutes}:{seconds:02d}"


RPE_EMOJIS: dict[int, str] = {
    1: "😄",
    2: "🙂",
    3: "🙂",
    4: "😐",
    5: "😐",
    6: "😟",
    7: "😣",
    8: "😫",
    9: "🥵",
    10: "😵",
}


def rpe_option_label(value: int | str | None) -> str:
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        return "RPE"

    emoji = RPE_EMOJIS.get(numeric_value, "😐")
    return f"{emoji} {numeric_value}"


def metric_status_class(value: int | float | str | None) -> str:
    if value is None or value == "":
        return "metric-neutral"

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return "metric-neutral"

    if numeric_value <= 2:
        return "metric-green"
    if numeric_value <= 4:
        return "metric-lime"
    if numeric_value <= 6:
        return "metric-yellow"
    if numeric_value <= 8:
        return "metric-orange"

    return "metric-red"


def parse_optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None

    return int(value)

def redirect_after_change(
    return_to: str | None = None,
    workout_id: int | None = None,
):
    if return_to == "edit_workout" and workout_id is not None:
        return RedirectResponse(f"/workouts/{workout_id}/edit", status_code=303)

    return RedirectResponse("/", status_code=303)

templates.env.filters["format_datetime"] = format_datetime
templates.env.filters["datetime_local_value"] = datetime_local_value
templates.env.filters["format_duration"] = format_duration
templates.env.filters["rpe_option_label"] = rpe_option_label
templates.env.filters["metric_status_class"] = metric_status_class
templates.env.filters["load_label_class"] = load_label_class
templates.env.filters["load_score_status_class"] = load_score_status_class
templates.env.filters["recommendation_status_class"] = recommendation_status_class


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid4().hex[:8])
    start_time = time.perf_counter()

    client_host = request.client.host if request.client else "-"
    method = request.method
    path = request.url.path

    access_logger.info(
        "request.start request_id=%s method=%s path=%s client=%s",
        request_id,
        method,
        path,
        client_host,
    )

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start_time) * 1000
        access_logger.exception(
            "request.error request_id=%s method=%s path=%s client=%s duration_ms=%.2f",
            request_id,
            method,
            path,
            client_host,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start_time) * 1000
    access_logger.info(
        "request.end request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
        request_id,
        method,
        path,
        response.status_code,
        duration_ms,
    )

    response.headers["X-Request-ID"] = request_id
    return response


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "app.startup db_path=%s log_level=%s",
        config.DB_PATH,
        config.LOG_LEVEL,
    )
    init_db()
    logger.info("app.ready")


def get_active_workout_draft() -> dict[str, Any] | None:
    with DRAFT_LOCK:
        return ACTIVE_WORKOUT_DRAFT


def create_workout_draft() -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")

    return {
        "started_at": now,
        "session_rpe": None,
        "lower_back_pain": None,
        "workout_exercises": [],
        "next_workout_exercise_id": 1,
        "next_set_id": 1,
    }


def get_draft_workout_exercise(
    draft: dict[str, Any],
    draft_exercise_id: int,
) -> dict[str, Any] | None:
    for item in draft["workout_exercises"]:
        if int(item["id"]) == draft_exercise_id:
            return item

    return None


def get_draft_set(
    draft: dict[str, Any],
    draft_set_id: int,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for item in draft["workout_exercises"]:
        for set_entry in item["sets"]:
            if int(set_entry["id"]) == draft_set_id:
                return item, set_entry

    return None


def renumber_draft_sets(draft_exercise: dict[str, Any]) -> None:
    for index, set_entry in enumerate(draft_exercise["sets"], start=1):
        set_entry["set_number"] = index


def get_draft_workout_details(draft: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for item in sorted(draft["workout_exercises"], key=lambda x: (x["position"], x["id"])):
        sets = item["sets"]
        total_volume = sum(float(s["weight"]) * int(s["reps"]) for s in sets)
        total_reps = sum(int(s["reps"]) for s in sets)

        if sets:
            last_set = sets[-1]
            default_weight = float(last_set["weight"])
            default_reps = int(last_set["reps"])
        else:
            previous_set = get_previous_set_for_exercise(
                exercise_id=int(item["exercise_id"]),
                current_workout_id=0,
            )

            if previous_set:
                default_weight = float(previous_set["weight"])
                default_reps = int(previous_set["reps"])
            else:
                default_weight = 0.0
                default_reps = 10

        result.append(
            {
                "workout_exercise_id": item["id"],
                "exercise_id": item["exercise_id"],
                "exercise_name": item["exercise_name"],
                "position": item["position"],
                "sets": sets,
                "total_volume": total_volume,
                "total_reps": total_reps,
                "default_weight": default_weight,
                "default_reps": default_reps,
            }
        )

    return result


def calculate_draft_elapsed_seconds(draft: dict[str, Any]) -> int:
    try:
        started_at = datetime.fromisoformat(draft["started_at"])
    except (KeyError, TypeError, ValueError):
        return 0

    return max(0, int((datetime.now() - started_at).total_seconds()))


def save_workout_draft_to_db(draft: dict[str, Any]) -> int:
    started_at_raw = str(draft["started_at"])
    finished_at = datetime.now().isoformat(timespec="seconds")

    try:
        started_at_dt = datetime.fromisoformat(started_at_raw)
        finished_at_dt = datetime.fromisoformat(finished_at)
        duration_seconds = max(0, int((finished_at_dt - started_at_dt).total_seconds()))
    except ValueError:
        duration_seconds = None

    with get_db() as conn:
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

        workout_id = int(workout_cursor.lastrowid)

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

    logger.info(
        "workout.draft.save workout_id=%s exercises=%s duration_seconds=%s",
        workout_id,
        len(draft["workout_exercises"]),
        duration_seconds,
    )

    return workout_id

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
            current_workout_id=workout_id,
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


def get_best_reps_at_weight(sets: list[dict[str, Any]], target_weight: float) -> int | None:
    matching_reps = [
        int(set_row["reps"])
        for set_row in sets
        if abs(float(set_row["weight"]) - target_weight) < 0.001
    ]

    if not matching_reps:
        return None

    return max(matching_reps)


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

    usual_interval_days = average(intervals)
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


def calculate_readiness_status(
    recovery_context: dict[str, Any],
    last_workout: sqlite3.Row,
    last_load_metrics: dict[str, Any],
) -> dict[str, Any]:
    score = 50
    reasons: list[str] = []

    hours_since_previous = recovery_context.get("hours_since_previous_workout")
    last_7d = recovery_context.get("last_7d", {})

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
            """
            SELECT *
            FROM workouts
            ORDER BY created_at DESC, id DESC
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
        current_workout_id=int(last_workout["id"]),
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

def get_weight_options(extra_weights: list[float] | None = None) -> list[float]:
    options: set[float] = set()

    # 0–70 kg, step 1 kg
    value = 0
    while value <= 70:
        options.add(float(value))
        value += 1

    # 75–150 kg, step 5 kg
    value = 75
    while value <= 150:
        options.add(float(value))
        value += 5

    if extra_weights:
        for weight in extra_weights:
            options.add(round(float(weight), 2))

    return sorted(options)

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

@app.get("/")
def index(request: Request):
    with get_db() as conn:
        exercises = conn.execute(
            "SELECT * FROM exercises ORDER BY name ASC"
        ).fetchall()

    draft = get_active_workout_draft()

    if draft is None:
        logger.debug("page.index no_active_workout")

        recovery_context = build_recovery_context()
        next_recommendation = build_next_workout_recommendation(
            recovery_context=recovery_context,
        )

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "active_workout": False,
                "workout": None,
                "exercises": exercises,
                "workout_exercises": [],
                "reps_options": range(1, 51),
                "weight_options": get_weight_options(),
                "total_volume": 0,
                "total_reps": 0,
                "total_sets": 0,
                "active_elapsed_seconds": 0,
                "load_metrics": None,
                "recovery_context": build_recovery_context(),
                "next_recommendation": next_recommendation,
            },
        )

    workout = {
        "id": "draft",
        "created_at": draft["started_at"],
        "started_at": draft["started_at"],
        "session_rpe": draft.get("session_rpe"),
        "lower_back_pain": draft.get("lower_back_pain"),
    }

    workout_exercises = get_draft_workout_details(draft)

    total_volume = sum(item["total_volume"] for item in workout_exercises)
    total_reps = sum(item["total_reps"] for item in workout_exercises)
    total_sets = sum(len(item["sets"]) for item in workout_exercises)

    load_metrics = calculate_workout_load_metrics(
        workout_exercises=workout_exercises,
        session_rpe=workout["session_rpe"],
        current_workout_id=None,
    )

    existing_weights: list[float] = []
    for item in workout_exercises:
        existing_weights.append(float(item["default_weight"]))
        for set_row in item["sets"]:
            existing_weights.append(float(set_row["weight"]))

    active_elapsed_seconds = calculate_draft_elapsed_seconds(draft)
    recovery_context = build_recovery_context(as_of=draft["started_at"])

    logger.debug(
        "page.index active_draft exercises=%s sets=%s elapsed_seconds=%s",
        len(workout_exercises),
        total_sets,
        active_elapsed_seconds,
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_workout": True,
            "workout": workout,
            "exercises": exercises,
            "workout_exercises": workout_exercises,
            "reps_options": range(1, 51),
            "weight_options": get_weight_options(extra_weights=existing_weights),
            "total_volume": total_volume,
            "total_reps": total_reps,
            "total_sets": total_sets,
            "active_elapsed_seconds": active_elapsed_seconds,
            "load_metrics": load_metrics,
            "recovery_context": recovery_context,
            "next_recommendation": None,
        },
    )

@app.post("/exercises")
def add_exercise(name: str = Form(...)):
    clean_name = name.strip()

    if clean_name:
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO exercises (name) VALUES (?)",
                (clean_name,),
            )
        logger.info("exercise.ensure name=%s", clean_name)
    else:
        logger.warning("exercise.create.skipped reason=empty_name")

    return RedirectResponse("/", status_code=303)




@app.post("/workouts/start")
def start_workout():
    global ACTIVE_WORKOUT_DRAFT

    with DRAFT_LOCK:
        if ACTIVE_WORKOUT_DRAFT is None:
            ACTIVE_WORKOUT_DRAFT = create_workout_draft()
            logger.info(
                "workout.draft.start started_at=%s",
                ACTIVE_WORKOUT_DRAFT["started_at"],
            )
        else:
            logger.info(
                "workout.draft.start.ignored reason=already_active started_at=%s",
                ACTIVE_WORKOUT_DRAFT["started_at"],
            )

    return RedirectResponse("/", status_code=303)


@app.post("/draft/metadata")
def update_draft_metadata(
    session_rpe: str | None = Form(None),
    lower_back_pain: str | None = Form(None),
):
    parsed_session_rpe = parse_optional_int(session_rpe)
    parsed_lower_back_pain = parse_optional_int(lower_back_pain)

    with DRAFT_LOCK:
        draft = ACTIVE_WORKOUT_DRAFT
        if draft is None:
            logger.warning("workout.draft.metadata.no_active")
            return RedirectResponse("/", status_code=303)

        draft["session_rpe"] = parsed_session_rpe
        draft["lower_back_pain"] = parsed_lower_back_pain

    logger.info(
        "workout.draft.metadata.update session_rpe=%s lower_back_pain=%s",
        session_rpe,
        lower_back_pain,
    )
    return RedirectResponse("/", status_code=303)


@app.post("/draft/exercise")
def add_exercise_to_draft(exercise_id: int = Form(...)):
    with get_db() as conn:
        exercise = conn.execute(
            "SELECT * FROM exercises WHERE id = ?",
            (exercise_id,),
        ).fetchone()

    if not exercise:
        logger.warning("workout.draft.exercise.add.not_found exercise_id=%s", exercise_id)
        return RedirectResponse("/", status_code=303)

    with DRAFT_LOCK:
        draft = ACTIVE_WORKOUT_DRAFT
        if draft is None:
            logger.warning("workout.draft.exercise.add.no_active exercise_id=%s", exercise_id)
            return RedirectResponse("/", status_code=303)

        draft_exercise_id = int(draft["next_workout_exercise_id"])
        draft["next_workout_exercise_id"] = draft_exercise_id + 1
        position = len(draft["workout_exercises"]) + 1

        draft["workout_exercises"].append(
            {
                "id": draft_exercise_id,
                "exercise_id": int(exercise["id"]),
                "exercise_name": str(exercise["name"]),
                "position": position,
                "sets": [],
            }
        )

    logger.info(
        "workout.draft.exercise.add draft_exercise_id=%s exercise_id=%s position=%s",
        draft_exercise_id,
        exercise_id,
        position,
    )
    return RedirectResponse("/", status_code=303)


@app.post("/draft-exercises/{draft_exercise_id}/sets")
def add_set_to_draft(
    draft_exercise_id: int,
    weight: float = Form(...),
    reps: int = Form(...),
):
    with DRAFT_LOCK:
        draft = ACTIVE_WORKOUT_DRAFT
        if draft is None:
            logger.warning("workout.draft.set.add.no_active draft_exercise_id=%s", draft_exercise_id)
            return RedirectResponse("/", status_code=303)

        draft_exercise = get_draft_workout_exercise(draft, draft_exercise_id)
        if not draft_exercise:
            logger.warning("workout.draft.set.add.exercise_not_found draft_exercise_id=%s", draft_exercise_id)
            return RedirectResponse("/", status_code=303)

        set_id = int(draft["next_set_id"])
        draft["next_set_id"] = set_id + 1
        set_number = len(draft_exercise["sets"]) + 1

        draft_exercise["sets"].append(
            {
                "id": set_id,
                "set_number": set_number,
                "weight": weight,
                "reps": reps,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )

    logger.info(
        "workout.draft.set.add set_id=%s draft_exercise_id=%s set_number=%s weight=%s reps=%s",
        set_id,
        draft_exercise_id,
        set_number,
        weight,
        reps,
    )
    return RedirectResponse("/", status_code=303)


@app.post("/draft-exercises/{draft_exercise_id}/sets/duplicate")
def duplicate_draft_set(draft_exercise_id: int):
    with DRAFT_LOCK:
        draft = ACTIVE_WORKOUT_DRAFT
        if draft is None:
            logger.warning("workout.draft.set.duplicate.no_active draft_exercise_id=%s", draft_exercise_id)
            return RedirectResponse("/", status_code=303)

        draft_exercise = get_draft_workout_exercise(draft, draft_exercise_id)
        if not draft_exercise:
            logger.warning("workout.draft.set.duplicate.exercise_not_found draft_exercise_id=%s", draft_exercise_id)
            return RedirectResponse("/", status_code=303)

        if draft_exercise["sets"]:
            source_set = draft_exercise["sets"][-1]
            weight = float(source_set["weight"])
            reps = int(source_set["reps"])
        else:
            previous_set = get_previous_set_for_exercise(
                exercise_id=int(draft_exercise["exercise_id"]),
                current_workout_id=0,
            )
            if not previous_set:
                logger.warning("workout.draft.set.duplicate.no_source draft_exercise_id=%s", draft_exercise_id)
                return RedirectResponse("/", status_code=303)

            weight = float(previous_set["weight"])
            reps = int(previous_set["reps"])

        set_id = int(draft["next_set_id"])
        draft["next_set_id"] = set_id + 1
        set_number = len(draft_exercise["sets"]) + 1

        draft_exercise["sets"].append(
            {
                "id": set_id,
                "set_number": set_number,
                "weight": weight,
                "reps": reps,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )

    logger.info(
        "workout.draft.set.duplicate set_id=%s draft_exercise_id=%s set_number=%s weight=%s reps=%s",
        set_id,
        draft_exercise_id,
        set_number,
        weight,
        reps,
    )
    return RedirectResponse("/", status_code=303)


@app.post("/draft-sets/{draft_set_id}/delete")
def delete_draft_set(draft_set_id: int):
    with DRAFT_LOCK:
        draft = ACTIVE_WORKOUT_DRAFT
        if draft is None:
            logger.warning("workout.draft.set.delete.no_active set_id=%s", draft_set_id)
            return RedirectResponse("/", status_code=303)

        found = get_draft_set(draft, draft_set_id)
        if not found:
            logger.warning("workout.draft.set.delete.not_found set_id=%s", draft_set_id)
            return RedirectResponse("/", status_code=303)

        draft_exercise, _ = found
        draft_exercise["sets"] = [
            set_entry for set_entry in draft_exercise["sets"]
            if int(set_entry["id"]) != draft_set_id
        ]
        renumber_draft_sets(draft_exercise)

    logger.info("workout.draft.set.delete set_id=%s", draft_set_id)
    return RedirectResponse("/", status_code=303)


@app.post("/draft-exercises/{draft_exercise_id}/delete")
def delete_draft_exercise(draft_exercise_id: int):
    with DRAFT_LOCK:
        draft = ACTIVE_WORKOUT_DRAFT
        if draft is None:
            logger.warning("workout.draft.exercise.delete.no_active draft_exercise_id=%s", draft_exercise_id)
            return RedirectResponse("/", status_code=303)

        before_count = len(draft["workout_exercises"])
        draft["workout_exercises"] = [
            item for item in draft["workout_exercises"]
            if int(item["id"]) != draft_exercise_id
        ]

        for index, item in enumerate(draft["workout_exercises"], start=1):
            item["position"] = index

    logger.info(
        "workout.draft.exercise.delete draft_exercise_id=%s deleted=%s",
        draft_exercise_id,
        before_count != len(draft["workout_exercises"]),
    )
    return RedirectResponse("/", status_code=303)

@app.post("/workouts/{workout_id}/exercise")
def add_exercise_to_workout(
    workout_id: int,
    exercise_id: int = Form(...),
    return_to: str | None = Form(None),
):
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

        logger.info(
            "workout.exercise.add workout_id=%s workout_exercise_id=%s exercise_id=%s position=%s return_to=%s",
            workout_id,
            cursor.lastrowid,
            exercise_id,
            next_position,
            return_to,
        )

    return redirect_after_change(return_to, workout_id)


@app.post("/workout-exercises/{workout_exercise_id}/sets")
def add_set(
    workout_exercise_id: int,
    weight: float = Form(...),
    reps: int = Form(...),
    return_to: str | None = Form(None),
):
    with get_db() as conn:
        workout_exercise = conn.execute(
            """
            SELECT workout_id
            FROM workout_exercises
            WHERE id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()

        if not workout_exercise:
            logger.warning(
                "set.add.not_found workout_exercise_id=%s return_to=%s",
                workout_exercise_id,
                return_to,
            )
            return RedirectResponse("/", status_code=303)

        workout_id = int(workout_exercise["workout_id"])

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
            INSERT INTO set_entries
                (workout_exercise_id, set_number, weight, reps, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                workout_exercise_id,
                next_set_number,
                weight,
                reps,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        logger.info(
            "set.add set_id=%s workout_id=%s workout_exercise_id=%s set_number=%s weight=%s reps=%s return_to=%s",
            cursor.lastrowid,
            workout_id,
            workout_exercise_id,
            next_set_number,
            weight,
            reps,
            return_to,
        )

    return redirect_after_change(return_to, workout_id)


@app.post("/sets/{set_id}/delete")
def delete_set(
    set_id: int,
    return_to: str | None = Form(None),
):
    workout_id: int | None = None

    with get_db() as conn:
        set_row = conn.execute(
            """
            SELECT
                se.workout_exercise_id,
                we.workout_id
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            WHERE se.id = ?
            """,
            (set_id,),
        ).fetchone()

        if set_row:
            workout_exercise_id = int(set_row["workout_exercise_id"])
            workout_id = int(set_row["workout_id"])

            conn.execute(
                """
                DELETE FROM set_entries
                WHERE id = ?
                """,
                (set_id,),
            )

            renumber_sets(conn, workout_exercise_id)
            logger.info(
                "set.delete set_id=%s workout_id=%s workout_exercise_id=%s return_to=%s",
                set_id,
                workout_id,
                workout_exercise_id,
                return_to,
            )
        else:
            logger.warning("set.delete.not_found set_id=%s return_to=%s", set_id, return_to)

    return redirect_after_change(return_to, workout_id)


@app.post("/workout-exercises/{workout_exercise_id}/delete")
def delete_workout_exercise(
    workout_exercise_id: int,
    return_to: str | None = Form(None),
):
    workout_id: int | None = None

    with get_db() as conn:
        workout_exercise = conn.execute(
            """
            SELECT workout_id
            FROM workout_exercises
            WHERE id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()

        if workout_exercise:
            workout_id = int(workout_exercise["workout_id"])

            conn.execute(
                """
                DELETE FROM workout_exercises
                WHERE id = ?
                """,
                (workout_exercise_id,),
            )
            logger.info(
                "workout.exercise.delete workout_exercise_id=%s workout_id=%s return_to=%s",
                workout_exercise_id,
                workout_id,
                return_to,
            )
        else:
            logger.warning(
                "workout.exercise.delete.not_found workout_exercise_id=%s return_to=%s",
                workout_exercise_id,
                return_to,
            )

    return redirect_after_change(return_to, workout_id)


@app.post("/workouts/finish")
def finish_workout():
    global ACTIVE_WORKOUT_DRAFT

    with DRAFT_LOCK:
        if ACTIVE_WORKOUT_DRAFT is None:
            logger.warning("workout.draft.finish.no_active")
            return RedirectResponse("/", status_code=303)

        draft = deepcopy(ACTIVE_WORKOUT_DRAFT)

    workout_id = save_workout_draft_to_db(draft)

    with DRAFT_LOCK:
        ACTIVE_WORKOUT_DRAFT = None

    logger.info("workout.draft.finish workout_id=%s", workout_id)
    return RedirectResponse(f"/workouts/{workout_id}", status_code=303)


@app.get("/workouts/{workout_id}/edit")
def edit_workout_page(request: Request, workout_id: int):
    with get_db() as conn:
        workout = conn.execute(
            """
            SELECT *
            FROM workouts
            WHERE id = ?
            """,
            (workout_id,),
        ).fetchone()

        exercises = conn.execute(
            """
            SELECT *
            FROM exercises
            ORDER BY name ASC
            """
        ).fetchall()

    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    workout_exercises = get_workout_details(workout_id)

    total_volume = sum(item["total_volume"] for item in workout_exercises)
    total_reps = sum(item["total_reps"] for item in workout_exercises)
    total_sets = sum(len(item["sets"]) for item in workout_exercises)
    analysis = build_workout_analysis(workout_id, workout_exercises)

    load_metrics = calculate_workout_load_metrics(
        workout_exercises=workout_exercises,
        session_rpe=workout["session_rpe"],
        current_workout_id=workout_id,
    )

    existing_weights: list[float] = []
    for item in workout_exercises:
        for set_row in item["sets"]:
            existing_weights.append(float(set_row["weight"]))

    logger.debug(
        "page.workout_edit workout_id=%s exercises=%s sets=%s",
        workout_id,
        len(workout_exercises),
        total_sets,
    )

    return templates.TemplateResponse(
        "edit_workout.html",
        {
            "request": request,
            "workout": workout,
            "exercises": exercises,
            "workout_exercises": workout_exercises,
            "reps_options": range(1, 51),
            "weight_options": get_weight_options(extra_weights=existing_weights),
            "total_volume": total_volume,
            "total_reps": total_reps,
            "total_sets": total_sets,
            "analysis": analysis,
            "load_metrics": load_metrics,
        },
    )


@app.post("/workouts/{workout_id}/update")
def update_workout(
    workout_id: int,
    created_at: str = Form(...),
    session_rpe: str | None = Form(None),
    lower_back_pain: str | None = Form(None),
):
    created_at = created_at.strip()

    # datetime-local sends YYYY-MM-DDTHH:MM
    if len(created_at) == 16:
        created_at = f"{created_at}:00"

    workout_date = created_at[:10]

    with get_db() as conn:
        parsed_session_rpe = parse_optional_int(session_rpe)
        parsed_lower_back_pain = parse_optional_int(lower_back_pain)

        existing_workout = conn.execute(
            "SELECT finished_at FROM workouts WHERE id = ?",
            (workout_id,),
        ).fetchone()

        duration_seconds = None
        if existing_workout and existing_workout["finished_at"]:
            try:
                duration_seconds = max(
                    0,
                    int(
                        (
                            datetime.fromisoformat(existing_workout["finished_at"])
                            - datetime.fromisoformat(created_at)
                        ).total_seconds()
                    ),
                )
            except ValueError:
                duration_seconds = None

        conn.execute(
            """
            UPDATE workouts
            SET created_at = ?,
                workout_date = ?,
                session_rpe = ?,
                lower_back_pain = ?,
                duration_seconds = COALESCE(?, duration_seconds)
            WHERE id = ?
            """,
            (
                created_at,
                workout_date,
                parsed_session_rpe,
                parsed_lower_back_pain,
                duration_seconds,
                workout_id,
            ),
        )

    logger.info(
        "workout.update workout_id=%s created_at=%s workout_date=%s session_rpe=%s lower_back_pain=%s duration_seconds=%s",
        workout_id,
        created_at,
        workout_date,
        parsed_session_rpe,
        parsed_lower_back_pain,
        duration_seconds,
    )
    return RedirectResponse(f"/workouts/{workout_id}/edit", status_code=303)


@app.post("/workouts/{workout_id}/delete")
def delete_workout(workout_id: int):
    with get_db() as conn:
        conn.execute(
            """
            DELETE FROM workouts
            WHERE id = ?
            """,
            (workout_id,),
        )

    logger.warning("workout.delete workout_id=%s", workout_id)
    return RedirectResponse("/history", status_code=303)


@app.get("/backup")
def backup_page(request: Request):
    with get_db() as conn:
        counts = get_table_counts(conn)

    logger.debug("page.backup counts=%s", counts)
    return templates.TemplateResponse(
        "backup.html",
        {
            "request": request,
            "counts": counts,
            "reset": request.query_params.get("reset") == "1",
        },
    )


@app.get("/backup/export.json")
def export_backup():
    payload = build_backup_payload()
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    logger.info("backup.export filename_timestamp=%s size_bytes=%s", timestamp, len(content.encode("utf-8")))
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="training-log-backup-{timestamp}.json"'
            )
        },
    )


@app.post("/backup/import")
async def import_backup(backup_file: UploadFile = File(...)):
    raw_content = await backup_file.read()
    logger.warning(
        "backup.import.received filename=%s size_bytes=%s",
        backup_file.filename,
        len(raw_content),
    )

    try:
        payload = json.loads(raw_content.decode("utf-8-sig"))
        restore_backup_payload(payload)
    except UnicodeDecodeError as exc:
        logger.exception("backup.import.error reason=utf8_decode filename=%s", backup_file.filename)
        raise HTTPException(
            status_code=400,
            detail="Backup file must be UTF-8 JSON.",
        ) from exc
    except json.JSONDecodeError as exc:
        logger.exception("backup.import.error reason=json_decode filename=%s", backup_file.filename)
        raise HTTPException(
            status_code=400,
            detail="Backup file is not valid JSON.",
        ) from exc
    except (ValueError, sqlite3.IntegrityError) as exc:
        logger.exception("backup.import.error reason=validation_or_integrity filename=%s", backup_file.filename)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.warning("backup.import.success filename=%s", backup_file.filename)
    return RedirectResponse("/history?restored=1", status_code=303)




@app.post("/backup/reset")
def reset_database():
    global ACTIVE_WORKOUT_DRAFT

    with DRAFT_LOCK:
        ACTIVE_WORKOUT_DRAFT = None

    reset_database_data()
    logger.warning("backup.reset.success")
    return RedirectResponse("/backup?reset=1", status_code=303)

@app.get("/history")
def history(request: Request):
    with get_db() as conn:
        workouts = conn.execute(
            """
            SELECT *
            FROM workouts
            ORDER BY id DESC
            LIMIT 30
            """
        ).fetchall()

    enriched = []

    for workout in workouts:
        details = get_workout_details(workout["id"])
        load_metrics = calculate_workout_load_metrics(
            workout_exercises=details,
            session_rpe=workout["session_rpe"],
            current_workout_id=workout["id"],
        )

        enriched.append(
            {
                "workout": workout,
                "total_volume": sum(item["total_volume"] for item in details),
                "total_reps": sum(item["total_reps"] for item in details),
                "total_sets": sum(len(item["sets"]) for item in details),
                "exercises_count": len(details),
                "load_metrics": load_metrics,
            }
        )

    logger.debug("page.history workouts=%s restored=%s", len(enriched), request.query_params.get("restored") == "1")

    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "items": enriched,
            "restored": request.query_params.get("restored") == "1",
        },
    )

@app.get("/workouts/{workout_id}")
def workout_detail(request: Request, workout_id: int):
    with get_db() as conn:
        workout = conn.execute(
            """
            SELECT *
            FROM workouts
            WHERE id = ?
            """,
            (workout_id,),
        ).fetchone()

    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    workout_exercises = get_workout_details(workout_id)

    total_volume = sum(item["total_volume"] for item in workout_exercises)
    total_reps = sum(item["total_reps"] for item in workout_exercises)
    total_sets = sum(len(item["sets"]) for item in workout_exercises)
    analysis = build_workout_analysis(workout_id, workout_exercises)

    load_metrics = calculate_workout_load_metrics(
        workout_exercises=workout_exercises,
        session_rpe=workout["session_rpe"],
        current_workout_id=workout_id,
    )

    logger.debug(
        "page.workout_detail workout_id=%s exercises=%s sets=%s",
        workout_id,
        len(workout_exercises),
        total_sets,
    )

    return templates.TemplateResponse(
        "workout.html",
        {
            "request": request,
            "workout": workout,
            "workout_exercises": workout_exercises,
            "total_volume": total_volume,
            "total_reps": total_reps,
            "total_sets": total_sets,
            "analysis": analysis,
            "load_metrics": load_metrics,
        },
    )

@app.post("/workout-exercises/{workout_exercise_id}/sets/duplicate")
def duplicate_set(
    workout_exercise_id: int,
    return_to: str | None = Form(None),
):
    with get_db() as conn:
        workout_exercise = conn.execute(
            """
            SELECT workout_id, exercise_id
            FROM workout_exercises
            WHERE id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()

        if not workout_exercise:
            logger.warning(
                "set.duplicate.not_found workout_exercise_id=%s return_to=%s",
                workout_exercise_id,
                return_to,
            )
            return RedirectResponse("/", status_code=303)

        workout_id = int(workout_exercise["workout_id"])

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

        if not source_set:
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

        if not source_set:
            logger.warning(
                "set.duplicate.no_source workout_id=%s workout_exercise_id=%s return_to=%s",
                workout_id,
                workout_exercise_id,
                return_to,
            )
            return redirect_after_change(return_to, workout_id)

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
            INSERT INTO set_entries
                (workout_exercise_id, set_number, weight, reps, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                workout_exercise_id,
                next_set_number,
                float(source_set["weight"]),
                int(source_set["reps"]),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        logger.info(
            "set.duplicate set_id=%s workout_id=%s workout_exercise_id=%s set_number=%s weight=%s reps=%s return_to=%s",
            cursor.lastrowid,
            workout_id,
            workout_exercise_id,
            next_set_number,
            float(source_set["weight"]),
            int(source_set["reps"]),
            return_to,
        )

    return redirect_after_change(return_to, workout_id)


@app.post("/workouts/{workout_id}/metadata")
def update_workout_metadata(
    workout_id: int,
    session_rpe: str | None = Form(None),
    lower_back_pain: str | None = Form(None),
):
    parsed_session_rpe = parse_optional_int(session_rpe)
    parsed_lower_back_pain = parse_optional_int(lower_back_pain)

    with get_db() as conn:
        conn.execute(
            """
            UPDATE workouts
            SET session_rpe = ?,
                lower_back_pain = ?
            WHERE id = ?
            """,
            (parsed_session_rpe, parsed_lower_back_pain, workout_id),
        )

    logger.info(
        "workout.metadata.update workout_id=%s session_rpe=%s lower_back_pain=%s",
        workout_id,
        parsed_session_rpe,
        parsed_lower_back_pain,
    )
    return RedirectResponse("/", status_code=303)


@app.get("/sets/{set_id}/edit")
def edit_set_page(request: Request, set_id: int):
    with get_db() as conn:
        set_row = conn.execute(
            """
            SELECT
                se.id,
                se.workout_exercise_id,
                se.set_number,
                se.weight,
                se.reps,
                we.workout_id,
                e.name AS exercise_name
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            JOIN exercises e ON e.id = we.exercise_id
            WHERE se.id = ?
            """,
            (set_id,),
        ).fetchone()

    if not set_row:
        raise HTTPException(status_code=404, detail="Set not found")

    logger.debug("page.set_edit set_id=%s workout_id=%s", set_id, set_row["workout_id"])

    return templates.TemplateResponse(
        "edit_set.html",
        {
            "request": request,
            "set": set_row,
            "weight_options": get_weight_options(
                extra_weights=[float(set_row["weight"])]
            ),
            "reps_options": range(1, 51),
        },
    )


@app.post("/sets/{set_id}/update")
def update_set(
    set_id: int,
    weight: float = Form(...),
    reps: int = Form(...),
    return_to: str | None = Form(None),
):
    with get_db() as conn:
        set_row = conn.execute(
            """
            SELECT we.workout_id
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            WHERE se.id = ?
            """,
            (set_id,),
        ).fetchone()

        if not set_row:
            logger.warning("set.update.not_found set_id=%s return_to=%s", set_id, return_to)
            return RedirectResponse("/", status_code=303)

        workout_id = int(set_row["workout_id"])

        conn.execute(
            """
            UPDATE set_entries
            SET weight = ?,
                reps = ?
            WHERE id = ?
            """,
            (weight, reps, set_id),
        )

    logger.info(
        "set.update set_id=%s workout_id=%s weight=%s reps=%s return_to=%s",
        set_id,
        workout_id,
        weight,
        reps,
        return_to,
    )
    return redirect_after_change(return_to, workout_id)

@app.get("/stats")
def stats_page(request: Request):
    limit = parse_limit(request.query_params.get("limit"), default=30)
    stats = build_stats(limit=limit)
    charts = build_stats2_charts(stats)

    logger.debug(
        "page.stats workouts=%s exercises=%s limit=%s",
        len(stats["workouts"]),
        len(stats["exercise_stats"]),
        "all" if limit is None else limit,
    )

    return templates.TemplateResponse(
        "stats.html",
        {
            "request": request,
            "stats": stats,
            "charts": charts,
            "limit": limit,
        },
    )

@app.get("/stats2")
def stats2_page(request: Request):
    limit = parse_limit(request.query_params.get("limit"), default=30)
    stats = build_stats(limit=limit)
    charts = build_stats2_charts(stats)

    logger.debug(
        "page.stats2 workouts=%s exercises=%s limit=%s",
        len(stats["workouts"]),
        len(stats["exercise_stats"]),
        "all" if limit is None else limit,
    )

    return templates.TemplateResponse(
        "stats2.html",
        {
            "request": request,
            "stats": stats,
            "charts": charts,
            "limit": limit,
        },
    )
