import sqlite3


VERSION = 11
NAME = "snapshot_exercise_measurements"


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
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def up(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "workout_exercises", "measurement_type", "TEXT")
    ensure_column(conn, "workout_exercises", "reps_unit", "TEXT")
    ensure_column(conn, "active_draft_exercises", "measurement_type", "TEXT")
    ensure_column(conn, "active_draft_exercises", "reps_unit", "TEXT")

    conn.execute(
        """
        UPDATE workout_exercises
        SET measurement_type = (
                SELECT COALESCE(e.measurement_type, 'weighted_reps')
                FROM exercises e
                WHERE e.id = workout_exercises.exercise_id
            ),
            reps_unit = (
                SELECT COALESCE(e.reps_unit, 'reps')
                FROM exercises e
                WHERE e.id = workout_exercises.exercise_id
            )
        WHERE measurement_type IS NULL
           OR measurement_type = ''
           OR reps_unit IS NULL
           OR reps_unit = ''
        """
    )
    conn.execute(
        """
        UPDATE active_draft_exercises
        SET measurement_type = (
                SELECT COALESCE(e.measurement_type, 'weighted_reps')
                FROM exercises e
                WHERE e.id = active_draft_exercises.exercise_id
            ),
            reps_unit = (
                SELECT COALESCE(e.reps_unit, 'reps')
                FROM exercises e
                WHERE e.id = active_draft_exercises.exercise_id
            )
        WHERE measurement_type IS NULL
           OR measurement_type = ''
           OR reps_unit IS NULL
           OR reps_unit = ''
        """
    )
