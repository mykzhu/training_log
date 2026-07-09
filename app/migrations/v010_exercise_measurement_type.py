import sqlite3


VERSION = 10
NAME = "exercise_measurement_type"


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
    ensure_column(
        conn,
        "exercises",
        "measurement_type",
        "TEXT NOT NULL DEFAULT 'weighted_reps'",
    )
    ensure_column(conn, "exercises", "reps_unit", "TEXT NOT NULL DEFAULT 'reps'")

    conn.execute(
        """
        UPDATE exercises
        SET measurement_type = 'weighted_reps',
            reps_unit = 'reps'
        WHERE measurement_type IS NULL
           OR trim(measurement_type) = ''
           OR reps_unit IS NULL
           OR trim(reps_unit) = ''
        """
    )
    conn.execute(
        """
        UPDATE exercises
        SET measurement_type = 'bodyweight_reps',
            reps_unit = 'reps'
        WHERE lower(name) LIKE '%crunch%'
        """
    )
    conn.execute(
        """
        UPDATE exercises
        SET measurement_type = 'loaded_carry_time',
            reps_unit = 'sec'
        WHERE lower(name) LIKE '%carry%'
        """
    )
