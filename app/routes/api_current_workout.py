from typing import Any

from fastapi import APIRouter, HTTPException

from app.db import get_db
from app.repositories.drafts import EmptyDraftError
from app.schemas import (
    AddExerciseRequest,
    AddSetRequest,
    CurrentWorkoutResponse,
    FinishCurrentWorkoutResponse,
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
    draft_has_logged_sets,
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
from app.services.garmin_service import garmin_service
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
            "garmin_recovery": garmin_service.recovery_snapshot(),
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
                "profile_key": item["profile_key"],
                "measurement_type": item["measurement_type"],
                "reps_unit": item["reps_unit"],
                "position": item["position"],
                "sets": item["sets"],
                "total_sets": len(item["sets"]),
                "total_reps": item["total_reps"],
                "total_volume": item["total_volume"],
                "total_volume_kg": item["total_volume_kg"],
                "bodyweight_reps": item["bodyweight_reps"],
                "duration_seconds": item["duration_seconds"],
                "distance_m": item["distance_m"],
                "default_weight": item["default_weight"],
                "default_reps": item["default_reps"],
                "configured_weights": item["configured_weights"],
                "weight_options": item["weight_options"],
                "reps_options": item["reps_options"],
            }
            for item in workout_exercises
        ],
        "load_metrics": load_metrics,
        "recovery_context": None,
        "next_workout_recommendation": None,
        "garmin_recovery": None,
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


@router.get("", response_model=CurrentWorkoutResponse)
def get_current_workout() -> dict[str, Any]:
    return build_current_workout_response()


@router.post("/start", response_model=CurrentWorkoutResponse)
def start_current_workout() -> dict[str, Any]:
    draft, _ = start_active_workout_draft()
    return build_current_workout_response(draft)


@router.patch("/metadata", response_model=CurrentWorkoutResponse)
def update_current_workout_metadata(
    payload: WorkoutMetadataUpdate,
) -> dict[str, Any]:
    require_active_draft()

    updates: dict[str, int | None] = {}
    if "session_rpe" in payload.model_fields_set:
        updates["session_rpe"] = payload.session_rpe
    if "lower_back_pain" in payload.model_fields_set:
        updates["lower_back_pain"] = payload.lower_back_pain

    if updates:
        update_active_draft_metadata(updates)

    return build_current_workout_response()


@router.post("/exercises", response_model=CurrentWorkoutResponse)
def add_current_workout_exercise(
    payload: AddExerciseRequest,
) -> dict[str, Any]:
    require_active_draft()
    exercise = get_exercise_or_404(payload.exercise_id)
    if not exercise["is_active"]:
        raise HTTPException(status_code=409, detail="Exercise is inactive.")

    add_exercise_to_active_draft(
        exercise_id=int(exercise["id"]),
        exercise_name=str(exercise["name"]),
        profile_key=str(exercise["profile_key"] or "accessory"),
    )
    return build_current_workout_response()


@router.delete("/exercises/{draft_exercise_id}", response_model=CurrentWorkoutResponse)
def delete_current_workout_exercise(
    draft_exercise_id: int,
) -> dict[str, Any]:
    draft = require_active_draft()
    if get_draft_workout_exercise(draft, draft_exercise_id) is None:
        raise HTTPException(status_code=404, detail="Draft exercise not found.")

    delete_active_draft_exercise(draft_exercise_id)
    return build_current_workout_response()


@router.post("/exercises/{draft_exercise_id}/sets", response_model=CurrentWorkoutResponse)
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


@router.post("/exercises/{draft_exercise_id}/sets/duplicate", response_model=CurrentWorkoutResponse)
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


@router.patch("/sets/{draft_set_id}", response_model=CurrentWorkoutResponse)
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


@router.delete("/sets/{draft_set_id}", response_model=CurrentWorkoutResponse)
def delete_current_workout_set(
    draft_set_id: int,
) -> dict[str, Any]:
    draft = require_active_draft()
    if get_draft_set(draft, draft_set_id) is None:
        raise HTTPException(status_code=404, detail="Draft set not found.")

    delete_active_draft_set(draft_set_id)
    return build_current_workout_response()


@router.post("/finish", response_model=FinishCurrentWorkoutResponse)
def finish_current_workout() -> dict[str, Any]:
    draft = require_active_draft()

    if not draft_has_logged_sets(draft):
        raise HTTPException(
            status_code=400,
            detail="Cannot finish a workout without logged sets.",
        )

    try:
        workout_id = finish_active_workout()
    except EmptyDraftError as exc:
        raise HTTPException(
            status_code=400,
            detail="Cannot finish a workout without logged sets.",
        ) from exc

    if workout_id is None:
        raise HTTPException(status_code=409, detail="No active workout draft.")

    return {
        "workout_id": workout_id,
        "current_workout": build_current_workout_response(),
    }


@router.delete("", response_model=CurrentWorkoutResponse)
def clear_current_workout() -> dict[str, Any]:
    clear_active_workout_draft()
    return build_current_workout_response()
