import tempfile
import unittest
from datetime import date
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from app import config
from app.db import get_db, init_db
from app.repositories import garmin as garmin_repository
from app.repositories.exercises import create_exercise
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

    def flattened_response_keys(self, value: Any) -> set[str]:
        keys: set[str] = set()
        if isinstance(value, dict):
            for key, nested_value in value.items():
                keys.add(str(key))
                keys.update(self.flattened_response_keys(nested_value))
        elif isinstance(value, list):
            for item in value:
                keys.update(self.flattened_response_keys(item))
        return keys

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
        self.assertEqual(response["stats"]["summary"]["total_volume_kg"], 1050.0)
        self.assertEqual(response["stats"]["summary"]["bodyweight_reps"], 0)
        self.assertEqual(response["stats"]["summary"]["weighted_reps"], 10)
        self.assertEqual(response["stats"]["summary"]["avg_kg_per_rep"], 105.0)
        self.assertEqual(response["stats"]["summary"]["total_reps"], 10)
        self.assertEqual(response["stats"]["summary"]["total_sets"], 2)
        self.assertEqual(response["stats"]["summary"]["avg_rpe"], 6.0)
        self.assertEqual(response["stats"]["summary"]["avg_back_pain"], 3.0)
        deadlift_stats = response["stats"]["exercise_stats"][0]
        self.assertEqual(deadlift_stats["exercise_id"], self.exercise_id("Deadlift"))
        self.assertEqual(deadlift_stats["name"], "Deadlift")
        self.assertEqual(deadlift_stats["total_volume_kg"], 1050.0)
        self.assertEqual(deadlift_stats["bodyweight_reps"], 0)
        self.assertIn("volume", response["charts"])
        self.assertIn("volume_kg", response["charts"])
        self.assertIn("bodyweight_reps", response["charts"])
        self.assertIn("load", response["charts"])
        self.assertIn("sparkbars", response["charts"])
        self.assertIn("training_load", response)
        self.assertEqual(
            response["training_load"],
            response["stats"]["training_load"],
        )
        self.assertIn("series", response["training_load"])

    def test_bodyweight_only_workout_contributes_to_stats_load_and_scatter(self) -> None:
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=6,
            lower_back_pain=1,
            exercises=[
                {
                    "name": "Crunches",
                    "sets": [
                        {"weight": 0, "reps": 50},
                        {"weight": 0, "reps": 50},
                    ],
                },
            ],
        )

        response = get_stats(limit="all")
        workout = response["stats"]["workouts"][0]
        summary = response["stats"]["summary"]
        crunches = response["stats"]["exercise_stats"][0]
        scatter = response["charts"]["scatter"]

        self.assertEqual(workout["id"], workout_id)
        self.assertEqual(workout["total_volume"], 0.0)
        self.assertEqual(workout["total_volume_kg"], 0.0)
        self.assertEqual(workout["bodyweight_reps"], 100)
        self.assertEqual(workout["weighted_reps"], 0)
        self.assertIsNone(workout["avg_kg_per_rep"])
        self.assertGreater(workout["load_score"], 0)

        self.assertEqual(summary["total_volume"], 0.0)
        self.assertEqual(summary["total_volume_kg"], 0.0)
        self.assertEqual(summary["bodyweight_reps"], 100)
        self.assertEqual(summary["weighted_reps"], 0)
        self.assertIsNone(summary["avg_kg_per_rep"])
        self.assertGreater(summary["total_load_score"], 0)

        self.assertEqual(crunches["name"], "Crunches")
        self.assertEqual(crunches["total_volume_kg"], 0.0)
        self.assertEqual(crunches["bodyweight_reps"], 100)
        self.assertEqual(crunches["weighted_reps"], 0)

        self.assertEqual(scatter["max_volume"], 0.0)
        self.assertGreater(scatter["max_load"], 0)
        self.assertEqual(len(scatter["points"]), 1)
        self.assertEqual(scatter["points"][0]["workout_id"], workout_id)
        self.assertGreater(scatter["points"][0]["load"], 0)
        self.assertEqual(scatter["points"][0]["total_volume_kg"], 0.0)

    def test_stats_response_has_kg_volume_and_load_first_fields(self) -> None:
        self.seed_stats_workouts()

        response = get_stats(limit="all")
        workout = response["stats"]["workouts"][0]
        summary = response["stats"]["summary"]
        scatter = response["charts"]["scatter"]

        self.assertIn("total_volume_kg", workout)
        self.assertIn("weighted_reps", workout)
        self.assertIn("load_score", workout)
        self.assertIn("back_stress_score", workout)
        self.assertIn("total_volume_kg", summary)
        self.assertIn("total_load_score", summary)
        self.assertIn("total_back_stress_score", summary)
        self.assertIn("load", scatter["points"][0])
        self.assertIn("total_volume_kg", scatter["points"][0])

    def test_stats_excludes_loaded_carries_from_kg_volume(self) -> None:
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
                    "name": "Suitcase carry",
                    "sets": [{"weight": 24, "reps": 30}],
                },
            ],
        )

        response = get_stats(limit="all")
        workout = response["stats"]["workouts"][0]
        summary = response["stats"]["summary"]
        carry = response["stats"]["exercise_stats"][0]
        scatter = response["charts"]["scatter"]

        self.assertEqual(workout["id"], workout_id)
        self.assertEqual(workout["total_volume"], 720.0)
        self.assertEqual(workout["total_volume_kg"], 0.0)
        self.assertEqual(workout["duration_seconds"], 30)
        self.assertEqual(summary["total_volume"], 720.0)
        self.assertEqual(summary["total_volume_kg"], 0.0)
        self.assertEqual(carry["total_volume_kg"], 0.0)
        self.assertEqual(carry["duration_seconds"], 30)
        self.assertEqual(scatter["points"][0]["total_volume_kg"], 0.0)

    def test_stats_response_does_not_expose_set_timestamp_analytics(self) -> None:
        self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=5,
            lower_back_pain=2,
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [
                        {"weight": 100, "reps": 5},
                        {"weight": 100, "reps": 5},
                    ],
                },
            ],
        )

        response = get_stats(limit="all")
        serialized = json.dumps(response).lower()
        keys = {key.lower() for key in self.flattened_response_keys(response)}
        forbidden_key_fragments = (
            "rest_seconds",
            "avg_rest",
            "density",
            "set_gap",
            "tempo",
        )

        for fragment in forbidden_key_fragments:
            with self.subTest(fragment=fragment):
                self.assertFalse(any(fragment in key for key in keys))
                self.assertNotIn(fragment, serialized)

    def test_stats_data_quality_notes_cover_bodyweight_and_zero_kg_weighted_sets(self) -> None:
        self.insert_workout(
            created_at="2026-06-01T10:00:00",
            session_rpe=6,
            lower_back_pain=2,
            exercises=[
                {
                    "name": "Crunches",
                    "sets": [{"weight": 0, "reps": 50}],
                },
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 0, "reps": 5}],
                },
            ],
        )

        response = get_stats(limit="all")
        warnings = response["stats"]["data_quality_warnings"]
        warnings_by_key = {warning["key"]: warning for warning in warnings}

        self.assertIn("bodyweight_excluded_from_kg_volume", warnings_by_key)
        self.assertEqual(
            warnings_by_key["bodyweight_excluded_from_kg_volume"]["count"],
            50,
        )
        self.assertIn("zero_kg_weighted_sets", warnings_by_key)
        self.assertEqual(warnings_by_key["zero_kg_weighted_sets"]["count"], 1)
        serialized_keys = " ".join(warnings_by_key)
        self.assertNotIn("rest", serialized_keys)
        self.assertNotIn("density", serialized_keys)

    def test_stats_data_quality_notes_cover_high_pain_low_load_and_missing_feedback(self) -> None:
        low_load_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            lower_back_pain=7,
            exercises=[
                {
                    "name": "Crunches",
                    "sets": [{"weight": 0, "reps": 20}],
                },
            ],
        )
        self.insert_workout(
            created_at="2026-06-08T10:00:00",
            session_rpe=7,
            lower_back_pain=2,
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 120, "reps": 5}],
                },
            ],
        )

        response = get_stats(limit="all")
        warnings_by_key = {
            warning["key"]: warning
            for warning in response["stats"]["data_quality_warnings"]
        }

        self.assertIn("high_pain_low_load", warnings_by_key)
        self.assertEqual(warnings_by_key["high_pain_low_load"]["workout_id"], low_load_id)
        self.assertIn("missing_feedback", warnings_by_key)

    def test_stats_data_quality_notes_include_partial_garmin_today(self) -> None:
        self.seed_stats_workouts()
        garmin_repository.upsert_daily_metric(
            {
                "date": "2026-07-09",
                "resting_heart_rate": 66,
                "hrv_ms": None,
                "stress_avg": 25,
                "body_battery_start": 52,
                "body_battery_end": 52,
                "steps": 97,
                "synced_at": "2026-07-09T09:25:50",
                "raw_diagnostics": {"test": {"ok": True}},
            }
        )

        with patch("app.services.stats_service.app_today", return_value=date(2026, 7, 9)):
            response = get_stats(limit="all")

        warning_keys = {
            warning["key"]
            for warning in response["stats"]["data_quality_warnings"]
        }
        self.assertIn("partial_garmin_today", warning_keys)

    def test_get_stats_orders_by_created_at_ascending_then_id_ascending(self) -> None:
        newer_id = self.insert_workout(
            created_at="2026-06-08T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 110, "reps": 5}],
                },
            ],
        )
        older_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )

        response = get_stats(limit="all")

        self.assertEqual(
            [workout["id"] for workout in response["stats"]["workouts"]],
            [older_id, newer_id],
        )

    def test_old_stats_are_stable_after_new_pr(self) -> None:
        old_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )
        first_response = get_stats(limit="all")
        old_load_before = first_response["stats"]["workouts"][0]["load_score"]

        self.insert_workout(
            created_at="2026-06-15T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 300, "reps": 5}],
                },
            ],
        )

        second_response = get_stats(limit="all")
        old_workout = next(
            workout
            for workout in second_response["stats"]["workouts"]
            if workout["id"] == old_id
        )

        self.assertEqual(old_workout["load_score"], old_load_before)
        self.assertIsNone(old_workout["intensity_score"])

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

    def test_stats_includes_exercise_strength_progress(self) -> None:
        first_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )
        second_id = self.insert_workout(
            created_at="2026-06-08T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 95, "reps": 5}],
                },
            ],
        )
        third_id = self.insert_workout(
            created_at="2026-06-15T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 110, "reps": 5}],
                },
            ],
        )

        response = get_stats(limit="all")

        progress = next(
            item
            for item in response["stats"]["exercise_progress"]
            if item["name"] == "Deadlift"
        )

        self.assertEqual(
            [point["workout_id"] for point in progress["points"]],
            [first_id, second_id, third_id],
        )

        first, second, third = progress["points"]

        self.assertAlmostEqual(first["e1rm"], 116.6667, places=3)
        self.assertAlmostEqual(first["rolling_best"], 116.6667, places=3)
        self.assertFalse(first["is_pr"])

        self.assertAlmostEqual(second["e1rm"], 110.8333, places=3)
        self.assertAlmostEqual(second["rolling_best"], 116.6667, places=3)
        self.assertFalse(second["is_pr"])

        self.assertAlmostEqual(third["e1rm"], 128.3333, places=3)
        self.assertAlmostEqual(third["rolling_best"], 128.3333, places=3)
        self.assertTrue(third["is_pr"])

    def test_strength_progress_uses_history_before_selected_range(self) -> None:
        self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 120, "reps": 5}],
                },
            ],
        )

        latest_id = self.insert_workout(
            created_at="2026-06-08T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 110, "reps": 5}],
                },
            ],
        )

        response = get_stats(limit="1")

        progress = next(
            item
            for item in response["stats"]["exercise_progress"]
            if item["name"] == "Deadlift"
        )

        self.assertEqual(len(progress["points"]), 1)

        point = progress["points"][0]

        self.assertEqual(point["workout_id"], latest_id)
        self.assertAlmostEqual(point["e1rm"], 128.3333, places=3)
        self.assertAlmostEqual(point["rolling_best"], 140.0, places=3)
        self.assertFalse(point["is_pr"])

    def test_stats_includes_fixed_rep_weight_progress(self) -> None:
        first_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [
                        {"weight": 100, "reps": 5},
                        {"weight": 105, "reps": 5},
                        {"weight": 90, "reps": 8},
                    ],
                },
            ],
        )

        second_id = self.insert_workout(
            created_at="2026-06-08T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [
                        {"weight": 102.5, "reps": 5},
                        {"weight": 95, "reps": 8},
                    ],
                },
            ],
        )

        third_id = self.insert_workout(
            created_at="2026-06-15T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [
                        {"weight": 110, "reps": 5},
                    ],
                },
            ],
        )

        response = get_stats(limit="all")

        progress = next(
            item
            for item in response["stats"]["exercise_rep_progress"]
            if item["name"] == "Deadlift"
        )

        five_rep_target = next(
            target
            for target in progress["rep_targets"]
            if target["reps"] == 5
        )

        self.assertEqual(
            [
                point["workout_id"]
                for point in five_rep_target["points"]
            ],
            [first_id, second_id, third_id],
        )

        first, second, third = five_rep_target["points"]

        self.assertEqual(first["weight"], 105.0)
        self.assertEqual(first["rolling_best"], 105.0)
        self.assertFalse(first["is_pr"])

        self.assertEqual(second["weight"], 102.5)
        self.assertEqual(second["rolling_best"], 105.0)
        self.assertFalse(second["is_pr"])

        self.assertEqual(third["weight"], 110.0)
        self.assertEqual(third["rolling_best"], 110.0)
        self.assertTrue(third["is_pr"])


    def test_fixed_rep_progress_uses_history_before_selected_range(
        self,
    ) -> None:
        self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 120, "reps": 5}],
                },
            ],
        )

        latest_id = self.insert_workout(
            created_at="2026-06-08T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 110, "reps": 5}],
                },
            ],
        )

        response = get_stats(limit="1")

        progress = next(
            item
            for item in response["stats"]["exercise_rep_progress"]
            if item["name"] == "Deadlift"
        )

        target = next(
            item
            for item in progress["rep_targets"]
            if item["reps"] == 5
        )

        self.assertEqual(len(target["points"]), 1)

        point = target["points"][0]

        self.assertEqual(point["workout_id"], latest_id)
        self.assertEqual(point["weight"], 110.0)
        self.assertEqual(point["rolling_best"], 120.0)
        self.assertFalse(point["is_pr"])

    def test_stats_includes_zero_filled_weekly_workload(
        self,
    ) -> None:
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

        self.insert_workout(
            created_at="2026-06-15T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [
                        {"weight": 110, "reps": 5},
                    ],
                },
            ],
        )

        response = get_stats(limit="all")

        workload = next(
            item
            for item in response["stats"][
                "exercise_weekly_workload"
            ]
            if item["name"] == "Deadlift"
        )

        self.assertEqual(
            [
                week["week_start"]
                for week in workload["weeks"]
            ],
            [
                "2026-06-01",
                "2026-06-08",
                "2026-06-15",
            ],
        )

        first, empty, third = workload["weeks"]

        self.assertEqual(first["sets"], 2)
        self.assertEqual(first["reps"], 13)
        self.assertEqual(first["volume"], 1220.0)
        self.assertEqual(first["workouts"], 1)

        self.assertEqual(empty["sets"], 0)
        self.assertEqual(empty["reps"], 0)
        self.assertEqual(empty["volume"], 0.0)
        self.assertEqual(empty["workouts"], 0)

        self.assertEqual(third["sets"], 1)
        self.assertEqual(third["reps"], 5)
        self.assertEqual(third["volume"], 550.0)
        self.assertEqual(third["workouts"], 1)

if __name__ == "__main__":
    unittest.main()
