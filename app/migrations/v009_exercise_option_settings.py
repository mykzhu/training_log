import sqlite3


VERSION = 9
NAME = "exercise_option_settings"


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
    ensure_column(conn, "exercises", "default_weight", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "exercises", "min_weight", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "exercises", "max_weight", "REAL NOT NULL DEFAULT 200")
    ensure_column(conn, "exercises", "weight_step", "REAL NOT NULL DEFAULT 2.5")
    ensure_column(conn, "exercises", "default_reps", "INTEGER NOT NULL DEFAULT 10")
    ensure_column(conn, "exercises", "min_reps", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "exercises", "max_reps", "INTEGER NOT NULL DEFAULT 50")
    ensure_column(conn, "exercises", "reps_step", "INTEGER NOT NULL DEFAULT 1")
