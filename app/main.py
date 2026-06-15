import json
import logging
import sqlite3
import time
from datetime import datetime
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
    workout_load_label,
)
from app.services.stats_service import (
    build_stats,
    build_stats2_charts,
    calculate_workout_load_metrics,
    parse_limit,
)
from app.services.draft_service import (
    add_exercise_to_active_draft,
    add_set_to_active_draft,
    calculate_draft_elapsed_seconds,
    clear_active_workout_draft,
    delete_active_draft_exercise,
    delete_active_draft_set,
    duplicate_active_draft_set,
    finish_active_workout,
    get_active_workout_draft,
    get_draft_workout_details,
    start_active_workout_draft,
    update_active_draft_metadata,
)
from app.services.recovery_service import build_recovery_context
from app.services.recommendation_service import build_next_workout_recommendation


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


def get_weight_options(extra_weights: list[float] | None = None) -> list[float]:
    options: set[float] = {0.0}

    # 1-20 kg, step 0.5 kg
    value = 1
    while value <= 20:
        options.add(float(value))
        value += 0.5

    # 22.5-70 kg, step 2.5 kg
    value = 22.5
    while value <= 70:
        options.add(float(value))
        value += 2.5

    # 75-150 kg, step 5 kg
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
    start_active_workout_draft()
    return RedirectResponse("/", status_code=303)


@app.post("/draft/metadata")
def update_draft_metadata(
    session_rpe: str | None = Form(None),
    lower_back_pain: str | None = Form(None),
):
    parsed_session_rpe = parse_optional_int(session_rpe)
    parsed_lower_back_pain = parse_optional_int(lower_back_pain)

    update_active_draft_metadata(
        session_rpe=parsed_session_rpe,
        lower_back_pain=parsed_lower_back_pain,
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

    add_exercise_to_active_draft(
        exercise_id=int(exercise["id"]),
        exercise_name=str(exercise["name"]),
    )
    return RedirectResponse("/", status_code=303)


@app.post("/draft-exercises/{draft_exercise_id}/sets")
def add_set_to_draft(
    draft_exercise_id: int,
    weight: float = Form(...),
    reps: int = Form(...),
):
    add_set_to_active_draft(
        draft_exercise_id=draft_exercise_id,
        weight=weight,
        reps=reps,
    )
    return RedirectResponse("/", status_code=303)


@app.post("/draft-exercises/{draft_exercise_id}/sets/duplicate")
def duplicate_draft_set(draft_exercise_id: int):
    duplicate_active_draft_set(draft_exercise_id)
    return RedirectResponse("/", status_code=303)


@app.post("/draft-sets/{draft_set_id}/delete")
def delete_draft_set(draft_set_id: int):
    delete_active_draft_set(draft_set_id)
    return RedirectResponse("/", status_code=303)


@app.post("/draft-exercises/{draft_exercise_id}/delete")
def delete_draft_exercise(draft_exercise_id: int):
    delete_active_draft_exercise(draft_exercise_id)
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
    workout_id = finish_active_workout()
    if workout_id is None:
        return RedirectResponse("/", status_code=303)

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
    clear_active_workout_draft()
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
