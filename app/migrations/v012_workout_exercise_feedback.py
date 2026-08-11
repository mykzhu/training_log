import sqlite3


VERSION = 12
NAME = "workout_exercise_feedback"


def up(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workout_exercise_feedback (
            workout_exercise_id INTEGER PRIMARY KEY,
            back_pain_before INTEGER CHECK (
                back_pain_before BETWEEN 0 AND 10
            ),
            back_pain_after INTEGER CHECK (
                back_pain_after BETWEEN 0 AND 10
            ),
            response TEXT CHECK (
                response IN ('helped', 'same', 'worse', 'unknown')
            ),
            notes TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (workout_exercise_id)
                REFERENCES workout_exercises(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS active_draft_exercise_feedback (
            draft_exercise_id INTEGER PRIMARY KEY,
            back_pain_before INTEGER CHECK (
                back_pain_before BETWEEN 0 AND 10
            ),
            back_pain_after INTEGER CHECK (
                back_pain_after BETWEEN 0 AND 10
            ),
            response TEXT CHECK (
                response IN ('helped', 'same', 'worse', 'unknown')
            ),
            notes TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (draft_exercise_id)
                REFERENCES active_draft_exercises(id)
                ON DELETE CASCADE
        );
        """
    )
