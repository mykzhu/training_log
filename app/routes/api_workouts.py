from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.repositories.exercises import get_exercise
from app.repositories.workouts import (
    NumberingConflictError,
    add_set_to_workout_exercise,
    add_workout_exercise,
    delete_set_entry,
    delete_workout,
    delete_workout_exercise,
    duplicate_set_for_workout_exercise,
    get_set_entry,
    get_workout,
    get_workout_details,
    get_workout_details_batch,
    get_workout_exercise,
    list_recent_workouts,
    update_set_entry,
    update_workout,
)
from app.schemas import (
    AddExerciseRequest,
    AddSetRequest,
    DeleteWorkoutResponse,
    UpdateSetRequest,
    WorkoutDetailResponse,
    WorkoutsResponse,
    WorkoutUpdateRequest,
)
from app.services.analysis_service import runtime_profiles_by_key
from app.services.stats_service import (
    build_e1rm_baselines_by_workout,
    build_workout_analysis,
    calculate_workout_load_metrics,
)


router = APIRouter(prefix="/api/v1/workouts", tags=["workouts"])
workout_items_router = APIRouter(prefix="/api/v1", tags=["workouts"])


def serialize_set(set_row: Any) -> dict[str, Any]:
    return {
        "id": int(set_row["id"]),
        "workout_exercise_id": int(set_row["workout_exercise_id"]),
        "set_number": int(set_row["set_number"]),
        "weight": float(set_row["weight"]),
        "reps": int(set_row["reps"]),
        "created_at": set_row["created_at"],
    }


def serialize_workout_exercise(item: dict[str, Any]) -> dict[str, Any]:
    sets = [serialize_set(set_row) for set_row in item["sets"]]

    return {
        "workout_exercise_id": int(item["workout_exercise_id"]),
        "exercise_id": int(item["exercise_id"]),
        "exercise_name": item["exercise_name"],
        "profile_key": item["profile_key"],
        "position": int(item["position"]),
        "sets": sets,
        "total_sets": len(sets),
        "total_reps": int(item["total_reps"]),
        "total_volume": float(item["total_volume"]),
        "default_weight": float(item["default_weight"]),
        "default_reps": int(item["default_reps"]),
        "configured_weights": item["configured_weights"],
    }


def build_workout_summary(
    workout: dict[str, Any],
    *,
    details: list[dict[str, Any]] | None = None,
    best_e1rm_by_exercise: dict[int, float] | None = None,
    profiles_by_key: dict[str, dict[str, float | str]] | None = None,
) -> dict[str, Any]:
    workout_id = int(workout["id"])
    details = details if details is not None else get_workout_details(workout_id)
    total_volume = sum(item["total_volume"] for item in details)
    total_reps = sum(item["total_reps"] for item in details)
    total_sets = sum(len(item["sets"]) for item in details)
    load_metrics = calculate_workout_load_metrics(
        workout_exercises=details,
        session_rpe=workout["session_rpe"],
        as_of_created_at=workout["created_at"],
        as_of_workout_id=workout_id,
        best_e1rm_by_exercise=best_e1rm_by_exercise,
        profiles_by_key=profiles_by_key,
    )

    return {
        "id": workout_id,
        "workout_date": workout["workout_date"],
        "created_at": workout["created_at"],
        "finished_at": workout["finished_at"],
        "session_rpe": workout["session_rpe"],
        "lower_back_pain": workout["lower_back_pain"],
        "duration_seconds": workout["duration_seconds"],
        "total_volume": total_volume,
        "total_reps": total_reps,
        "total_sets": total_sets,
        "exercises_count": len(details),
        "load_metrics": load_metrics,
    }


