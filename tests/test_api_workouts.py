import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app import config
from app.db import get_db, init_db
import app.main as main
import app.routes.api_workouts as api_workouts_module
from app.repositories.exercises import create_exercise
from app.repositories.workouts import NumberingConflictError
from app.routes.api_workouts import (
    add_workout_exercise_endpoint,
    add_workout_exercise_set_endpoint,
    delete_workout_endpoint,
    delete_set_endpoint,
    delete_workout_exercise_endpoint,
    duplicate_workout_exercise_set_endpoint,
    get_workout_detail,
    get_workouts,
    update_set_endpoint,
    update_workout_endpoint,
)
from app.schemas import (
    AddExerciseRequest,
    AddSetRequest,
    UpdateSetRequest,
    WorkoutUpdateRequest,
)


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
                exercise_id = self.exercise_id(str(exercise["name"]))
                workout_exercise_cursor = conn.execute(
                    """
                    INSERT INTO workout_exercises (
                        workout_id,
                        exercise_id,
                        position,
                        measurement_type,
                        reps_unit
                    )
                    SELECT
                        ?,
                        e.id,
                        ?,
                        e.measurement_type,
                        e.reps_unit
                    FROM exercises e
                    WHERE e.id = ?
                    """,
                    (
                        workout_id,
                        position,
                        exercise_id,
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

    def get_workout_exercise_id(
        self,
        response: dict[str, Any],
        exercise_name: str,
    ) -> int:
        for exercise in response["exercises"]:
            if exercise["exercise_name"] == exercise_name:
                return int(exercise["workout_exercise_id"])

        raise AssertionError(f"Workout exercise not found: {exercise_name}")

    def test_workout_routes_are_registered(self) -> None:
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in main.app.routes
            if hasattr(route, "methods")
        }

        self.assertIn(("/api/v1/workouts", ("GET",)), routes)
        self.assertIn(("/api/v1/workouts/{workout_id}", ("GET",)), routes)
        self.assertIn(("/api/v1/workouts/{workout_id}", ("PATCH",)), routes)
        self.assertIn(("/api/v1/workouts/{workout_id}", ("DELETE",)), routes)
        self.assertIn(("/api/v1/workouts/{workout_id}/exercises", ("POST",)), routes)
        self.assertIn(
            (
                "/api/v1/workouts/{workout_id}/exercises/{workout_exercise_id}",
                ("DELETE",),
            ),
            routes,
        )
        self.assertIn(
            ("/api/v1/workout-exercises/{workout_exercise_id}/sets", ("POST",)),
            routes,
        )
        self.assertIn(
            (
                "/api/v1/workout-exercises/{workout_exercise_id}/sets/duplicate",
                ("POST",),
            ),
            routes,
        )
        self.assertIn(("/api/v1/sets/{set_id}", ("PATCH",)), routes)
        self.assertIn(("/api/v1/sets/{set_id}", ("DELETE",)), routes)

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
                    "name": "Squats",
                    "sets": [{"weight": 40, "reps": 10}],
                },
            ],
        )

        response = get_workouts(limit=30)

        self.assertEqual(response["limit"], 30)
        self.assertEqual(
            [workout["id"] for workout in response["workouts"]],
            [second_id, first_id],
        )
        self.assertEqual(response["workouts"][0]["total_volume"], 400.0)
        self.assertEqual(response["workouts"][0]["total_reps"], 10)
        self.assertEqual(response["workouts"][0]["total_sets"], 1)
        self.assertEqual(response["workouts"][0]["exercises_count"], 1)
        self.assertIn("load_score", response["workouts"][0]["load_metrics"])

    def test_get_workouts_orders_by_created_at_desc_then_id_desc(self) -> None:
        newer_id = self.insert_workout(
            created_at="2026-06-08T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )
        older_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 90, "reps": 5}],
                },
            ],
        )

        response = get_workouts(limit=30)

        self.assertEqual(
            [workout["id"] for workout in response["workouts"]],
            [newer_id, older_id],
        )

    def test_historical_load_does_not_use_future_workout(self) -> None:
        old_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )
        old_metrics_before = get_workout_detail(old_id)["load_metrics"]

        self.insert_workout(
            created_at="2026-06-15T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 300, "reps": 5}],
                },
            ],
        )

        old_metrics_after = get_workout_detail(old_id)["load_metrics"]

        self.assertIsNone(old_metrics_after["intensity_score"])
        self.assertEqual(
            old_metrics_after["load_score"],
            old_metrics_before["load_score"],
        )

    def test_historical_load_same_timestamp_uses_lower_id_only(self) -> None:
        self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )
        target_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 110, "reps": 5}],
                },
            ],
        )
        self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 300, "reps": 5}],
                },
            ],
        )

        metrics = get_workout_detail(target_id)["load_metrics"]

        self.assertAlmostEqual(metrics["intensity_score"], 110.0)

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
        self.assertIn(100.0, response["exercises"][0]["configured_weights"])
        self.assertIn(100.0, response["exercises"][0]["weight_options"])
        self.assertIn(50, response["exercises"][0]["reps_options"])
        self.assertIn("load_label", response["load_metrics"])
        self.assertIn("load_score", response["load_metrics"])
        self.assertIn("back_stress_score", response["load_metrics"])
        self.assertIn("compound_score", response["load_metrics"])
        self.assertEqual(response["analysis"]["prs"], [])
        self.assertEqual(
            response["analysis"]["exercises"][0]["exercise_name"],
            "Deadlift",
        )

    def test_workout_detail_reports_measurement_specific_set_metrics(self) -> None:
        create_exercise(
            "Suitcase carry",
            is_active=False,
            weights=[24],
        )
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=5,
            lower_back_pain=2,
            exercises=[
                {
                    "name": "Crunches",
                    "sets": [{"weight": 0, "reps": 40}],
                },
                {
                    "name": "Bench Press",
                    "sets": [{"weight": 70, "reps": 8}],
                },
                {
                    "name": "Suitcase carry",
                    "sets": [{"weight": 24, "reps": 45}],
                },
            ],
        )

        response = get_workout_detail(workout_id)
        details = {
            item["exercise_name"]: item
            for item in response["exercises"]
        }

        crunches = details["Crunches"]
        self.assertEqual(crunches["measurement_type"], "bodyweight_reps")
        self.assertEqual(crunches["total_volume_kg"], 0.0)
        self.assertEqual(crunches["bodyweight_reps"], 40)
        self.assertEqual(crunches["duration_seconds"], 0)
        self.assertEqual(crunches["distance_m"], 0)

        bench = details["Bench Press"]
        self.assertEqual(bench["measurement_type"], "weighted_reps")
        self.assertEqual(bench["total_volume_kg"], 560.0)
        self.assertEqual(bench["bodyweight_reps"], 0)
        self.assertEqual(bench["duration_seconds"], 0)
        self.assertEqual(bench["distance_m"], 0)

        carry = details["Suitcase carry"]
        self.assertEqual(carry["measurement_type"], "loaded_carry_time")
        self.assertEqual(carry["reps_unit"], "sec")
        self.assertEqual(carry["total_volume"], 1080.0)
        self.assertEqual(carry["total_volume_kg"], 0.0)
        self.assertEqual(carry["bodyweight_reps"], 0)
        self.assertEqual(carry["duration_seconds"], 45)
        self.assertEqual(carry["distance_m"], 0)

    def test_workout_detail_excludes_loaded_carry_distance_from_kg_volume(self) -> None:
        create_exercise(
            "Farmer carry",
            is_active=False,
            weights=[24],
            measurement_settings={
                "measurement_type": "loaded_carry_distance",
                "reps_unit": "m",
            },
        )
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=5,
            lower_back_pain=2,
            exercises=[
                {
                    "name": "Farmer carry",
                    "sets": [{"weight": 24, "reps": 40}],
                },
            ],
        )

        response = get_workout_detail(workout_id)
        carry = response["exercises"][0]

        self.assertEqual(carry["measurement_type"], "loaded_carry_distance")
        self.assertEqual(carry["reps_unit"], "m")
        self.assertEqual(carry["total_volume"], 960.0)
        self.assertEqual(carry["total_volume_kg"], 0.0)
        self.assertEqual(carry["duration_seconds"], 0)
        self.assertEqual(carry["distance_m"], 40)

    def test_workout_detail_preserves_measurement_snapshot_after_exercise_change(self) -> None:
        create_exercise(
            "Farmer carry",
            is_active=False,
            weights=[24],
            measurement_settings={
                "measurement_type": "loaded_carry_time",
                "reps_unit": "sec",
            },
        )
        first_workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=5,
            lower_back_pain=2,
            exercises=[
                {
                    "name": "Farmer carry",
                    "sets": [{"weight": 24, "reps": 45}],
                },
            ],
        )

        with get_db() as conn:
            conn.execute(
                """
                UPDATE exercises
                SET measurement_type = 'loaded_carry_distance',
                    reps_unit = 'm'
                WHERE name = 'Farmer carry'
                """
            )

        second_workout_id = self.insert_workout(
            created_at="2026-06-02T10:00:00",
            session_rpe=5,
            lower_back_pain=2,
            exercises=[
                {
                    "name": "Farmer carry",
                    "sets": [{"weight": 24, "reps": 40}],
                },
            ],
        )

        first = get_workout_detail(first_workout_id)["exercises"][0]
        second = get_workout_detail(second_workout_id)["exercises"][0]

        self.assertEqual(first["measurement_type"], "loaded_carry_time")
        self.assertEqual(first["reps_unit"], "sec")
        self.assertEqual(first["duration_seconds"], 45)
        self.assertEqual(first["distance_m"], 0)
        self.assertEqual(second["measurement_type"], "loaded_carry_distance")
        self.assertEqual(second["reps_unit"], "m")
        self.assertEqual(second["duration_seconds"], 0)
        self.assertEqual(second["distance_m"], 40)

    def test_get_workout_detail_returns_404_for_missing_workout(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            get_workout_detail(9999)

        self.assertEqual(exc.exception.status_code, 404)

    def test_update_workout_endpoint_updates_datetime_metadata_and_duration(
        self,
    ) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=6,
            lower_back_pain=1,
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
                created_at="2026-06-01T09:30",
                session_rpe=8,
                lower_back_pain=3,
            ),
        )

        self.assertEqual(response["workout"]["created_at"], "2026-06-01T09:30:00")
        self.assertEqual(response["workout"]["workout_date"], "2026-06-01")
        self.assertEqual(response["workout"]["session_rpe"], 8)
        self.assertEqual(response["workout"]["lower_back_pain"], 3)
        self.assertEqual(response["workout"]["duration_seconds"], 5400)

    def test_update_workout_endpoint_can_clear_optional_metadata(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=6,
            lower_back_pain=1,
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )

        response = update_workout_endpoint(
            workout_id,
            WorkoutUpdateRequest(session_rpe=None, lower_back_pain=None),
        )

        self.assertIsNone(response["workout"]["session_rpe"])
        self.assertIsNone(response["workout"]["lower_back_pain"])

    def test_update_workout_endpoint_returns_400_when_no_fields_provided(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )

        with self.assertRaises(HTTPException) as exc:
            update_workout_endpoint(workout_id, WorkoutUpdateRequest())

        self.assertEqual(exc.exception.status_code, 400)

    def test_update_workout_endpoint_returns_404_for_missing_workout(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            update_workout_endpoint(
                9999,
                WorkoutUpdateRequest(session_rpe=5),
            )

        self.assertEqual(exc.exception.status_code, 404)

    def test_delete_workout_endpoint_deletes_workout_and_child_rows(self) -> None:
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

        response = delete_workout_endpoint(workout_id)

        with get_db() as conn:
            workout_count = conn.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]
            workout_exercise_count = conn.execute(
                "SELECT COUNT(*) FROM workout_exercises"
            ).fetchone()[0]
            set_count = conn.execute("SELECT COUNT(*) FROM set_entries").fetchone()[0]

        self.assertTrue(response["deleted"])
        self.assertEqual(response["workout_id"], workout_id)
        self.assertEqual(workout_count, 0)
        self.assertEqual(workout_exercise_count, 0)
        self.assertEqual(set_count, 0)

    def test_delete_workout_endpoint_returns_404_for_missing_workout(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            delete_workout_endpoint(9999)

        self.assertEqual(exc.exception.status_code, 404)

    def test_legacy_edit_workout_flow_updates_sets_and_preserves_order(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=6,
            lower_back_pain=1,
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
                created_at="2026-06-01T09:45",
                session_rpe=7,
                lower_back_pain=2,
            ),
        )
        self.assertEqual(response["workout"]["created_at"], "2026-06-01T09:45:00")
        self.assertEqual(response["workout"]["session_rpe"], 7)
        self.assertEqual(response["workout"]["lower_back_pain"], 2)

        response = add_workout_exercise_endpoint(
            workout_id,
            AddExerciseRequest(exercise_id=self.exercise_id("Squats")),
        )
        self.assertEqual(
            [exercise["exercise_name"] for exercise in response["exercises"]],
            ["Deadlift", "Squats"],
        )
        self.assertEqual(
            [exercise["position"] for exercise in response["exercises"]],
            [1, 2],
        )

        deadlift_workout_exercise_id = self.get_workout_exercise_id(response, "Deadlift")
        squat_workout_exercise_id = self.get_workout_exercise_id(response, "Squats")
        response = add_workout_exercise_set_endpoint(
            squat_workout_exercise_id,
            AddSetRequest(weight=40, reps=10),
        )
        self.assertEqual(response["exercises"][1]["sets"][0]["set_number"], 1)

        response = duplicate_workout_exercise_set_endpoint(deadlift_workout_exercise_id)
        deadlift_sets = response["exercises"][0]["sets"]
        duplicated_set_id = int(deadlift_sets[1]["id"])
        self.assertEqual([set_entry["set_number"] for set_entry in deadlift_sets], [1, 2])

        response = update_set_endpoint(duplicated_set_id, UpdateSetRequest(reps=6))
        self.assertEqual(response["exercises"][0]["sets"][1]["reps"], 6)

        original_set_id = int(response["exercises"][0]["sets"][0]["id"])
        response = delete_set_endpoint(original_set_id)
        self.assertEqual(response["exercises"][0]["sets"][0]["set_number"], 1)
        self.assertEqual(response["exercises"][0]["sets"][0]["reps"], 6)

        response = delete_workout_exercise_endpoint(workout_id, squat_workout_exercise_id)
        self.assertEqual(
            [exercise["exercise_name"] for exercise in response["exercises"]],
            ["Deadlift"],
        )
        self.assertEqual(response["exercises"][0]["position"], 1)

    def test_add_workout_exercise_endpoint_appends_exercise(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[],
        )

        response = add_workout_exercise_endpoint(
            workout_id,
            AddExerciseRequest(exercise_id=self.exercise_id("Deadlift")),
        )

        self.assertEqual(len(response["exercises"]), 1)
        self.assertEqual(response["exercises"][0]["exercise_name"], "Deadlift")
        self.assertEqual(response["exercises"][0]["position"], 1)
        self.assertEqual(response["exercises"][0]["sets"], [])

    def test_inactive_exercise_cannot_be_added_to_completed_workout(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[],
        )
        deadlift_id = self.exercise_id("Deadlift")
        with get_db() as conn:
            conn.execute(
                "UPDATE exercises SET is_active = 0 WHERE id = ?",
                (deadlift_id,),
            )

        with self.assertRaises(HTTPException) as exc:
            add_workout_exercise_endpoint(
                workout_id,
                AddExerciseRequest(exercise_id=deadlift_id),
            )

        self.assertEqual(exc.exception.status_code, 409)

    def test_inactive_exercise_in_completed_workout_remains_visible(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )
        deadlift_id = self.exercise_id("Deadlift")
        with get_db() as conn:
            conn.execute(
                "UPDATE exercises SET is_active = 0 WHERE id = ?",
                (deadlift_id,),
            )

        response = get_workout_detail(workout_id)

        self.assertEqual(response["exercises"][0]["exercise_name"], "Deadlift")
        self.assertIn(100.0, response["exercises"][0]["configured_weights"])

    def test_add_workout_exercise_endpoint_returns_404_for_missing_workout(
        self,
    ) -> None:
        with self.assertRaises(HTTPException) as exc:
            add_workout_exercise_endpoint(
                9999,
                AddExerciseRequest(exercise_id=self.exercise_id("Deadlift")),
            )

        self.assertEqual(exc.exception.status_code, 404)

    def test_add_workout_exercise_endpoint_returns_404_for_missing_exercise(
        self,
    ) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[],
        )

        with self.assertRaises(HTTPException) as exc:
            add_workout_exercise_endpoint(
                workout_id,
                AddExerciseRequest(exercise_id=9999),
            )

        self.assertEqual(exc.exception.status_code, 404)

    def test_delete_workout_exercise_endpoint_removes_exercise_and_sets(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
                {
                    "name": "Squats",
                    "sets": [{"weight": 40, "reps": 10}],
                },
            ],
        )
        detail = get_workout_detail(workout_id)
        workout_exercise_id = self.get_workout_exercise_id(detail, "Deadlift")

        response = delete_workout_exercise_endpoint(workout_id, workout_exercise_id)

        self.assertEqual(len(response["exercises"]), 1)
        self.assertEqual(response["exercises"][0]["exercise_name"], "Squats")
        self.assertEqual(response["exercises"][0]["position"], 1)
        self.assertEqual(response["total_volume"], 400.0)

        with get_db() as conn:
            set_count = conn.execute("SELECT COUNT(*) FROM set_entries").fetchone()[0]

        self.assertEqual(set_count, 1)

    def test_delete_workout_exercise_renumbers_remaining_positions(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {"name": "Deadlift", "sets": [{"weight": 100, "reps": 5}]},
                {"name": "Squats", "sets": [{"weight": 40, "reps": 10}]},
                {"name": "Bench Press", "sets": [{"weight": 60, "reps": 8}]},
            ],
        )
        detail = get_workout_detail(workout_id)
        squat_workout_exercise_id = self.get_workout_exercise_id(detail, "Squats")

        response = delete_workout_exercise_endpoint(
            workout_id,
            squat_workout_exercise_id,
        )

        self.assertEqual(
            [exercise["exercise_name"] for exercise in response["exercises"]],
            ["Deadlift", "Bench Press"],
        )
        self.assertEqual(
            [exercise["position"] for exercise in response["exercises"]],
            [1, 2],
        )

    def test_delete_first_and_last_workout_exercise_renumbers_positions(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {"name": "Deadlift", "sets": [{"weight": 100, "reps": 5}]},
                {"name": "Squats", "sets": [{"weight": 40, "reps": 10}]},
                {"name": "Bench Press", "sets": [{"weight": 60, "reps": 8}]},
            ],
        )

        detail = get_workout_detail(workout_id)
        first_id = self.get_workout_exercise_id(detail, "Deadlift")
        response = delete_workout_exercise_endpoint(workout_id, first_id)
        self.assertEqual(
            [exercise["position"] for exercise in response["exercises"]],
            [1, 2],
        )
        self.assertEqual(
            [exercise["exercise_name"] for exercise in response["exercises"]],
            ["Squats", "Bench Press"],
        )

        last_id = self.get_workout_exercise_id(response, "Bench Press")
        response = delete_workout_exercise_endpoint(workout_id, last_id)
        self.assertEqual(
            [exercise["position"] for exercise in response["exercises"]],
            [1],
        )
        self.assertEqual(response["exercises"][0]["exercise_name"], "Squats")

    def test_add_workout_exercise_after_delete_uses_next_sequential_position(
        self,
    ) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {"name": "Deadlift", "sets": [{"weight": 100, "reps": 5}]},
                {"name": "Squats", "sets": [{"weight": 40, "reps": 10}]},
                {"name": "Bench Press", "sets": [{"weight": 60, "reps": 8}]},
            ],
        )
        detail = get_workout_detail(workout_id)
        squat_workout_exercise_id = self.get_workout_exercise_id(detail, "Squats")
        delete_workout_exercise_endpoint(workout_id, squat_workout_exercise_id)

        response = add_workout_exercise_endpoint(
            workout_id,
            AddExerciseRequest(exercise_id=self.exercise_id("Shoulder Press")),
        )
        positions = [exercise["position"] for exercise in response["exercises"]]

        self.assertEqual(positions, [1, 2, 3])
        self.assertEqual(len(positions), len(set(positions)))

    def test_add_set_after_delete_uses_next_sequential_set_number(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [
                        {"weight": 100, "reps": 5},
                        {"weight": 102.5, "reps": 5},
                        {"weight": 105, "reps": 5},
                    ],
                },
            ],
        )
        detail = get_workout_detail(workout_id)
        workout_exercise_id = self.get_workout_exercise_id(detail, "Deadlift")
        set_id = int(detail["exercises"][0]["sets"][1]["id"])
        delete_set_endpoint(set_id)

        response = add_workout_exercise_set_endpoint(
            workout_exercise_id,
            AddSetRequest(weight=107.5, reps=5),
        )
        set_numbers = [
            set_entry["set_number"]
            for set_entry in response["exercises"][0]["sets"]
        ]

        self.assertEqual(set_numbers, [1, 2, 3])
        self.assertEqual(len(set_numbers), len(set(set_numbers)))

    def test_add_workout_exercise_numbering_conflict_returns_409(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[],
        )
        original = api_workouts_module.add_workout_exercise
        api_workouts_module.add_workout_exercise = lambda *_args, **_kwargs: (
            (_ for _ in ()).throw(NumberingConflictError("collision"))
        )
        try:
            with self.assertRaises(HTTPException) as exc:
                add_workout_exercise_endpoint(
                    workout_id,
                    AddExerciseRequest(exercise_id=self.exercise_id("Deadlift")),
                )
        finally:
            api_workouts_module.add_workout_exercise = original

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "Could not assign a unique position. Please retry.",
        )

    def test_add_set_numbering_conflict_returns_409(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[{"name": "Deadlift", "sets": []}],
        )
        detail = get_workout_detail(workout_id)
        workout_exercise_id = self.get_workout_exercise_id(detail, "Deadlift")
        original = api_workouts_module.add_set_to_workout_exercise
        api_workouts_module.add_set_to_workout_exercise = lambda *_args, **_kwargs: (
            (_ for _ in ()).throw(NumberingConflictError("collision"))
        )
        try:
            with self.assertRaises(HTTPException) as exc:
                add_workout_exercise_set_endpoint(
                    workout_exercise_id,
                    AddSetRequest(weight=100, reps=5),
                )
        finally:
            api_workouts_module.add_set_to_workout_exercise = original

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "Could not assign a unique set number. Please retry.",
        )

    def test_add_workout_exercise_set_endpoint_appends_set(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [],
                },
            ],
        )
        detail = get_workout_detail(workout_id)
        workout_exercise_id = self.get_workout_exercise_id(detail, "Deadlift")

        response = add_workout_exercise_set_endpoint(
            workout_exercise_id,
            AddSetRequest(weight=100, reps=5),
        )

        sets = response["exercises"][0]["sets"]
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0]["set_number"], 1)
        self.assertEqual(sets[0]["weight"], 100.0)
        self.assertEqual(sets[0]["reps"], 5)
        self.assertEqual(response["total_volume"], 500.0)

    def test_add_workout_exercise_set_endpoint_returns_404_for_missing_exercise(
        self,
    ) -> None:
        with self.assertRaises(HTTPException) as exc:
            add_workout_exercise_set_endpoint(
                9999,
                AddSetRequest(weight=100, reps=5),
            )

        self.assertEqual(exc.exception.status_code, 404)

    def test_duplicate_workout_exercise_set_endpoint_duplicates_latest_set(
        self,
    ) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )
        detail = get_workout_detail(workout_id)
        workout_exercise_id = self.get_workout_exercise_id(detail, "Deadlift")

        response = duplicate_workout_exercise_set_endpoint(workout_exercise_id)

        sets = response["exercises"][0]["sets"]
        self.assertEqual(len(sets), 2)
        self.assertEqual([set_entry["set_number"] for set_entry in sets], [1, 2])
        self.assertEqual(sets[1]["weight"], 100.0)
        self.assertEqual(sets[1]["reps"], 5)

    def test_duplicate_workout_exercise_set_endpoint_uses_previous_workout_source(
        self,
    ) -> None:
        self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 90, "reps": 6}],
                },
            ],
        )
        workout_id = self.insert_workout(
            created_at="2026-06-08T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [],
                },
            ],
        )
        detail = get_workout_detail(workout_id)
        workout_exercise_id = self.get_workout_exercise_id(detail, "Deadlift")

        response = duplicate_workout_exercise_set_endpoint(workout_exercise_id)

        sets = response["exercises"][0]["sets"]
        self.assertEqual(len(sets), 1)
        self.assertEqual(sets[0]["weight"], 90.0)
        self.assertEqual(sets[0]["reps"], 6)

    def test_duplicate_workout_exercise_set_endpoint_returns_404_without_source(
        self,
    ) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [],
                },
            ],
        )
        detail = get_workout_detail(workout_id)
        workout_exercise_id = self.get_workout_exercise_id(detail, "Deadlift")

        with self.assertRaises(HTTPException) as exc:
            duplicate_workout_exercise_set_endpoint(workout_exercise_id)

        self.assertEqual(exc.exception.status_code, 404)

    def test_update_set_endpoint_updates_partial_set_fields(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )
        detail = get_workout_detail(workout_id)
        set_id = int(detail["exercises"][0]["sets"][0]["id"])

        response = update_set_endpoint(set_id, UpdateSetRequest(weight=105))

        set_entry = response["exercises"][0]["sets"][0]
        self.assertEqual(set_entry["weight"], 105.0)
        self.assertEqual(set_entry["reps"], 5)
        self.assertEqual(response["total_volume"], 525.0)

    def test_update_set_endpoint_returns_400_when_no_fields_provided(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )
        detail = get_workout_detail(workout_id)
        set_id = int(detail["exercises"][0]["sets"][0]["id"])

        with self.assertRaises(HTTPException) as exc:
            update_set_endpoint(set_id, UpdateSetRequest())

        self.assertEqual(exc.exception.status_code, 400)

    def test_update_set_endpoint_returns_404_for_missing_set(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            update_set_endpoint(9999, UpdateSetRequest(weight=105))

        self.assertEqual(exc.exception.status_code, 404)

    def test_delete_set_endpoint_removes_set_and_renumbers_remaining_sets(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [
                        {"weight": 100, "reps": 5},
                        {"weight": 90, "reps": 8},
                        {"weight": 80, "reps": 10},
                    ],
                },
            ],
        )
        detail = get_workout_detail(workout_id)
        deleted_set_id = int(detail["exercises"][0]["sets"][1]["id"])

        response = delete_set_endpoint(deleted_set_id)

        sets = response["exercises"][0]["sets"]
        self.assertEqual(len(sets), 2)
        self.assertEqual([set_entry["set_number"] for set_entry in sets], [1, 2])
        self.assertEqual([set_entry["weight"] for set_entry in sets], [100.0, 80.0])
        self.assertEqual(response["total_volume"], 1300.0)

    def test_delete_set_endpoint_returns_404_for_missing_set(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            delete_set_endpoint(9999)

        self.assertEqual(exc.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
