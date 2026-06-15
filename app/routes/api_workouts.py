from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.repositories.workouts import (
    get_workout,
    get_workout_details,
    list_recent_workouts,
)
from app.services.stats_service import calculate_workout_load_metrics


router = APIRouter(prefix="/api/v1/workouts", tags=["workouts"])


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
        "position": int(item["position"]),
        "sets": sets,
        "total_sets": len(sets),
        "total_reps": int(item["total_reps"]),
        "total_volume": float(item["total_volume"]),
        "default_weight": float(item["default_weight"]),
        "default_reps": int(item["default_reps"]),
    }


def build_workout_summary(workout: dict[str, Any]) -> dict[str, Any]:
    workout_id = int(workout["id"])
    details = get_workout_details(workout_id)
    total_volume = sum(item["total_volume"] for item in details)
    total_reps = sum(item["total_reps"] for item in details)
    total_sets = sum(len(item["sets"]) for item in details)
    load_metrics = calculate_workout_load_metrics(
        workout_exercises=details,
        session_rpe=workout["session_rpe"],
        current_workout_id=workout_id,
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


@router.get("")
def get_workouts(
    limit: int = Query(default=30, ge=1, le=500),
) -> dict[str, Any]:
    workouts = list_recent_workouts(limit=limit)
    return {
        "limit": limit,
        "workouts": [build_workout_summary(workout) for workout in workouts],
    }


@router.get("/{workout_id}")
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
        current_workout_id=workout_id,
    )

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
    }