def build_workout_summaries(workouts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    workout_ids = [int(workout["id"]) for workout in workouts]
    details_by_workout = get_workout_details_batch(workout_ids)
    e1rm_baselines_by_workout = build_e1rm_baselines_by_workout(
        workouts=workouts,
        details_by_workout=details_by_workout,
    )
    profiles_by_key = runtime_profiles_by_key()

    return [
        build_workout_summary(
            workout,
            details=details_by_workout.get(int(workout["id"]), []),
            best_e1rm_by_exercise=e1rm_baselines_by_workout.get(
                int(workout["id"]),
                {},
            ),
            profiles_by_key=profiles_by_key,
        )
        for workout in workouts
    ]


def normalize_created_at(value: str | None) -> str:
    if value is None:
        raise HTTPException(status_code=400, detail="created_at cannot be null.")

    created_at = value.strip()
    if len(created_at) == 16:
        created_at = f"{created_at}:00"

    try:
        parsed = datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="created_at must be an ISO datetime.",
        ) from exc

    return parsed.isoformat(timespec="seconds")


def calculate_duration_seconds(
    created_at: str,
    finished_at: str | None,
) -> int | None:
    if not finished_at:
        return None

    try:
        return max(
            0,
            int(
                (
                    datetime.fromisoformat(finished_at)
                    - datetime.fromisoformat(created_at)
                ).total_seconds()
            ),
        )
    except ValueError:
        return None


@router.get("", response_model=WorkoutsResponse)
def get_workouts(
    limit: int = Query(default=30, ge=1, le=500),
) -> dict[str, Any]:
    workouts = list_recent_workouts(limit=limit)
    return {
        "limit": limit,
        "workouts": build_workout_summaries(workouts),
    }


