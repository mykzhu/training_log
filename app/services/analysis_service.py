from collections.abc import Mapping
import sqlite3
from typing import Any

from app import config
from app.db import get_db
from app.repositories.analysis_profiles import load_profiles_by_key
from app.services.default_analysis_profiles import (
    DEFAULT_EXERCISE_PROFILE_KEYS_BY_NAME,
    DEFAULT_LOAD_PROFILE,
    DEFAULT_LOAD_PROFILES_BY_KEY,
    DEFAULT_PROFILE_KEY,
    DEFAULT_PROFILE_LABELS_BY_KEY,
    DEFAULT_SUPPORTED_PROFILE_KEYS,
    default_profile_rows,
    profile_key_for_exercise_name,
)


LOAD_PROFILES_BY_KEY = DEFAULT_LOAD_PROFILES_BY_KEY
PROFILE_LABELS_BY_KEY = DEFAULT_PROFILE_LABELS_BY_KEY
SUPPORTED_PROFILE_KEYS = DEFAULT_SUPPORTED_PROFILE_KEYS
EXERCISE_PROFILE_KEYS_BY_NAME = DEFAULT_EXERCISE_PROFILE_KEYS_BY_NAME


def default_profiles_by_key() -> dict[str, dict[str, float | str]]:
    return {key: dict(profile) for key, profile in DEFAULT_LOAD_PROFILES_BY_KEY.items()}


def runtime_profiles_by_key() -> dict[str, dict[str, float | str]]:
    if not config.DB_PATH.exists():
        return default_profiles_by_key()

    try:
        with get_db() as conn:
            profiles = load_profiles_by_key(conn)
    except (sqlite3.Error, RuntimeError):
        return default_profiles_by_key()

    if DEFAULT_PROFILE_KEY not in profiles:
        profiles[DEFAULT_PROFILE_KEY] = dict(DEFAULT_LOAD_PROFILE)
    return profiles


def is_supported_profile_key(profile_key: str) -> bool:
    if profile_key in DEFAULT_SUPPORTED_PROFILE_KEYS:
        return True
    if not config.DB_PATH.exists():
        return False

    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT 1 FROM analysis_profiles WHERE key = ?",
                (profile_key,),
            ).fetchone()
    except (sqlite3.Error, RuntimeError):
        return False

    return row is not None


def list_exercise_profiles() -> list[dict[str, Any]]:
    if not config.DB_PATH.exists():
        return default_profile_rows()

    try:
        from app.repositories.analysis_profiles import list_analysis_profiles

        with get_db() as conn:
            return list_analysis_profiles(conn)
    except (sqlite3.Error, RuntimeError):
        return default_profile_rows()


def profile_from_map(
    profiles_by_key: Mapping[str, Mapping[str, float | str]],
    exercise_name: str,
    profile_key: str | None = None,
) -> dict[str, float | str]:
    if profile_key and profile_key in profiles_by_key:
        return dict(profiles_by_key[profile_key])

    if profile_key and profile_key in DEFAULT_LOAD_PROFILES_BY_KEY:
        return dict(DEFAULT_LOAD_PROFILES_BY_KEY[profile_key])

    if profile_key:
        return dict(profiles_by_key.get(DEFAULT_PROFILE_KEY, DEFAULT_LOAD_PROFILE))

    inferred_key = profile_key_for_exercise_name(exercise_name)
    if inferred_key in profiles_by_key:
        return dict(profiles_by_key[inferred_key])

    return dict(profiles_by_key.get(DEFAULT_PROFILE_KEY, DEFAULT_LOAD_PROFILE))


def get_exercise_load_profile(
    exercise_name: str,
    profile_key: str | None = None,
) -> dict[str, float | str]:
    return profile_from_map(runtime_profiles_by_key(), exercise_name, profile_key)


def estimated_1rm(weight: float, reps: int) -> float | None:
    if weight <= 0:
        return None

    if reps < 3 or reps > 12:
        return None

    return weight * (1 + reps / 30)


def rep_factor(reps: int) -> float:
    if reps <= 0:
        return 0.0
    if reps <= 3:
        return 1.15
    if reps <= 8:
        return 1.10
    if reps <= 15:
        return 1.00
    return 0.85


