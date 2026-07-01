import os
from pathlib import Path


def parse_int_env_value(
    raw: str | None,
    default: int,
    *,
    minimum: int | None = None,
) -> int:
    if raw is None or not raw.strip():
        value = default
    else:
        try:
            value = int(raw)
        except ValueError:
            value = default

    if minimum is not None:
        value = max(value, minimum)
    return value


def int_env(name: str, default: int, *, minimum: int | None = None) -> int:
    return parse_int_env_value(os.getenv(name), default, minimum=minimum)


DB_PATH = Path(os.getenv("DB_PATH", "data/training.db"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
GARMIN_TOKEN_DIR = Path(os.getenv("GARMIN_TOKEN_DIR", "/data/garmin_tokens"))
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Uzhgorod")
APP_URL_PREFIX = os.getenv("APP_URL_PREFIX", "").strip("/")
FRONTEND_DIST_DIR = Path(
    os.getenv(
        "FRONTEND_DIST_DIR",
        Path(__file__).resolve().parent / "static",
    )
)
GARMIN_AUTO_SYNC_CHECK_INTERVAL_SECONDS = int_env(
    "GARMIN_AUTO_SYNC_CHECK_INTERVAL_SECONDS",
    3600,
    minimum=300,
)

DEFAULT_EXERCISES = (
    "Deadlift",
    "Squats",
    "DB Squats",
    "Bench Press",
    "45-Degree Bench Press",
    "DB Bench Press",
    "Shoulder Press",
    "DB Shoulder Press",
    "EZ Biceps",
    "Triceps Pushdown",
    "Crunches",
)

DEFAULT_EXERCISE_PROFILE_KEYS = {
    "Deadlift": "deadlift",
    "Squats": "squats",
    "DB Squats": "db_squats",
    "Bench Press": "bench_press",
    "45-Degree Bench Press": "incline_bench_press",
    "DB Bench Press": "db_bench_press",
    "Shoulder Press": "shoulder_press",
    "DB Shoulder Press": "db_shoulder_press",
    "EZ Biceps": "ez_curl",
    "Triceps Pushdown": "triceps_pushdown",
    "Crunches": "crunches",
}
