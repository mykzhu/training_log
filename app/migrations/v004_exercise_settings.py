import sqlite3


VERSION = 4
NAME = "exercise_settings"


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
    ensure_column(conn, "exercises", "is_active", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "exercises", "sort_order", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "exercises", "profile_key", "TEXT")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS exercise_weight_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER NOT NULL,
            weight REAL NOT NULL CHECK (weight >= 0),
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE,
            UNIQUE (exercise_id, weight)
        );

        CREATE TABLE IF NOT EXISTS app_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )