from typing import Any


DEFAULT_PROFILE_KEY = "accessory"

DEFAULT_LOAD_PROFILES_BY_KEY: dict[str, dict[str, float | str]] = {
    "deadlift": {
        "category": "heavy compound",
        "exercise_factor": 1.8,
        "compound_factor": 1.8,
        "back_factor": 1.8,
    },
    "db_bench_press": {
        "category": "upper compound",
        "exercise_factor": 1.2,
        "compound_factor": 1.2,
        "back_factor": 0.2,
    },
    "db_row": {
        "category": "upper pull",
        "exercise_factor": 1.2,
        "compound_factor": 1.2,
        "back_factor": 0.7,
    },
    "ez_curl": {
        "category": "arms",
        "exercise_factor": 0.75,
        "compound_factor": 0.25,
        "back_factor": 0.1,
    },
    "triceps_extension": {
        "category": "arms",
        "exercise_factor": 0.75,
        "compound_factor": 0.25,
        "back_factor": 0.1,
    },
    "lateral_raise": {
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
    "squats": {
        "category": "legs compound",
        "exercise_factor": 1.7,
        "compound_factor": 1.7,
        "back_factor": 1.2,
    },
    "db_squats": {
        "category": "legs compound",
        "exercise_factor": 1.4,
        "compound_factor": 1.4,
        "back_factor": 0.8,
    },
    "bench_press": {
        "category": "upper compound",
        "exercise_factor": 1.4,
        "compound_factor": 1.4,
        "back_factor": 0.2,
    },
    "incline_bench_press": {
        "category": "upper compound",
        "exercise_factor": 1.3,
        "compound_factor": 1.3,
        "back_factor": 0.2,
    },
    "shoulder_press": {
        "category": "shoulders compound",
        "exercise_factor": 1.3,
        "compound_factor": 1.2,
        "back_factor": 0.35,
    },
    "db_shoulder_press": {
        "category": "shoulders compound",
        "exercise_factor": 1.15,
        "compound_factor": 1.0,
        "back_factor": 0.25,
    },
    "triceps_pushdown": {
        "category": "arms",
        "exercise_factor": 0.7,
        "compound_factor": 0.2,
        "back_factor": 0.05,
    },
    "back_rehab": {
        "category": "back rehab",
        "exercise_factor": 0.15,
        "compound_factor": 0.0,
        "back_factor": 0.0,
    },
    "core_stability": {
        "category": "core stability",
        "exercise_factor": 0.25,
        "compound_factor": 0.1,
        "back_factor": 0.05,
    },
    "mobility": {
        "category": "mobility",
        "exercise_factor": 0.10,
        "compound_factor": 0.0,
        "back_factor": 0.0,
    },
}

DEFAULT_LOAD_PROFILE = {
    "category": "accessory",
    "exercise_factor": 1.0,
    "compound_factor": 0.5,
    "back_factor": 0.3,
}
DEFAULT_LOAD_PROFILES_BY_KEY[DEFAULT_PROFILE_KEY] = DEFAULT_LOAD_PROFILE

DEFAULT_PROFILE_LABELS_BY_KEY = {
    "deadlift": "Deadlift",
    "squats": "Squats",
    "db_squats": "DB squats",
    "bench_press": "Bench press",
    "incline_bench_press": "Incline bench press",
    "db_bench_press": "DB bench press",
    "shoulder_press": "Shoulder press",
    "db_shoulder_press": "DB shoulder press",
    "ez_curl": "EZ curl",
    "triceps_pushdown": "Triceps pushdown",
    "crunches": "Crunches",
    "db_row": "DB row",
    "triceps_extension": "Triceps extension",
    "lateral_raise": "Lateral raise",
    "back_rehab": "Back rehab",
    "core_stability": "Core stability",
    "mobility": "Mobility",
    "accessory": "Accessory",
}

DEFAULT_PROFILE_ORDER = tuple(DEFAULT_PROFILE_LABELS_BY_KEY)
DEFAULT_SUPPORTED_PROFILE_KEYS = DEFAULT_PROFILE_ORDER

DEFAULT_EXERCISE_PROFILE_KEYS_BY_NAME = {
    "db squats": "db_squats",
    "dumbbell squats": "db_squats",
    "45-degree bench press": "incline_bench_press",
    "incline bench press": "incline_bench_press",
    "db shoulder press": "db_shoulder_press",
    "dumbbell shoulder press": "db_shoulder_press",
    "db bench press": "db_bench_press",
    "dumbbell bench press": "db_bench_press",
    "triceps pushdown": "triceps_pushdown",
    "shoulder press": "shoulder_press",
    "bench press": "bench_press",
    "ez biceps": "ez_curl",
    "ez curl": "ez_curl",
    "deadlift": "deadlift",
    "crunches": "crunches",
    "squats": "squats",
    "dead bug": "core_stability",
    "cat cow": "mobility",
    "cat-cow": "mobility",
    "bird dog": "core_stability",
    "mcgill curl-up": "back_rehab",
    "mcgill curlup": "back_rehab",
    "pelvic tilt": "mobility",
    "side plank": "core_stability",
    "front plank": "core_stability",
    "plank": "core_stability",
    "glute bridge": "core_stability",
    "child pose": "mobility",
    "cobra": "mobility",
    "prone press up": "mobility",
}


def profile_key_for_exercise_name(exercise_name: str) -> str:
    normalized = exercise_name.strip().lower()

    for name_fragment, profile_key in DEFAULT_EXERCISE_PROFILE_KEYS_BY_NAME.items():
        if name_fragment in normalized:
            return profile_key

    return DEFAULT_PROFILE_KEY


def default_profile_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, key in enumerate(DEFAULT_PROFILE_ORDER, start=1):
        profile = DEFAULT_LOAD_PROFILES_BY_KEY[key]
        rows.append(
            {
                "key": key,
                "label": DEFAULT_PROFILE_LABELS_BY_KEY[key],
                "category": str(profile["category"]),
                "exercise_factor": float(profile["exercise_factor"]),
                "compound_factor": float(profile["compound_factor"]),
                "back_factor": float(profile["back_factor"]),
                "is_builtin": True,
                "is_active": True,
                "sort_order": index * 10,
                "exercise_count": 0,
            }
        )
    return rows
