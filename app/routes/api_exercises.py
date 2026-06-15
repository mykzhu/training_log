import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException

from app.repositories.exercises import (
    create_exercise,
    get_exercise,
    list_exercises,
    update_exercise_name,
)
from app.schemas import ExerciseCreateRequest, ExerciseUpdateRequest


router = APIRouter(prefix="/api/v1/exercises", tags=["exercises"])


def clean_exercise_name(name: str) -> str:
    return " ".join(name.strip().split())


@router.get("")
def get_exercises() -> dict[str, list[dict[str, Any]]]:
    return {"exercises": list_exercises()}


@router.post("")
def create_exercise_endpoint(
    payload: ExerciseCreateRequest,
) -> dict[str, Any]:
    name = clean_exercise_name(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Exercise name is required.")

    exercise, created = create_exercise(name)
    return {
        "exercise": exercise,
        "created": created,
    }


@router.patch("/{exercise_id}")
def update_exercise_endpoint(
    exercise_id: int,
    payload: ExerciseUpdateRequest,
) -> dict[str, Any]:
    name = clean_exercise_name(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Exercise name is required.")

    if get_exercise(exercise_id) is None:
        raise HTTPException(status_code=404, detail="Exercise not found.")

    try:
        exercise = update_exercise_name(exercise_id, name)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Exercise name already exists.",
        ) from exc

    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found.")

    return {"exercise": exercise}
