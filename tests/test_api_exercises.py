import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app import config
from app.db import get_db, init_db
import app.main as main
from app.routes.api_exercises import (
    create_exercise_endpoint,
    create_exercise_profile_endpoint,
    delete_exercise_endpoint,
    delete_exercise_profile_endpoint,
    get_exercises,
    get_exercise_profiles,
    get_exercise_stats_endpoint,
    reorder_exercises_endpoint,
    replace_exercise_weights_endpoint,
    update_exercise_endpoint,
)
from app.schemas import (
    ExerciseCreateRequest,
    ExerciseOrderUpdateRequest,
    ExerciseProfileCreateRequest,
    ExerciseUpdateRequest,
    ExerciseWeightsUpdateRequest,
)
from app.services.draft_service import (
    add_exercise_to_active_draft,
    start_active_workout_draft,
)


class ExercisesApiTests(unittest.TestCase):
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

    def test_exercise_routes_are_registered(self) -> None:
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in main.app.routes
            if hasattr(route, "methods")
        }

        self.assertIn(("/api/v1/exercises", ("GET",)), routes)
        self.assertIn(("/api/v1/exercises", ("POST",)), routes)
        self.assertIn((
            "/api/v1/exercises/{exercise_id}/stats",
            ("GET",),
        ), routes)
        self.assertIn(("/api/v1/exercises/{exercise_id}", ("PATCH",)), routes)
        self.assertIn(("/api/v1/exercises/{exercise_id}", ("DELETE",)), routes)
        self.assertIn(("/api/v1/exercises/{exercise_id}/weights", ("PUT",)), routes)
        self.assertIn(("/api/v1/exercises/order", ("PUT",)), routes)
        self.assertIn(("/api/v1/exercise-profiles", ("GET",)), routes)
        self.assertIn(("/api/v1/exercise-profiles", ("POST",)), routes)
        self.assertIn(("/api/v1/exercise-profiles/{profile_key}", ("PATCH",)), routes)
        self.assertIn(("/api/v1/exercise-profiles/{profile_key}", ("DELETE",)), routes)

    def test_get_exercise_profiles_returns_friendly_catalog(self) -> None:
        response = get_exercise_profiles()
        keys = [profile["key"] for profile in response["profiles"]]

        self.assertIn("deadlift", keys)
        self.assertIn("accessory", keys)
        self.assertIn("Deadlift", [profile["label"] for profile in response["profiles"]])

    def test_exercise_stats_returns_history_summary_and_pr_markers(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")
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
                    "sets": [{"weight": 110, "reps": 5}],
                },
            ],
        )

        response = get_exercise_stats_endpoint(deadlift_id, limit="all")

        self.assertEqual(response["limit"], "all")
        self.assertEqual(response["exercise"]["id"], deadlift_id)
        self.assertTrue(response["exercise"]["is_active"])
        self.assertEqual(response["profile"]["key"], "deadlift")
        self.assertEqual(response["source_workout_ids"], [first_id, second_id])
        self.assertEqual(response["summary"]["workout_count"], 2)
        self.assertEqual(response["summary"]["total_volume"], 1050.0)
        self.assertEqual(response["summary"]["total_reps"], 10)
        self.assertEqual(response["summary"]["total_sets"], 2)
        self.assertEqual(response["summary"]["best_weight"], 110.0)
        self.assertAlmostEqual(response["summary"]["best_e1rm"], 128.3333, places=3)
        self.assertEqual(response["latest"]["workout_id"], second_id)
        self.assertEqual(response["history"][0]["workout_id"], first_id)
        self.assertEqual(response["history"][1]["workout_id"], second_id)
        self.assertEqual(response["history"][1]["pr_flags"], [
            "Weight PR",
            "e1RM PR",
            "Volume PR",
        ])
        self.assertEqual(response["summary"]["pr_count"], 3)
        self.assertEqual(response["per_workout_sets"][1]["sets"][0]["weight"], 110.0)
        self.assertEqual(
            [point["workout_id"] for point in response["strength_progress"]["points"]],
            [first_id, second_id],
        )

    def test_bodyweight_exercise_stats_use_reps_instead_of_volume_pr(self) -> None:
        crunches_id = self.exercise_id("Crunches")
        first_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
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
        second_id = self.insert_workout(
            created_at="2026-06-08T10:00:00",
            exercises=[
                {
                    "name": "Crunches",
                    "sets": [
                        {"weight": 0, "reps": 60},
                        {"weight": 0, "reps": 60},
                    ],
                },
            ],
        )

        response = get_exercise_stats_endpoint(crunches_id, limit="all")

        self.assertEqual(response["exercise"]["measurement_type"], "bodyweight_reps")
        self.assertEqual(response["exercise"]["reps_unit"], "reps")
        self.assertEqual(response["source_workout_ids"], [first_id, second_id])
        self.assertEqual(response["summary"]["total_volume"], 0.0)
        self.assertEqual(response["summary"]["total_volume_kg"], 0.0)
        self.assertEqual(response["summary"]["bodyweight_reps"], 220)
        self.assertEqual(response["summary"]["total_reps"], 220)
        self.assertEqual(response["summary"]["weighted_reps"], 0)
        self.assertIsNone(response["summary"]["avg_kg_per_rep"])
        self.assertIsNone(response["summary"]["best_e1rm"])

        latest = response["history"][1]
        self.assertEqual(latest["workout_id"], second_id)
        self.assertEqual(latest["total_volume_kg"], 0.0)
        self.assertEqual(latest["bodyweight_reps"], 120)
        self.assertEqual(latest["measurement_type"], "bodyweight_reps")
        self.assertEqual(latest["reps_unit"], "reps")
        self.assertIn("Rep PR", latest["pr_flags"])
        self.assertIn("Total reps PR", latest["pr_flags"])
        self.assertNotIn("Volume PR", latest["pr_flags"])
        self.assertEqual(
            [marker["value"] for marker in response["trend"]["bodyweight_reps"]["markers"]],
            [100, 120],
        )

    def test_exercise_stats_keep_inactive_exercise_history(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")
        workout_id = self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )
        update_exercise_endpoint(deadlift_id, ExerciseUpdateRequest(is_active=False))

        response = get_exercise_stats_endpoint(deadlift_id, limit="all")

        self.assertFalse(response["exercise"]["is_active"])
        self.assertEqual(response["source_workout_ids"], [workout_id])
        self.assertEqual(response["summary"]["workout_count"], 1)

    def test_exercise_stats_empty_history_is_stable(self) -> None:
        created = create_exercise_endpoint(
            ExerciseCreateRequest(name="Future Exercise", is_active=False)
        )
        exercise_id = int(created["exercise"]["id"])

        response = get_exercise_stats_endpoint(exercise_id, limit="all")

        self.assertEqual(response["exercise"]["id"], exercise_id)
        self.assertEqual(response["summary"]["workout_count"], 0)
        self.assertEqual(response["summary"]["total_volume"], 0.0)
        self.assertIsNone(response["summary"]["best_e1rm"])
        self.assertIsNone(response["latest"])
        self.assertEqual(response["history"], [])
        self.assertEqual(response["per_workout_sets"], [])
        self.assertEqual(response["source_workout_ids"], [])

    def test_exercise_stats_returns_404_for_missing_exercise(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            get_exercise_stats_endpoint(9999, limit="all")

        self.assertEqual(exc.exception.status_code, 404)

    def test_exercise_stats_limit_uses_prior_history_without_future_leakage(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")
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
        future_id = self.insert_workout(
            created_at="2026-06-15T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 150, "reps": 5}],
                },
            ],
        )

        limited = get_exercise_stats_endpoint(deadlift_id, limit="2")
        latest_entry = limited["history"][0]
        future_entry = limited["history"][1]

        self.assertEqual([entry["workout_id"] for entry in limited["history"]], [
            latest_id,
            future_id,
        ])
        self.assertAlmostEqual(latest_entry["rolling_best_e1rm"], 140.0, places=3)
        self.assertNotIn("e1RM PR", latest_entry["pr_flags"])
        self.assertIn("e1RM PR", future_entry["pr_flags"])

    def test_get_exercises_returns_seeded_exercises_by_settings_order(self) -> None:
        response = get_exercises()
        names = [exercise["name"] for exercise in response["exercises"]]

        self.assertEqual(names, list(config.DEFAULT_EXERCISES))
        self.assertIn("Deadlift", names)
        self.assertEqual(response["exercises"][0]["profile_key"], "deadlift")
        self.assertTrue(response["exercises"][0]["is_active"])
        self.assertIn(100.0, response["exercises"][0]["weights"])
        self.assertEqual(response["exercises"][0]["default_reps"], 10)
        self.assertEqual(response["exercises"][0]["max_reps"], 50)
        for exercise in response["exercises"]:
            self.assertTrue(
                exercise["weights"],
                f"{exercise['name']} has no default weight options",
            )

    def test_create_exercise_strips_name_and_reports_created(self) -> None:
        response = create_exercise_endpoint(
            ExerciseCreateRequest(name="  Incline   Row  ", weights=[17.75, 15, 15])
        )

        self.assertTrue(response["created"])
        self.assertEqual(response["exercise"]["name"], "Incline Row")
        self.assertEqual(response["exercise"]["weights"], [15.0, 17.75])
        self.assertEqual(response["exercise"]["profile_key"], "accessory")
        self.assertEqual(response["exercise"]["measurement_type"], "weighted_reps")
        self.assertEqual(response["exercise"]["reps_unit"], "reps")
        self.assertEqual(response["exercise"]["default_reps"], 10)

        with self.assertRaises(HTTPException) as exc:
            create_exercise_endpoint(ExerciseCreateRequest(name="Incline Row"))

        self.assertEqual(exc.exception.status_code, 409)

    def test_update_exercise_can_change_set_option_settings(self) -> None:
        exercise_id = self.exercise_id("Crunches")

        response = update_exercise_endpoint(
            exercise_id,
            ExerciseUpdateRequest(
                default_weight=0,
                min_weight=0,
                max_weight=0,
                weight_step=1,
                default_reps=70,
                min_reps=1,
                max_reps=200,
                reps_step=1,
                measurement_type="bodyweight_reps",
                reps_unit="reps",
            ),
        )

        exercise = response["exercise"]
        self.assertEqual(exercise["default_weight"], 0)
        self.assertEqual(exercise["max_weight"], 0)
        self.assertEqual(exercise["default_reps"], 70)
        self.assertEqual(exercise["max_reps"], 200)
        self.assertEqual(exercise["measurement_type"], "bodyweight_reps")
        self.assertEqual(exercise["reps_unit"], "reps")

    def test_create_exercise_infers_measurement_from_name(self) -> None:
        response = create_exercise_endpoint(
            ExerciseCreateRequest(
                name="Farmer Carry",
                weights=[20],
            )
        )

        self.assertEqual(response["exercise"]["measurement_type"], "loaded_carry_time")
        self.assertEqual(response["exercise"]["reps_unit"], "sec")

    def test_update_exercise_expands_reps_range_to_save_high_default(self) -> None:
        exercise_id = self.exercise_id("Crunches")

        response = update_exercise_endpoint(
            exercise_id,
            ExerciseUpdateRequest(default_reps=70),
        )

        exercise = response["exercise"]
        self.assertEqual(exercise["default_reps"], 70)
        self.assertEqual(exercise["max_reps"], 70)

    def test_create_exercise_can_infer_profile_from_name(self) -> None:
        response = create_exercise_endpoint(
            ExerciseCreateRequest(name="Trap Bar Deadlift", weights=[40])
        )

        self.assertEqual(response["exercise"]["profile_key"], "deadlift")

    def test_create_exercise_rejects_unknown_profile(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            create_exercise_endpoint(
                ExerciseCreateRequest(
                    name="Incline Row",
                    profile_key="not_real",
                    weights=[20],
                )
            )

        self.assertEqual(exc.exception.status_code, 400)

    def test_create_exercise_rejects_case_insensitive_duplicate(self) -> None:
        create_exercise_endpoint(
            ExerciseCreateRequest(name="Incline Row", weights=[20])
        )

        with self.assertRaises(HTTPException) as exc:
            create_exercise_endpoint(
                ExerciseCreateRequest(name="incline row", weights=[20])
            )

        self.assertEqual(exc.exception.status_code, 409)

    def test_create_exercise_rejects_blank_name_after_stripping(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            create_exercise_endpoint(ExerciseCreateRequest(name="   "))

        self.assertEqual(exc.exception.status_code, 400)

    def test_active_exercise_requires_at_least_one_weight(self) -> None:
        with self.assertRaises(HTTPException) as create_exc:
            create_exercise_endpoint(ExerciseCreateRequest(name="New Active"))

        self.assertEqual(create_exc.exception.status_code, 409)

        response = create_exercise_endpoint(
            ExerciseCreateRequest(name="Future Exercise", is_active=False)
        )
        exercise_id = int(response["exercise"]["id"])

        with self.assertRaises(HTTPException) as activate_exc:
            update_exercise_endpoint(
                exercise_id,
                ExerciseUpdateRequest(is_active=True),
            )

        self.assertEqual(activate_exc.exception.status_code, 409)

    def test_update_exercise_renames_existing_row(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        response = update_exercise_endpoint(
            deadlift_id,
            ExerciseUpdateRequest(name="  Trap Bar  Deadlift "),
        )

        self.assertEqual(response["exercise"]["id"], deadlift_id)
        self.assertEqual(response["exercise"]["name"], "Trap Bar Deadlift")

    def test_update_exercise_allows_capitalization_only_change(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        response = update_exercise_endpoint(
            deadlift_id,
            ExerciseUpdateRequest(name="DEADLIFT"),
        )

        self.assertEqual(response["exercise"]["id"], deadlift_id)
        self.assertEqual(response["exercise"]["name"], "DEADLIFT")

    def test_update_exercise_can_change_profile(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        response = update_exercise_endpoint(
            deadlift_id,
            ExerciseUpdateRequest(profile_key="accessory"),
        )

        self.assertEqual(response["exercise"]["profile_key"], "accessory")

    def test_update_exercise_can_toggle_activity(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        response = update_exercise_endpoint(
            deadlift_id,
            ExerciseUpdateRequest(is_active=False),
        )

        self.assertFalse(response["exercise"]["is_active"])
        active_names = [exercise["name"] for exercise in get_exercises()["exercises"]]
        all_names = [
            exercise["name"]
            for exercise in get_exercises(include_inactive=True)["exercises"]
        ]
        self.assertNotIn("Deadlift", active_names)
        self.assertIn("Deadlift", all_names)

    def test_delete_unused_exercise_succeeds_and_removes_weight_presets(self) -> None:
        created = create_exercise_endpoint(
            ExerciseCreateRequest(
                name="Temporary Exercise",
                is_active=False,
                weights=[5, 10],
            )
        )
        exercise_id = int(created["exercise"]["id"])

        response = delete_exercise_endpoint(exercise_id)

        self.assertTrue(response["deleted"])
        self.assertEqual(response["exercise_id"], exercise_id)
        self.assertEqual(response["usage"], {
            "workout_count": 0,
            "set_count": 0,
            "draft_count": 0,
        })
        with get_db() as conn:
            exercise_row = conn.execute(
                "SELECT 1 FROM exercises WHERE id = ?",
                (exercise_id,),
            ).fetchone()
            weight_count = conn.execute(
                "SELECT COUNT(*) FROM exercise_weight_options WHERE exercise_id = ?",
                (exercise_id,),
            ).fetchone()[0]

        self.assertIsNone(exercise_row)
        self.assertEqual(int(weight_count), 0)

    def test_delete_missing_exercise_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            delete_exercise_endpoint(999999)

        self.assertEqual(exc.exception.status_code, 404)

    def test_delete_exercise_with_workout_history_returns_409_and_preserves_history(self) -> None:
        exercise_id = self.exercise_id("Deadlift")
        self.insert_workout(
            created_at="2026-06-01T10:00:00",
            exercises=[
                {
                    "name": "Deadlift",
                    "sets": [{"weight": 100, "reps": 5}],
                },
            ],
        )

        with self.assertRaises(HTTPException) as exc:
            delete_exercise_endpoint(exercise_id)

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("Deactivate it instead", exc.exception.detail)
        with get_db() as conn:
            history_count = conn.execute(
                "SELECT COUNT(*) FROM workout_exercises WHERE exercise_id = ?",
                (exercise_id,),
            ).fetchone()[0]

        self.assertEqual(int(history_count), 1)

    def test_delete_exercise_with_active_draft_returns_409(self) -> None:
        exercise_id = self.exercise_id("Deadlift")
        start_active_workout_draft()
        add_exercise_to_active_draft(exercise_id, "Deadlift")

        with self.assertRaises(HTTPException) as exc:
            delete_exercise_endpoint(exercise_id)

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("active draft", exc.exception.detail)

    def test_replace_exercise_weights_normalizes_values(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        response = replace_exercise_weights_endpoint(
            deadlift_id,
            ExerciseWeightsUpdateRequest(weights=[52.5, 50, 50, 0]),
        )

        self.assertEqual(response["weights"], [0.0, 50.0, 52.5])

    def test_replace_active_exercise_weights_rejects_empty_list(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            replace_exercise_weights_endpoint(
                self.exercise_id("Deadlift"),
                ExerciseWeightsUpdateRequest(weights=[]),
            )

        self.assertEqual(exc.exception.status_code, 409)

    def test_replace_exercise_weights_rejects_negative_values(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            replace_exercise_weights_endpoint(
                self.exercise_id("Deadlift"),
                ExerciseWeightsUpdateRequest(weights=[-1]),
            )

        self.assertEqual(exc.exception.status_code, 400)

    def test_reorder_exercises_updates_sort_order(self) -> None:
        exercises = get_exercises(include_inactive=True)["exercises"]
        exercise_ids = [exercise["id"] for exercise in exercises]

        response = reorder_exercises_endpoint(
            ExerciseOrderUpdateRequest(exercise_ids=list(reversed(exercise_ids)))
        )

        self.assertEqual(
            [exercise["id"] for exercise in response["exercises"]],
            list(reversed(exercise_ids)),
        )

    def test_reorder_exercises_rejects_missing_ids(self) -> None:
        exercises = get_exercises(include_inactive=True)["exercises"]

        with self.assertRaises(HTTPException) as exc:
            reorder_exercises_endpoint(
                ExerciseOrderUpdateRequest(
                    exercise_ids=[exercise["id"] for exercise in exercises[:-1]]
                )
            )

        self.assertEqual(exc.exception.status_code, 400)

    def test_update_exercise_returns_404_for_missing_row(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            update_exercise_endpoint(
                9999,
                ExerciseUpdateRequest(name="Missing"),
            )

        self.assertEqual(exc.exception.status_code, 404)

    def test_update_exercise_returns_409_for_duplicate_name(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        with self.assertRaises(HTTPException) as exc:
            update_exercise_endpoint(
                deadlift_id,
                ExerciseUpdateRequest(name="Squats"),
            )

        self.assertEqual(exc.exception.status_code, 409)

    def test_exercise_request_models_validate_lengths(self) -> None:
        with self.assertRaises(Exception):
            ExerciseCreateRequest(name="")

        with self.assertRaises(Exception):
            ExerciseUpdateRequest(name="")

    def test_delete_custom_unused_profile_succeeds(self) -> None:
        created = create_exercise_profile_endpoint(
            ExerciseProfileCreateRequest(
                label="Loaded carry test",
                category="core carry",
                exercise_factor=1,
                compound_factor=0.5,
                back_factor=0.2,
            )
        )
        profile_key = created["profile"]["key"]

        response = delete_exercise_profile_endpoint(profile_key)

        self.assertTrue(response["deleted"])
        self.assertEqual(response["profile_key"], profile_key)
        with get_db() as conn:
            row = conn.execute(
                "SELECT 1 FROM analysis_profiles WHERE key = ?",
                (profile_key,),
            ).fetchone()

        self.assertIsNone(row)

    def test_delete_profile_returns_404_for_missing_profile(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            delete_exercise_profile_endpoint("missing_profile")

        self.assertEqual(exc.exception.status_code, 404)

    def test_delete_builtin_profile_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            delete_exercise_profile_endpoint("deadlift")

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("Built-in", exc.exception.detail)

    def test_delete_accessory_profile_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            delete_exercise_profile_endpoint("accessory")

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("Accessory", exc.exception.detail)

    def test_delete_profile_used_by_exercise_is_rejected(self) -> None:
        created = create_exercise_profile_endpoint(
            ExerciseProfileCreateRequest(
                label="Used custom type",
                category="custom",
                exercise_factor=1,
                compound_factor=0.5,
                back_factor=0.2,
            )
        )
        profile_key = created["profile"]["key"]
        create_exercise_endpoint(
            ExerciseCreateRequest(
                name="Profile Locked Exercise",
                is_active=False,
                profile_key=profile_key,
            )
        )

        with self.assertRaises(HTTPException) as exc:
            delete_exercise_profile_endpoint(profile_key)

        self.assertEqual(exc.exception.status_code, 409)
        self.assertIn("used by exercises", exc.exception.detail)


if __name__ == "__main__":
    unittest.main()
