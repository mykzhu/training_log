import tempfile
import unittest
from pathlib import Path
from typing import Any

from app import config
from app.db import get_db, init_db
import app.main as main
from app.routes.api_stats import get_stats


class StatsApiTests(unittest.TestCase):
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

    def seed_stats_workouts(self) -> tuple[int, int]:
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
            lower_back_pain=4,
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 110, "reps": 5}],
                },
            ],
        )

        return first_id, second_id

    def test_stats_route_is_registered(self) -> None:
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in main.app.routes
            if hasattr(route, "methods")
        }

        self.assertIn(("/api/v1/stats", ("GET",)), routes)

    def test_get_stats_returns_summary_charts_and_chronological_workouts(self) -> None:
        first_id, second_id = self.seed_stats_workouts()

        response = get_stats()

        self.assertEqual(response["limit"], 30)
        self.assertEqual(
            [workout["id"] for workout in response["stats"]["workouts"]],
            [first_id, second_id],
        )
        self.assertEqual(response["stats"]["summary"]["workout_count"], 2)
        self.assertEqual(response["stats"]["summary"]["total_volume"], 1050.0)
        self.assertEqual(response["stats"]["summary"]["total_reps"], 10)
        self.assertEqual(response["stats"]["summary"]["total_sets"], 2)
        self.assertEqual(response["stats"]["summary"]["avg_rpe"], 6.0)
        self.assertEqual(response["stats"]["summary"]["avg_back_pain"], 3.0)
        self.assertIn("volume", response["charts"])
        self.assertIn("load", response["charts"])
        self.assertIn("sparkbars", response["charts"])

    def test_get_stats_limits_to_recent_workouts(self) -> None:
        _, second_id = self.seed_stats_workouts()

        response = get_stats(limit="1")

        self.assertEqual(response["limit"], 1)
        self.assertEqual(response["stats"]["summary"]["workout_count"], 1)
        self.assertEqual(response["stats"]["summary"]["total_volume"], 550.0)
        self.assertEqual(
            [workout["id"] for workout in response["stats"]["workouts"]],
            [second_id],
        )

    def test_get_stats_accepts_all_limit(self) -> None:
        first_id, second_id = self.seed_stats_workouts()

        response = get_stats(limit="all")

        self.assertEqual(response["limit"], "all")
        self.assertEqual(response["stats"]["summary"]["workout_count"], 2)
        self.assertEqual(
            [workout["id"] for workout in response["stats"]["workouts"]],
            [first_id, second_id],
        )

    def test_get_stats_uses_default_for_invalid_limit(self) -> None:
        self.seed_stats_workouts()

        response = get_stats(limit="not-a-number")

        self.assertEqual(response["limit"], 30)
        self.assertEqual(response["stats"]["summary"]["workout_count"], 2)


if __name__ == "__main__":
    unittest.main()
