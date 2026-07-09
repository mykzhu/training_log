import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app.db import get_db
from app.repositories.analysis_profiles import (
    AccessoryProfileError,
    DuplicateProfileKeyError,
    DuplicateProfileLabelError,
    InvalidProfileKeyError,
    ProfileInUseError,
    create_analysis_profile,
    list_analysis_profiles,
    update_analysis_profile,
)
from app.repositories.exercises import (
    ActiveExerciseWeightError,
    InactiveExerciseProfileError,
    create_exercise,
    get_exercise,
    list_exercises,
    normalize_exercise_name,
    reorder_exercises,
    replace_exercise_weights,
    update_exercise,
)
from app.services.stats_service import build_exercise_stats, parse_limit
from app.schemas import (
    ExerciseCreateRequest,
    ExerciseMutationResponse,
    ExerciseOrderUpdateRequest,
    ExerciseProfileCreateRequest,
    ExerciseProfileMutationResponse,
    ExerciseProfilesResponse,
    ExerciseProfileUpdateRequest,
    ExerciseStatsResponseModel,
    ExerciseUpdateRequest,
    ExerciseWeightsResponse,
    ExerciseWeightsUpdateRequest,
    ExercisesResponse,
)


router = APIRouter(prefix="/api/v1/exercises", tags=["exercises"])
profiles_router = APIRouter(prefix="/api/v1/exercise-profiles", tags=["exercises"])


def clean_exercise_name(name: str) -> str:
    return normalize_exercise_name(name)


def profile_error_response(exc: Exception) -> HTTPException:
    if isinstance(exc, (DuplicateProfileKeyError, DuplicateProfileLabelError)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ProfileInUseError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, (AccessoryProfileError, InvalidProfileKeyError, ValueError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail="Profile action failed.")


@router.get("", response_model=ExercisesResponse)
def get_exercises(
    include_inactive: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "exercises": list_exercises(include_inactive=include_inactive),
    }


@router.get("/{exercise_id}/stats", response_model=ExerciseStatsResponseModel)
def get_exercise_stats_endpoint(
    exercise_id: int,
    limit: Annotated[str | None, Query()] = "30",
) -> dict[str, Any]:
    parsed_limit = parse_limit(limit, default=30)
    stats = build_exercise_stats(exercise_id, limit=parsed_limit)

    if stats is None:
        raise HTTPException(status_code=404, detail="Exercise not found.")

    return stats


@router.post("", response_model=ExerciseMutationResponse)
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
            option_settings={
                "default_weight": payload.default_weight,
                "min_weight": payload.min_weight,
                "max_weight": payload.max_weight,
                "weight_step": payload.weight_step,
                "default_reps": payload.default_reps,
                "min_reps": payload.min_reps,
                "max_reps": payload.max_reps,
                "reps_step": payload.reps_step,
            },
            measurement_settings={
                "measurement_type": payload.measurement_type,
                "reps_unit": payload.reps_unit,
            },
        )
    except ActiveExerciseWeightError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InactiveExerciseProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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


@router.patch("/{exercise_id}", response_model=ExerciseMutationResponse)
def update_exercise_endpoint(
    exercise_id: int,
    payload: ExerciseUpdateRequest,
) -> dict[str, Any]:
    changed_fields = payload.model_fields_set
    if not changed_fields:
        raise HTTPException(status_code=400, detail="No exercise fields provided.")

    name = None
    if "name" in changed_fields:
        name = clean_exercise_name(payload.name or "")
        if not name:
            raise HTTPException(status_code=400, detail="Exercise name is required.")

    if get_exercise(exercise_id) is None:
        raise HTTPException(status_code=404, detail="Exercise not found.")

    option_field_names = {
        "default_weight",
        "min_weight",
        "max_weight",
        "weight_step",
        "default_reps",
        "min_reps",
        "max_reps",
        "reps_step",
    }
    option_settings = {
        field_name: getattr(payload, field_name)
        for field_name in option_field_names
        if field_name in changed_fields
    }
    measurement_field_names = {"measurement_type", "reps_unit"}
    measurement_settings = {
        field_name: getattr(payload, field_name)
        for field_name in measurement_field_names
        if field_name in changed_fields
    }

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
            option_settings=option_settings if option_settings else None,
            measurement_settings=(
                measurement_settings if measurement_settings else None
            ),
        )
    except ActiveExerciseWeightError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InactiveExerciseProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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


@router.put("/order", response_model=ExercisesResponse)
def reorder_exercises_endpoint(
    payload: ExerciseOrderUpdateRequest,
) -> dict[str, Any]:
    try:
        exercises = reorder_exercises(payload.exercise_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"exercises": exercises}


@router.put("/{exercise_id}/weights", response_model=ExerciseWeightsResponse)
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


@profiles_router.get("", response_model=ExerciseProfilesResponse)
def get_exercise_profiles() -> dict[str, list[dict[str, Any]]]:
    with get_db() as conn:
        return {"profiles": list_analysis_profiles(conn)}


@profiles_router.post("", response_model=ExerciseProfileMutationResponse)
def create_exercise_profile_endpoint(
    payload: ExerciseProfileCreateRequest,
) -> dict[str, Any]:
    try:
        with get_db() as conn:
            profile = create_analysis_profile(
                conn,
                key=payload.key,
                label=payload.label,
                category=payload.category,
                exercise_factor=payload.exercise_factor,
                compound_factor=payload.compound_factor,
                back_factor=payload.back_factor,
            )
    except Exception as exc:
        http_exc = profile_error_response(exc)
        raise http_exc from exc

    return {"profile": profile, "created": True}


@profiles_router.patch("/{profile_key}", response_model=ExerciseProfileMutationResponse)
def update_exercise_profile_endpoint(
    profile_key: str,
    payload: ExerciseProfileUpdateRequest,
) -> dict[str, Any]:
    changed_fields = payload.model_fields_set
    if not changed_fields:
        raise HTTPException(status_code=400, detail="No profile fields provided.")

    try:
        with get_db() as conn:
            profile = update_analysis_profile(
                conn,
                profile_key,
                label=payload.label if "label" in changed_fields else None,
                category=(
                    payload.category if "category" in changed_fields else None
                ),
                exercise_factor=(
                    payload.exercise_factor
                    if "exercise_factor" in changed_fields
                    else None
                ),
                compound_factor=(
                    payload.compound_factor
                    if "compound_factor" in changed_fields
                    else None
                ),
                back_factor=(
                    payload.back_factor if "back_factor" in changed_fields else None
                ),
                is_active=(
                    payload.is_active if "is_active" in changed_fields else None
                ),
            )
    except Exception as exc:
        http_exc = profile_error_response(exc)
        raise http_exc from exc

    if profile is None:
        raise HTTPException(status_code=404, detail="Exercise profile not found.")

    return {"profile": profile}
