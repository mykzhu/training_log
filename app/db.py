import logging
import sqlite3

from app import config


logger = logging.getLogger("training_log")


def get_db() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def seed_default_exercises(conn: sqlite3.Connection) -> None:
    for exercise in config.DEFAULT_EXERCISES:
        conn.execute(
            "INSERT OR IGNORE INTO exercises (name) VALUES (?)",
            (exercise,),
        )


def ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }

    if column_name not in columns:
        logger.info(
            "db.migration.add_column table=%s column=%s definition=%s",
            table_name,
            column_name,
            column_definition,
        )
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def init_db() -> None:
    logger.info("db.init.start db_path=%s", config.DB_PATH)

    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds INTEGER
            );

            CREATE TABLE IF NOT EXISTS workout_exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_id INTEGER NOT NULL,
                exercise_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE,
                FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS set_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_exercise_id INTEGER NOT NULL,
                set_number INTEGER NOT NULL,
                weight REAL NOT NULL DEFAULT 0,
                reps INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (workout_exercise_id) REFERENCES workout_exercises(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS active_workout_draft (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                started_at TEXT NOT NULL,
                session_rpe INTEGER,
                lower_back_pain INTEGER,
                next_workout_exercise_id INTEGER NOT NULL,
                next_set_id INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS active_draft_exercises (
                id INTEGER PRIMARY KEY,
                draft_id INTEGER NOT NULL DEFAULT 1,
                exercise_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                FOREIGN KEY (draft_id) REFERENCES active_workout_draft(id) ON DELETE CASCADE,
                FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS active_draft_sets (
                id INTEGER PRIMARY KEY,
                draft_exercise_id INTEGER NOT NULL,
                set_number INTEGER NOT NULL,
                weight REAL NOT NULL DEFAULT 0,
                reps INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (draft_exercise_id) REFERENCES active_draft_exercises(id) ON DELETE CASCADE
            );
            """
        )

        ensure_column(conn, "workouts", "session_rpe", "INTEGER")
        ensure_column(conn, "workouts", "lower_back_pain", "INTEGER")
        ensure_column(conn, "workouts", "duration_seconds", "INTEGER")

        seed_default_exercises(conn)

        logger.info("db.init.done")
