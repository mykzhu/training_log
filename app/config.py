import os
from pathlib import Path


DB_PATH = Path(os.getenv("DB_PATH", "data/training.db"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
FRONTEND_DIST_DIR = Path(
    os.getenv(
        "FRONTEND_DIST_DIR",
        Path(__file__).resolve().parent / "static",
    )
)

DEFAULT_EXERCISES = (
    "Deadlift",
    "Goblet Squat",
    "DB Bench Press",
    "DB Row",
    "EZ Curl",
    "Triceps Extension",
    "Lateral Raise",
    "Crunches",
)
