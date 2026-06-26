import sqlite3


VERSION = 5
NAME = "performance_indexes"


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


def up(conn: sqlite3.Connection) -> None:
    ensure_case_insensitive_exercise_name_index(conn)
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

        CREATE INDEX IF NOT EXISTS idx_exercise_weight_options_exercise
        ON exercise_weight_options(exercise_id, sort_order, weight);
        """
    )