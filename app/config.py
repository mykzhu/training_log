import os
from pathlib import Path


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
