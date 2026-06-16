import math
import tempfile
import unittest
from pathlib import Path
from typing import Any

from app import config
from app.db import get_db, init_db
from app.repositories.workouts import get_workout_details
from app.routes.api_workouts import update_workout_endpoint
from app.schemas import WorkoutUpdateRequest
from app.services import draft_service
from app.services.stats_service import build_stats, build_workout_analysis


class MainDatabaseBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        self.original_active_draft = draft_service.ACTIVE_WORKOUT_DRAFT

        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()
        draft_service.clear_active_workout_draft()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        draft_service.ACTIVE_WORKOUT_DRAFT = self.original_active_draft
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

    def test_build_stats_aggregates_real_database_rows(self) -> None:
        first_workout_id = self.insert_workout(
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
        second_workout_id = self.insert_workout(
            created_at="2026-06-08T10:00:00",
            session_rpe=7,
            lower_back_pain=None,
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 110, "reps": 5}],
                },
            ],
        )

        stats = build_stats(limit=30)

        self.assertEqual(
            [item["id"] for item in stats["workouts"]],
            [first_workout_id, second_workout_id],
        )

        summary = stats["summary"]
        self.assertEqual(summary["workout_count"], 2)
        self.assertEqual(summary["total_volume"], 1050)
        self.assertEqual(summary["total_reps"], 10)
        self.assertEqual(summary["total_sets"], 2)
        self.assertEqual(summary["avg_intensity"], 105)
        self.assertEqual(summary["avg_rpe"], 6)
        self.assertEqual(summary["avg_back_pain"], 2)
        self.assertTrue(math.isclose(summary["total_load_score"], 5.3064))
        self.assertTrue(math.isclose(summary["total_compound_score"], 3.96))
        self.assertTrue(math.isclose(summary["total_back_stress_score"], 4.95))
        self.assertTrue(math.isclose(summary["avg_relative_intensity"], 110.0))

        first, second = stats["workouts"]
        self.assertEqual(first["load_label"], "Light")
        self.assertTrue(math.isclose(first["load_score"], 1.98))
        self.assertIsNone(first["intensity_score"])
        self.assertEqual(second["load_label"], "Light")
        self.assertTrue(math.isclose(second["load_score"], 3.3264))
        self.assertTrue(math.isclose(second["intensity_score"], 110.0))

        deadlift_stats = stats["exercise_stats"][0]
        self.assertEqual(deadlift_stats["exercise_id"], self.exercise_id("Deadlift"))
        self.assertEqual(deadlift_stats["name"], "Deadlift")
        self.assertEqual(deadlift_stats["total_volume"], 1050)
        self.assertEqual(deadlift_stats["total_reps"], 10)
        self.assertEqual(deadlift_stats["total_sets"], 2)
        self.assertTrue(math.isclose(deadlift_stats["best_e1rm"], 128.33333333333334))
        self.assertEqual(
            deadlift_stats["best_set"],
            {
                "weight": 110.0,
                "reps": 5,
                "workout_id": second_workout_id,
                "date": "2026-06-08",
            },
        )

    def test_build_workout_analysis_detects_prs_against_previous_workouts(self) -> None:
        self.insert_workout(
            created_at="2026-06-01T10:00:00",
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
        current_workout_id = self.insert_workout(
            created_at="2026-06-08T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [
                        {"weight": 105, "reps": 6},
                        {"weight": 90, "reps": 10},
                    ],
                },
            ],
        )

        workout_details = get_workout_details(current_workout_id)
        analysis = build_workout_analysis(current_workout_id, workout_details)

        self.assertEqual(
            analysis["prs"],
            [
                {"exercise_name": "Deadlift", "type": "Weight PR"},
                {"exercise_name": "Deadlift", "type": "Rep PR"},
                {"exercise_name": "Deadlift", "type": "e1RM PR"},
                {"exercise_name": "Deadlift", "type": "Volume PR"},
            ],
        )

        exercise_analysis = analysis["exercises"][0]
        self.assertEqual(exercise_analysis["exercise_name"], "Deadlift")
        self.assertEqual(
            exercise_analysis["pr_flags"],
            ["Weight PR", "Rep PR", "e1RM PR", "Volume PR"],
        )
        self.assertEqual(exercise_analysis["best_set"], {"weight": 105.0, "reps": 6})
        self.assertEqual(exercise_analysis["best_e1rm_set"], {"weight": 105.0, "reps": 6})
        self.assertTrue(math.isclose(exercise_analysis["best_e1rm"], 126.0))

    def test_update_workout_endpoint_can_clear_optional_metadata(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=8,
            lower_back_pain=4,
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )

        response = update_workout_endpoint(
            workout_id,
            WorkoutUpdateRequest(
                session_rpe=None,
                lower_back_pain=None,
            ),
        )

        self.assertIsNone(response["workout"]["session_rpe"])
        self.assertIsNone(response["workout"]["lower_back_pain"])

        with get_db() as conn:
            workout = conn.execute(
                """
                SELECT session_rpe, lower_back_pain
                FROM workouts
                WHERE id = ?
                """,
                (workout_id,),
            ).fetchone()

        self.assertIsNone(workout["session_rpe"])
        self.assertIsNone(workout["lower_back_pain"])


if __name__ == "__main__":
    unittest.main()
