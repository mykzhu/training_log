import sqlite3


VERSION = 2
NAME = "workout_metadata"


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
    ensure_column(conn, "workouts", "session_rpe", "INTEGER")
    ensure_column(conn, "workouts", "lower_back_pain", "INTEGER")
    ensure_column(conn, "workouts", "duration_seconds", "INTEGER")