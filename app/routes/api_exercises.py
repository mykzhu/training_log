import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException

from app.repositories.exercises import (
    ActiveExerciseWeightError,
    create_exercise,
    get_exercise,
    list_exercises,
    normalize_exercise_name,
    reorder_exercises,
    replace_exercise_weights,
    update_exercise,
)
from app.services.analysis_service import list_exercise_profiles
from app.schemas import (
    ExerciseCreateRequest,
    ExerciseOrderUpdateRequest,
    ExerciseUpdateRequest,
    ExerciseWeightsUpdateRequest,
)


router = APIRouter(prefix="/api/v1/exercises", tags=["exercises"])
profiles_router = APIRouter(prefix="/api/v1/exercise-profiles", tags=["exercises"])


def clean_exercise_name(name: str) -> str:
    return normalize_exercise_name(name)


@router.get("")
def get_exercises(
    include_inactive: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "exercises": list_exercises(include_inactive=include_inactive),
    }


@router.post("")
def create_exercise_endpoint(
    payload: ExerciseCreateRequest,
) -> dict[str, Any]:
    name = clean_exercise_name(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Exercise name is required.")

    try:
        exercise, created = create_exercise(
            name,
            is_active=payload.is_active,
            profile_key=payload.profile_key,
            weights=payload.weights,
        )
    except ActiveExerciseWeightError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Exercise name already exists.",
        ) from exc

    return {
        "exercise": exercise,
        "created": created,
    }


@router.patch("/{exercise_id}")
def update_exercise_endpoint(
    exercise_id: int,
    payload: ExerciseUpdateRequest,
) -> dict[str, Any]:
    changed_fields = payload.__fields_set__
    if not changed_fields:
        raise HTTPException(status_code=400, detail="No exercise fields provided.")

    name = None
    if "name" in changed_fields:
        name = clean_exercise_name(payload.name or "")
        if not name:
            raise HTTPException(status_code=400, detail="Exercise name is required.")

    if get_exercise(exercise_id) is None:
        raise HTTPException(status_code=404, detail="Exercise not found.")

    try:
        exercise = update_exercise(
            exercise_id,
            name=name,
            is_active=payload.is_active if "is_active" in changed_fields else None,
            profile_key=(
                payload.profile_key
                if "profile_key" in changed_fields
                else None
            ),
        )
    except ActiveExerciseWeightError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Exercise name already exists.",
        ) from exc

    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found.")

    return {"exercise": exercise}


@router.put("/order")
def reorder_exercises_endpoint(
    payload: ExerciseOrderUpdateRequest,
) -> dict[str, Any]:
    try:
        exercises = reorder_exercises(payload.exercise_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"exercises": exercises}


@router.put("/{exercise_id}/weights")
def replace_exercise_weights_endpoint(
    exercise_id: int,
    payload: ExerciseWeightsUpdateRequest,
) -> dict[str, Any]:
    try:
        weights = replace_exercise_weights(exercise_id, payload.weights)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Exercise not found.") from exc
    except ActiveExerciseWeightError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "exercise_id": exercise_id,
        "weights": weights,
    }


@profiles_router.get("")
def get_exercise_profiles() -> dict[str, list[dict[str, str]]]:
    return {"profiles": list_exercise_profiles()}
