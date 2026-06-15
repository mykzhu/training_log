import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app import config
from app.db import get_db, init_db
import app.main as main
from app.routes.api_workouts import get_workout_detail, get_workouts


class WorkoutsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

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
        exercises: list[dict[str, Any]],
        session_rpe: int | None = None,
        lower_back_pain: int | None = None,
    ) -> int:
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

            for position, exercise in enumerate(exercises, start=1):
                workout_exercise_cursor = conn.execute(
                    """
                    INSERT INTO workout_exercises (
                        workout_id,
                        exercise_id,
                        position
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        workout_id,
                        self.exercise_id(str(exercise["name"])),
                        position,
                    ),
                )
                workout_exercise_id = int(workout_exercise_cursor.lastrowid)

                for set_number, set_entry in enumerate(exercise["sets"], start=1):
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
                        (
                            workout_exercise_id,
                            set_number,
                            float(set_entry["weight"]),
                            int(set_entry["reps"]),
                            created_at,
                        ),
                    )

        return workout_id

    def test_workout_routes_are_registered(self) -> None:
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in main.app.routes
            if hasattr(route, "methods")
        }

        self.assertIn(("/api/v1/workouts", ("GET",)), routes)
        self.assertIn(("/api/v1/workouts/{workout_id}", ("GET",)), routes)

    def test_get_workouts_returns_recent_summaries(self) -> None:
        first_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=5,
            lower_back_pain=2,
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )
        second_id = self.insert_workout(
            created_at="2026-06-08T10:00:00",
            session_rpe=7,
            lower_back_pain=None,
            exercises=[
                {
                    "name": "Goblet Squat",
                    "sets": [{"weight": 32, "reps": 10}],
                },
            ],
        )

        response = get_workouts(limit=30)

        self.assertEqual(response["limit"], 30)
        self.assertEqual(
            [workout["id"] for workout in response["workouts"]],
            [second_id, first_id],
        )
        self.assertEqual(response["workouts"][0]["total_volume"], 320.0)
        self.assertEqual(response["workouts"][0]["total_reps"], 10)
        self.assertEqual(response["workouts"][0]["total_sets"], 1)
        self.assertEqual(response["workouts"][0]["exercises_count"], 1)
        self.assertIn("load_score", response["workouts"][0]["load_metrics"])

    def test_get_workout_detail_returns_exercises_sets_and_metrics(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=6,
            lower_back_pain=1,
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [
                        {"weight": 100, "reps": 5},
                        {"weight": 90, "reps": 8},
                    ],
                },
            ],
        )

        response = get_workout_detail(workout_id)

        self.assertEqual(response["workout"]["id"], workout_id)
        self.assertEqual(response["workout"]["session_rpe"], 6)
        self.assertEqual(response["total_volume"], 1220.0)
        self.assertEqual(response["total_reps"], 13)
        self.assertEqual(response["total_sets"], 2)
        self.assertEqual(response["exercises"][0]["exercise_name"], "Deadlift")
        self.assertEqual(response["exercises"][0]["total_sets"], 2)
        self.assertEqual(response["exercises"][0]["sets"][0]["weight"], 100.0)
        self.assertIn("load_label", response["load_metrics"])

    def test_get_workout_detail_returns_404_for_missing_workout(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            get_workout_detail(9999)

        self.assertEqual(exc.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