@router.get("/{workout_id}", response_model=WorkoutDetailResponse)
def get_workout_detail(workout_id: int) -> dict[str, Any]:
    workout = get_workout(workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found.")

    details = get_workout_details(workout_id)
    exercises = [serialize_workout_exercise(item) for item in details]
    total_volume = sum(item["total_volume"] for item in details)
    total_reps = sum(item["total_reps"] for item in details)
    total_sets = sum(len(item["sets"]) for item in details)
    load_metrics = calculate_workout_load_metrics(
        workout_exercises=details,
        session_rpe=workout["session_rpe"],
        as_of_created_at=workout["created_at"],
        as_of_workout_id=workout_id,
    )
    analysis = build_workout_analysis(workout_id, details)

    return {
        "workout": {
            "id": int(workout["id"]),
            "workout_date": workout["workout_date"],
            "created_at": workout["created_at"],
            "finished_at": workout["finished_at"],
            "session_rpe": workout["session_rpe"],
            "lower_back_pain": workout["lower_back_pain"],
            "duration_seconds": workout["duration_seconds"],
        },
        "exercises": exercises,
        "total_volume": total_volume,
        "total_reps": total_reps,
        "total_sets": total_sets,
        "load_metrics": load_metrics,
        "analysis": analysis,
    }


@router.patch("/{workout_id}", response_model=WorkoutDetailResponse)
def update_workout_endpoint(
    workout_id: int,
    payload: WorkoutUpdateRequest,
) -> dict[str, Any]:
    workout = get_workout(workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found.")

    changed_fields = payload.model_fields_set
    if not changed_fields:
        raise HTTPException(status_code=400, detail="No workout fields provided.")

    created_at = workout["created_at"]
    workout_date = workout["workout_date"]
    duration_seconds = workout["duration_seconds"]

    if "created_at" in changed_fields:
        created_at = normalize_created_at(payload.created_at)
        workout_date = created_at[:10]
        duration_seconds = calculate_duration_seconds(
            created_at=created_at,
            finished_at=workout["finished_at"],
        )

    session_rpe = (
        payload.session_rpe
        if "session_rpe" in changed_fields
        else workout["session_rpe"]
    )
    lower_back_pain = (
        payload.lower_back_pain
        if "lower_back_pain" in changed_fields
        else workout["lower_back_pain"]
    )

    updated_workout = update_workout(
        workout_id,
        workout_date=workout_date,
        created_at=created_at,
        session_rpe=session_rpe,
        lower_back_pain=lower_back_pain,
        duration_seconds=duration_seconds,
    )
    if updated_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found.")

    return get_workout_detail(workout_id)


@router.delete("/{workout_id}", response_model=DeleteWorkoutResponse)
def delete_workout_endpoint(workout_id: int) -> dict[str, Any]:
    if not delete_workout(workout_id):
        raise HTTPException(status_code=404, detail="Workout not found.")

    return {
        "deleted": True,
        "workout_id": workout_id,
    }


@router.post("/{workout_id}/exercises", response_model=WorkoutDetailResponse)
def add_workout_exercise_endpoint(
    workout_id: int,
    payload: AddExerciseRequest,
) -> dict[str, Any]:
    if get_workout(workout_id) is None:
        raise HTTPException(status_code=404, detail="Workout not found.")

    exercise = get_exercise(payload.exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found.")
    if not exercise["is_active"]:
        raise HTTPException(status_code=409, detail="Exercise is inactive.")

    try:
        add_workout_exercise(workout_id, payload.exercise_id)
    except NumberingConflictError:
        raise HTTPException(
            status_code=409,
            detail="Could not assign a unique position. Please retry.",
        ) from None
    return get_workout_detail(workout_id)


@router.delete("/{workout_id}/exercises/{workout_exercise_id}", response_model=WorkoutDetailResponse)
def delete_workout_exercise_endpoint(
    workout_id: int,
    workout_exercise_id: int,
) -> dict[str, Any]:
    if get_workout(workout_id) is None:
        raise HTTPException(status_code=404, detail="Workout not found.")

    if not delete_workout_exercise(workout_id, workout_exercise_id):
        raise HTTPException(status_code=404, detail="Workout exercise not found.")

    return get_workout_detail(workout_id)


@workout_items_router.post("/workout-exercises/{workout_exercise_id}/sets", response_model=WorkoutDetailResponse)
def add_workout_exercise_set_endpoint(
    workout_exercise_id: int,
    payload: AddSetRequest,
) -> dict[str, Any]:
    workout_exercise = get_workout_exercise(workout_exercise_id)
    if workout_exercise is None:
        raise HTTPException(status_code=404, detail="Workout exercise not found.")

    try:
        set_entry = add_set_to_workout_exercise(
            workout_exercise_id,
            weight=payload.weight,
            reps=payload.reps,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
    except NumberingConflictError:
        raise HTTPException(
            status_code=409,
            detail="Could not assign a unique set number. Please retry.",
        ) from None
    if set_entry is None:
        raise HTTPException(status_code=404, detail="Workout exercise not found.")

    return get_workout_detail(int(workout_exercise["workout_id"]))


@workout_items_router.post("/workout-exercises/{workout_exercise_id}/sets/duplicate", response_model=WorkoutDetailResponse)
def duplicate_workout_exercise_set_endpoint(
    workout_exercise_id: int,
) -> dict[str, Any]:
    workout_exercise = get_workout_exercise(workout_exercise_id)
    if workout_exercise is None:
        raise HTTPException(status_code=404, detail="Workout exercise not found.")

    set_entry = duplicate_set_for_workout_exercise(
        workout_exercise_id,
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
    if set_entry is None:
        raise HTTPException(status_code=404, detail="No set source found.")

    return get_workout_detail(int(workout_exercise["workout_id"]))


@workout_items_router.patch("/sets/{set_id}", response_model=WorkoutDetailResponse)
def update_set_endpoint(
    set_id: int,
    payload: UpdateSetRequest,
) -> dict[str, Any]:
    if payload.weight is None and payload.reps is None:
        raise HTTPException(status_code=400, detail="No set fields provided.")

    current_set = get_set_entry(set_id)
    if current_set is None:
        raise HTTPException(status_code=404, detail="Set not found.")

    updated_set = update_set_entry(
        set_id,
        weight=payload.weight,
        reps=payload.reps,
    )
    if updated_set is None:
        raise HTTPException(status_code=404, detail="Set not found.")

    return get_workout_detail(int(current_set["workout_id"]))


@workout_items_router.delete("/sets/{set_id}", response_model=WorkoutDetailResponse)
def delete_set_endpoint(set_id: int) -> dict[str, Any]:
    current_set = delete_set_entry(set_id)
    if current_set is None:
        raise HTTPException(status_code=404, detail="Set not found.")

    return get_workout_detail(int(current_set["workout_id"]))
