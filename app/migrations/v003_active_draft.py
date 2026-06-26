import sqlite3


VERSION = 3
NAME = "active_draft"


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
    conn.executescript(
        """
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
    ensure_column(conn, "active_workout_draft", "session_rpe", "INTEGER")
    ensure_column(conn, "active_workout_draft", "lower_back_pain", "INTEGER")