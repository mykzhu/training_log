import os
from pathlib import Path


DB_PATH = Path(os.getenv("DB_PATH", "data/training.db"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()

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
