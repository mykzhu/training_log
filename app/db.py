import logging
import sqlite3

from app import config
from app.services.analysis_service import (
    is_supported_profile_key,
    profile_key_for_exercise_name,
)


logger = logging.getLogger("training_log")

EXERCISE_SETTINGS_WEIGHT_MIGRATION_KEY = "exercise_settings_weight_migration_v1"
DEFAULT_WEIGHT_OPTIONS_BY_PROFILE: dict[str, tuple[float, ...]] = {
    "deadlift": (40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100),
    "goblet_squat": (12, 16, 20, 24, 28, 32),
    "db_bench_press": (10, 12.5, 15, 17.5, 20, 22.5, 25),
    "db_row": (10, 12.5, 15, 17.5, 20, 22.5, 25, 30),
    "ez_curl": (10, 12.5, 15, 17.5, 20, 22.5),
    "triceps_extension": (10, 12.5, 15, 17.5, 20, 22.5),
    "lateral_raise": (2.5, 5, 7.5, 10, 12.5, 15),
    "crunches": (0,),
}


def get_db() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def seed_default_exercises(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    if count != 0:
        return

    for index, exercise in enumerate(config.DEFAULT_EXERCISES, start=1):
        conn.execute(
            """
            INSERT INTO exercises (
                name,
                is_active,
                sort_order,
                profile_key
            )
            VALUES (?, 1, ?, ?)
            """,
            (
                exercise,
                index * 10,
                profile_key_for_exercise_name(exercise),
            ),
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


def ensure_case_insensitive_exercise_name_index(conn: sqlite3.Connection) -> None:
    duplicates = conn.execute(
        """
        SELECT lower(name) AS normalized_name, COUNT(*) AS count
        FROM exercises
        GROUP BY lower(name)
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    if duplicates:
        names = ", ".join(str(row["normalized_name"]) for row in duplicates)
        raise RuntimeError(
            f"Exercise names must be unique ignoring case before migration: {names}"
        )

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_exercises_name_nocase
        ON exercises(name COLLATE NOCASE)
        """
    )


def get_metadata(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = ?",
        (key,),
    ).fetchone()

    return str(row["value"]) if row else None


def set_metadata(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO app_metadata (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def insert_weight_options(
    conn: sqlite3.Connection,
    exercise_id: int,
    weights: list[float] | tuple[float, ...],
) -> None:
    for index, weight in enumerate(sorted({round(float(value), 4) for value in weights}), start=1):
        conn.execute(
            """
            INSERT OR IGNORE INTO exercise_weight_options (
                exercise_id,
                weight,
                sort_order
            )
            VALUES (?, ?, ?)
            """,
            (exercise_id, weight, index * 10),
        )


def seed_initial_weight_options(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT id, profile_key
        FROM exercises
        ORDER BY sort_order ASC, id ASC
        """
    ).fetchall()

    for row in rows:
        exercise_id = int(row["id"])
        profile_key = str(row["profile_key"] or "accessory")
        weights = DEFAULT_WEIGHT_OPTIONS_BY_PROFILE.get(profile_key, ())
        if weights:
            insert_weight_options(conn, exercise_id, weights)


def migrate_historical_weight_options(conn: sqlite3.Connection) -> None:
    historical_rows = conn.execute(
        """
        SELECT DISTINCT
            we.exercise_id,
            se.weight
        FROM set_entries se
        JOIN workout_exercises we ON we.id = se.workout_exercise_id
        UNION
        SELECT DISTINCT
            ade.exercise_id,
            ads.weight
        FROM active_draft_sets ads
        JOIN active_draft_exercises ade ON ade.id = ads.draft_exercise_id
        ORDER BY exercise_id ASC, weight ASC
        """
    ).fetchall()

    weights_by_exercise: dict[int, list[float]] = {}
    for row in historical_rows:
        weights_by_exercise.setdefault(int(row["exercise_id"]), []).append(
            float(row["weight"])
        )

    for exercise_id, weights in weights_by_exercise.items():
        insert_weight_options(conn, exercise_id, weights)


def initialize_exercise_settings(
    conn: sqlite3.Connection,
    *,
    force_weight_migration: bool = False,
) -> None:
    rows = conn.execute(
        """
        SELECT id, name, sort_order, profile_key
        FROM exercises
        ORDER BY id ASC
        """
    ).fetchall()
    default_order = {
        name: index
        for index, name in enumerate(config.DEFAULT_EXERCISES, start=1)
    }
    ordered_rows = sorted(
        rows,
        key=lambda row: (
            default_order.get(str(row["name"]), 9999),
            str(row["name"]).lower(),
            int(row["id"]),
        ),
    )

    for index, row in enumerate(ordered_rows, start=1):
        exercise_id = int(row["id"])

        if int(row["sort_order"] or 0) == 0:
            conn.execute(
                """
                UPDATE exercises
                SET sort_order = ?
                WHERE id = ?
                """,
                (index * 10, exercise_id),
            )

        profile_key = str(row["profile_key"] or "")
        if not profile_key or not is_supported_profile_key(profile_key):
            conn.execute(
                """
                UPDATE exercises
                SET profile_key = ?
                WHERE id = ?
                """,
                (profile_key_for_exercise_name(str(row["name"])), exercise_id),
            )

    if force_weight_migration or not get_metadata(
        conn,
        EXERCISE_SETTINGS_WEIGHT_MIGRATION_KEY,
    ):
        migrate_historical_weight_options(conn)
        seed_initial_weight_options(conn)
        set_metadata(conn, EXERCISE_SETTINGS_WEIGHT_MIGRATION_KEY, "1")


def init_db() -> None:
    logger.info("db.init.start db_path=%s", config.DB_PATH)

    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                profile_key TEXT
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

            CREATE TABLE IF NOT EXISTS exercise_weight_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exercise_id INTEGER NOT NULL,
                weight REAL NOT NULL CHECK (weight >= 0),
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE,
                UNIQUE (exercise_id, weight)
            );

            CREATE INDEX IF NOT EXISTS idx_exercise_weight_options_exercise
            ON exercise_weight_options(exercise_id, sort_order, weight);

            CREATE TABLE IF NOT EXISTS app_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        ensure_column(conn, "exercises", "is_active", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "exercises", "sort_order", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "exercises", "profile_key", "TEXT")
        ensure_column(conn, "workouts", "session_rpe", "INTEGER")
        ensure_column(conn, "workouts", "lower_back_pain", "INTEGER")
        ensure_column(conn, "workouts", "duration_seconds", "INTEGER")

        seed_default_exercises(conn)
        initialize_exercise_settings(conn)
        ensure_case_insensitive_exercise_name_index(conn)

        logger.info("db.init.done")
