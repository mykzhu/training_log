from collections.abc import Mapping
from typing import Any


EXERCISE_LOAD_PROFILES: dict[str, dict[str, float | str]] = {
    "deadlift": {
        "category": "heavy compound",
        "exercise_factor": 1.8,
        "compound_factor": 1.8,
        "back_factor": 1.8,
    },
    "goblet squat": {
        "category": "legs compound",
        "exercise_factor": 1.5,
        "compound_factor": 1.5,
        "back_factor": 1.1,
    },
    "db bench press": {
        "category": "upper compound",
        "exercise_factor": 1.2,
        "compound_factor": 1.2,
        "back_factor": 0.2,
    },
    "db row": {
        "category": "upper pull",
        "exercise_factor": 1.2,
        "compound_factor": 1.2,
        "back_factor": 0.7,
    },
    "ez curl": {
        "category": "arms",
        "exercise_factor": 0.75,
        "compound_factor": 0.25,
        "back_factor": 0.1,
    },
    "triceps extension": {
        "category": "arms",
        "exercise_factor": 0.75,
        "compound_factor": 0.25,
        "back_factor": 0.1,
    },
    "lateral raise": {
        "category": "shoulders",
        "exercise_factor": 1.0,
        "compound_factor": 0.4,
        "back_factor": 0.15,
    },
    "crunches": {
        "category": "core",
        "exercise_factor": 0.5,
        "compound_factor": 0.2,
        "back_factor": 0.25,
    },
}

DEFAULT_LOAD_PROFILE = {
    "category": "accessory",
    "exercise_factor": 1.0,
    "compound_factor": 0.5,
    "back_factor": 0.3,
}


def get_exercise_load_profile(exercise_name: str) -> dict[str, float | str]:
    normalized = exercise_name.strip().lower()

    for key, profile in EXERCISE_LOAD_PROFILES.items():
        if key in normalized:
            return profile

    return DEFAULT_LOAD_PROFILE


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
) -> dict[str, Any]:
    best_e1rm_by_exercise = best_e1rm_by_exercise or {}

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
        profile = get_exercise_load_profile(exercise_name)

        exercise_factor = float(profile["exercise_factor"])
        compound_factor = float(profile["compound_factor"])
        back_factor = float(profile["back_factor"])
        category = str(profile["category"])

        exercise_load = 0.0
        exercise_compound = 0.0
        exercise_intensity = 0.0
        exercise_back = 0.0

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
                    exercise_intensity / len(item["sets"])
                    if item["sets"]
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