def intensity_factor(relative_intensity: float | None) -> float:
    if relative_intensity is None:
        return 1.0

    if relative_intensity < 0.55:
        return 0.5
    if relative_intensity < 0.70:
        return 0.8
    if relative_intensity < 0.80:
        return 1.0
    if relative_intensity < 0.90:
        return 1.25

    return 1.5


def rpe_factor(session_rpe: int | float | None) -> float:
    if session_rpe is None:
        return 1.0

    return 0.7 + float(session_rpe) * 0.06


def workout_load_label(load_score: float) -> str:
    if load_score < 4:
        return "Light"
    if load_score < 8:
        return "Medium"
    if load_score < 14:
        return "Hard"
    return "Very hard"


def calculate_workout_load_metrics(
    workout_exercises: list[dict[str, Any]],
    session_rpe: int | float | None = None,
    best_e1rm_by_exercise: Mapping[int, float] | None = None,
    profiles_by_key: Mapping[str, Mapping[str, float | str]] | None = None,
) -> dict[str, Any]:
    best_e1rm_by_exercise = best_e1rm_by_exercise or {}
    profiles_by_key = profiles_by_key or runtime_profiles_by_key()

    raw_load_score = 0.0
    compound_score = 0.0
    intensity_score = 0.0
    back_stress_score = 0.0
    scored_sets = 0
    known_intensity_sets = 0

    exercise_breakdown: list[dict[str, Any]] = []

    for item in workout_exercises:
        exercise_id = int(item["exercise_id"])
        exercise_name = str(item["exercise_name"])
        profile = profile_from_map(
            profiles_by_key,
            exercise_name,
            profile_key=item.get("profile_key"),
        )

        exercise_factor = float(profile["exercise_factor"])
        compound_factor = float(profile["compound_factor"])
        back_factor = float(profile["back_factor"])
        category = str(profile["category"])

        exercise_load = 0.0
        exercise_compound = 0.0
        exercise_intensity = 0.0
        exercise_back = 0.0
        exercise_known_intensity_sets = 0

        best_e1rm = best_e1rm_by_exercise.get(exercise_id)

        for set_row in item["sets"]:
            weight = float(set_row["weight"])
            reps = int(set_row["reps"])

            if reps <= 0:
                continue

            set_e1rm = estimated_1rm(weight, reps)
            relative_intensity = None

            if best_e1rm and best_e1rm > 0 and set_e1rm is not None:
                relative_intensity = min(1.5, set_e1rm / best_e1rm)
                known_intensity_sets += 1
                exercise_known_intensity_sets += 1

            set_rep_factor = rep_factor(reps)
            set_intensity_factor = intensity_factor(relative_intensity)

            set_score = exercise_factor * set_rep_factor * set_intensity_factor
            set_compound_score = compound_factor * set_rep_factor
            set_back_score = back_factor * set_rep_factor * set_intensity_factor

            raw_load_score += set_score
            compound_score += set_compound_score
            back_stress_score += set_back_score

            if relative_intensity is not None:
                intensity_score += relative_intensity * 100

            exercise_load += set_score
            exercise_compound += set_compound_score
            exercise_back += set_back_score

            if relative_intensity is not None:
                exercise_intensity += relative_intensity * 100

            scored_sets += 1

        exercise_breakdown.append(
            {
                "exercise_id": exercise_id,
                "exercise_name": exercise_name,
                "category": category,
                "load_score": exercise_load,
                "compound_score": exercise_compound,
                "intensity_score": (
                    exercise_intensity / exercise_known_intensity_sets
                    if exercise_known_intensity_sets
                    else None
                ),
                "back_stress_score": exercise_back,
            }
        )

    rpe_multiplier = rpe_factor(session_rpe)
    load_score = raw_load_score * rpe_multiplier
    load_label = workout_load_label(load_score)

    return {
        "load_score": load_score,
        "raw_load_score": raw_load_score,
        "load_label": load_label,
        "rpe_factor": rpe_multiplier,
        "compound_score": compound_score,
        "intensity_score": (
            intensity_score / known_intensity_sets
            if known_intensity_sets
            else None
        ),
        "back_stress_score": back_stress_score,
        "scored_sets": scored_sets,
        "exercise_breakdown": exercise_breakdown,
    }
