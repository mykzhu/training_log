from typing import Any

from fastapi import APIRouter, HTTPException

from app.db import get_db
from app.schemas import (
    AddExerciseRequest,
    AddSetRequest,
    UpdateSetRequest,
    WorkoutMetadataUpdate,
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
    get_draft_set,
    get_draft_workout_details,
    get_draft_workout_exercise,
    start_active_workout_draft,
    update_active_draft_metadata,
    update_active_draft_set,
)
from app.services.recommendation_service import build_next_workout_recommendation
from app.services.recovery_service import build_recovery_context
from app.services.stats_service import calculate_workout_load_metrics


router = APIRouter(prefix="/api/v1/current-workout", tags=["current-workout"])


def build_current_workout_response(
    draft: dict[str, Any] | None = None,
) -> dict[str, Any]:
    draft = get_active_workout_draft() if draft is None else draft

    if draft is None:
        recovery_context = build_recovery_context()
        return {
            "active": False,
            "started_at": None,
            "elapsed_seconds": 0,
            "session_rpe": None,
            "lower_back_pain": None,
            "total_sets": 0,
            "total_reps": 0,
            "total_volume": 0,
            "exercises": [],
            "load_metrics": None,
            "recovery_context": recovery_context,
            "next_workout_recommendation": build_next_workout_recommendation(
                recovery_context=recovery_context,
            ),
        }

    workout_exercises = get_draft_workout_details(draft)
    total_volume = sum(item["total_volume"] for item in workout_exercises)
    total_reps = sum(item["total_reps"] for item in workout_exercises)
    total_sets = sum(len(item["sets"]) for item in workout_exercises)
    load_metrics = calculate_workout_load_metrics(
        workout_exercises=workout_exercises,
        session_rpe=draft["session_rpe"],
        current_workout_id=None,
    )

    return {
        "active": True,
        "started_at": draft["started_at"],
        "elapsed_seconds": calculate_draft_elapsed_seconds(draft),
        "session_rpe": draft["session_rpe"],
        "lower_back_pain": draft["lower_back_pain"],
        "total_sets": total_sets,
        "total_reps": total_reps,
        "total_volume": total_volume,
        "exercises": [
            {
                "draft_exercise_id": item["workout_exercise_id"],
                "exercise_id": item["exercise_id"],
                "exercise_name": item["exercise_name"],
                "position": item["position"],
                "sets": item["sets"],
                "total_sets": len(item["sets"]),
                "total_reps": item["total_reps"],
                "total_volume": item["total_volume"],
                "default_weight": item["default_weight"],
                "default_reps": item["default_reps"],
            }
            for item in workout_exercises
        ],
        "load_metrics": load_metrics,
        "recovery_context": None,
        "next_workout_recommendation": None,
    }


def require_active_draft() -> dict[str, Any]:
    draft = get_active_workout_draft()
    if draft is None:
        raise HTTPException(status_code=409, detail="No active workout draft.")

    return draft


def get_exercise_or_404(exercise_id: int) -> dict[str, Any]:
    with get_db() as conn:
        exercise = conn.execute(
            "SELECT * FROM exercises WHERE id = ?",
            (exercise_id,),
        ).fetchone()

    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found.")

    return dict(exercise)


@router.get("")
def get_current_workout() -> dict[str, Any]:
    return build_current_workout_response()


@router.post("/start")
def start_current_workout() -> dict[str, Any]:
    draft, _ = start_active_workout_draft()
    return build_current_workout_response(draft)


@router.patch("/metadata")
def update_current_workout_metadata(
    payload: WorkoutMetadataUpdate,
) -> dict[str, Any]:
    require_active_draft()
    update_active_draft_metadata(
        session_rpe=payload.session_rpe,
        lower_back_pain=payload.lower_back_pain,
    )
    return build_current_workout_response()


@router.post("/exercises")
def add_current_workout_exercise(
    payload: AddExerciseRequest,
) -> dict[str, Any]:
    require_active_draft()
    exercise = get_exercise_or_404(payload.exercise_id)
    add_exercise_to_active_draft(
        exercise_id=int(exercise["id"]),
        exercise_name=str(exercise["name"]),
    )
    return build_current_workout_response()


@router.delete("/exercises/{draft_exercise_id}")
def delete_current_workout_exercise(
    draft_exercise_id: int,
) -> dict[str, Any]:
    draft = require_active_draft()
    if get_draft_workout_exercise(draft, draft_exercise_id) is None:
        raise HTTPException(status_code=404, detail="Draft exercise not found.")

    delete_active_draft_exercise(draft_exercise_id)
    return build_current_workout_response()


@router.post("/exercises/{draft_exercise_id}/sets")
def add_current_workout_set(
    draft_exercise_id: int,
    payload: AddSetRequest,
) -> dict[str, Any]:
    draft = require_active_draft()
    if get_draft_workout_exercise(draft, draft_exercise_id) is None:
        raise HTTPException(status_code=404, detail="Draft exercise not found.")

    add_set_to_active_draft(
        draft_exercise_id=draft_exercise_id,
        weight=payload.weight,
        reps=payload.reps,
    )
    return build_current_workout_response()


@router.post("/exercises/{draft_exercise_id}/sets/duplicate")
def duplicate_current_workout_set(
    draft_exercise_id: int,
) -> dict[str, Any]:
    draft = require_active_draft()
    if get_draft_workout_exercise(draft, draft_exercise_id) is None:
        raise HTTPException(status_code=404, detail="Draft exercise not found.")

    set_entry = duplicate_active_draft_set(draft_exercise_id)
    if set_entry is None:
        raise HTTPException(status_code=404, detail="No set source found.")

    return build_current_workout_response()


@router.patch("/sets/{draft_set_id}")
def update_current_workout_set(
    draft_set_id: int,
    payload: UpdateSetRequest,
) -> dict[str, Any]:
    draft = require_active_draft()
    if payload.weight is None and payload.reps is None:
        raise HTTPException(status_code=400, detail="No set fields provided.")

    if get_draft_set(draft, draft_set_id) is None:
        raise HTTPException(status_code=404, detail="Draft set not found.")

    update_active_draft_set(
        draft_set_id=draft_set_id,
        weight=payload.weight,
        reps=payload.reps,
    )
    return build_current_workout_response()


@router.delete("/sets/{draft_set_id}")
def delete_current_workout_set(
    draft_set_id: int,
) -> dict[str, Any]:
    draft = require_active_draft()
    if get_draft_set(draft, draft_set_id) is None:
        raise HTTPException(status_code=404, detail="Draft set not found.")

    delete_active_draft_set(draft_set_id)
    return build_current_workout_response()


@router.post("/finish")
def finish_current_workout() -> dict[str, Any]:
    require_active_draft()
    workout_id = finish_active_workout()
    if workout_id is None:
        raise HTTPException(status_code=409, detail="No active workout draft.")

    return {
        "workout_id": workout_id,
        "current_workout": build_current_workout_response(),
    }


@router.delete("")
def clear_current_workout() -> dict[str, Any]:
    clear_active_workout_draft()
    return build_current_workout_response()
