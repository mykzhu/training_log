import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from app import config
from app.db import get_db, init_db
from app.routes.api_stats import get_stats
from app.routes.api_workouts import get_workouts
from app.services.recovery_service import build_recovery_context


class CountingConnection(sqlite3.Connection):
    select_count = 0

    def execute(self, sql: str, parameters: Any = (), /) -> sqlite3.Cursor:
        normalized = sql.lstrip().upper()
        if normalized.startswith("SELECT") or normalized.startswith("WITH"):
            type(self).select_count += 1

        return super().execute(sql, parameters)


class QueryCountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_connect = sqlite3.connect

        def connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
            kwargs.setdefault("factory", CountingConnection)
            return self.original_connect(*args, **kwargs)

        sqlite3.connect = connect
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()

    def tearDown(self) -> None:
        sqlite3.connect = self.original_connect
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def reset_query_count(self) -> None:
        CountingConnection.select_count = 0

    def exercise_id(self, exercise_name: str) -> int:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id FROM exercises WHERE name = ?",
                (exercise_name,),
            ).fetchone()

        if row is None:
            raise AssertionError(f"Seed exercise not found: {exercise_name}")

        return int(row["id"])

    def insert_workout(
        self,
        *,
        created_at: str,
        weight: float,
        reps: int = 5,
        session_rpe: int | None = 5,
        lower_back_pain: int | None = 2,
    ) -> int:
        exercise_id = self.exercise_id("Deadlift")

        with get_db() as conn:
            workout_cursor = conn.execute(
                """
                INSERT INTO workouts (
                    workout_date,
                    created_at,
                    finished_at,
                    session_rpe,
                    lower_back_pain,
                    duration_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at[:10],
                    created_at,
                    f"{created_at[:10]}T11:00:00",
                    session_rpe,
                    lower_back_pain,
                    3600,
                ),
            )
            workout_id = int(workout_cursor.lastrowid)

            workout_exercise_cursor = conn.execute(
                """
                INSERT INTO workout_exercises (workout_id, exercise_id, position)
                VALUES (?, ?, ?)
                """,
                (workout_id, exercise_id, 1),
            )
            workout_exercise_id = int(workout_exercise_cursor.lastrowid)

            conn.execute(
                """
                INSERT INTO set_entries (
                    workout_exercise_id,
                    set_number,
                    weight,
                    reps,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (workout_exercise_id, 1, weight, reps, created_at),
            )

        return workout_id

    def seed_workouts(self, count: int = 12) -> None:
        for index in range(count):
            self.insert_workout(
                created_at=f"2026-06-{index + 1:02d}T10:00:00",
                weight=100 + index,
            )

    def test_workout_history_summaries_use_batched_queries(self) -> None:
        self.seed_workouts()

        self.reset_query_count()
        response = get_workouts(limit=10)

        self.assertEqual(len(response["workouts"]), 10)
        self.assertLessEqual(CountingConnection.select_count, 7)

    def test_stats_use_batched_queries(self) -> None:
        self.seed_workouts()

        self.reset_query_count()
        response = get_stats(limit="10")

        self.assertEqual(response["stats"]["summary"]["workout_count"], 10)
        self.assertLessEqual(CountingConnection.select_count, 8)

    def test_recovery_context_uses_one_history_window_query(self) -> None:
        self.seed_workouts()

        self.reset_query_count()
        context = build_recovery_context(as_of="2026-06-13T10:00:00")

        self.assertEqual(context["last_42d"]["workout_count"], 12)
        self.assertLessEqual(CountingConnection.select_count, 8)


if __name__ == "__main__":
    unittest.main()
