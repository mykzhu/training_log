import logging
import sqlite3

from app import config
from app.migrations.runner import run_migrations
from app.repositories.analysis_profiles import (
    ensure_default_analysis_profiles,
    profile_exists,
)
from app.services.default_analysis_profiles import profile_key_for_exercise_name


logger = logging.getLogger("training_log")

EXERCISE_SETTINGS_WEIGHT_MIGRATION_KEY = "exercise_settings_weight_migration_v1"
DEFAULT_WEIGHT_OPTIONS_BY_PROFILE: dict[str, tuple[float, ...]] = {
    "deadlift": (40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100),
    "db_bench_press": (10, 12.5, 15, 17.5, 20, 22.5, 25),
    "db_row": (10, 12.5, 15, 17.5, 20, 22.5, 25, 30),
    "ez_curl": (10, 12.5, 15, 17.5, 20, 22.5),
    "triceps_extension": (10, 12.5, 15, 17.5, 20, 22.5),
    "lateral_raise": (2.5, 5, 7.5, 10, 12.5, 15),
    "crunches": (0,),
    "squats": (
        20, 25, 30, 35, 40, 45, 50, 55, 60,
        65, 70, 75, 80, 85, 90, 95, 100,
    ),
    "db_squats": (
        5, 7.5, 10, 12.5, 15, 17.5, 20,
        22.5, 25, 27.5, 30, 32.5, 35,
    ),
    "bench_press": (
        20, 25, 30, 35, 40, 45, 50, 55,
        60, 65, 70, 75, 80, 85, 90, 95, 100,
    ),
    "incline_bench_press": (
        20, 25, 30, 35, 40, 45, 50,
        55, 60, 65, 70, 75, 80,
    ),
    "shoulder_press": (
        10, 15, 20, 25, 30, 35,
        40, 45, 50, 55, 60,
    ),
    "db_shoulder_press": (
        5, 7.5, 10, 12.5, 15, 17.5,
        20, 22.5, 25, 27.5, 30,
    ),
    "triceps_pushdown": (
        5, 10, 15, 20, 25,
        30, 35, 40, 45, 50,
    ),
}


def get_db() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def seed_default_exercises(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    if count != 0:
        return

    for index, exercise in enumerate(config.DEFAULT_EXERCISES, start=1):
        normalized_name = exercise.lower()
        measurement_type = "weighted_reps"
        reps_unit = "reps"
        if "crunch" in normalized_name:
            measurement_type = "bodyweight_reps"
        elif "carry" in normalized_name:
            measurement_type = "loaded_carry_time"
            reps_unit = "sec"

        conn.execute(
            """
            INSERT INTO exercises (
                name,
                is_active,
                sort_order,
                profile_key,
                measurement_type,
                reps_unit
            )
            VALUES (?, 1, ?, ?, ?, ?)
            """,
            (
                exercise,
                index * 10,
                config.DEFAULT_EXERCISE_PROFILE_KEYS[exercise],
                measurement_type,
                reps_unit,
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


def renumber_grouped_positions(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    group_column: str,
    position_column: str,
) -> None:
    groups = conn.execute(
        f"""
        SELECT DISTINCT {group_column} AS group_id
        FROM {table_name}
        ORDER BY {group_column} ASC
        """
    ).fetchall()

    for group in groups:
        group_id = int(group["group_id"])
        rows = conn.execute(
            f"""
            SELECT id
            FROM {table_name}
            WHERE {group_column} = ?
            ORDER BY {position_column} ASC, id ASC
            """,
            (group_id,),
        ).fetchall()

        for index, row in enumerate(rows, start=1):
            conn.execute(
                f"""
                UPDATE {table_name}
                SET {position_column} = ?
                WHERE id = ?
                """,
                (index, int(row["id"])),
            )


def normalize_ordering_columns(conn: sqlite3.Connection) -> None:
    renumber_grouped_positions(
        conn,
        table_name="workout_exercises",
        group_column="workout_id",
        position_column="position",
    )
    renumber_grouped_positions(
        conn,
        table_name="set_entries",
        group_column="workout_exercise_id",
        position_column="set_number",
    )
    renumber_grouped_positions(
        conn,
        table_name="active_draft_exercises",
        group_column="draft_id",
        position_column="position",
    )
    renumber_grouped_positions(
        conn,
        table_name="active_draft_sets",
        group_column="draft_exercise_id",
        position_column="set_number",
    )


def ensure_performance_indexes(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_workouts_created_at_id
        ON workouts(created_at, id);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_workout_exercises_workout_position
        ON workout_exercises(workout_id, position);

        CREATE INDEX IF NOT EXISTS idx_workout_exercises_exercise_workout
        ON workout_exercises(exercise_id, workout_id);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_set_entries_exercise_set_number
        ON set_entries(workout_exercise_id, set_number);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_active_draft_exercises_draft_position
        ON active_draft_exercises(draft_id, position);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_active_draft_sets_exercise_set_number
        ON active_draft_sets(draft_exercise_id, set_number);
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
        if not profile_key or not profile_exists(conn, profile_key):
            inferred_profile_key = profile_key_for_exercise_name(str(row["name"]))
            if not profile_exists(conn, inferred_profile_key):
                inferred_profile_key = "accessory"
            conn.execute(
                """
                UPDATE exercises
                SET profile_key = ?
                WHERE id = ?
                """,
                (inferred_profile_key, exercise_id),
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
        run_migrations(conn)
        ensure_default_analysis_profiles(conn)
        seed_default_exercises(conn)
        initialize_exercise_settings(conn)
        normalize_ordering_columns(conn)
        ensure_case_insensitive_exercise_name_index(conn)
        ensure_performance_indexes(conn)

        logger.info("db.init.done")
