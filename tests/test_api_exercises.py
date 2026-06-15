import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app import config
from app.db import get_db, init_db
import app.main as main
from app.routes.api_exercises import (
    create_exercise_endpoint,
    get_exercises,
    update_exercise_endpoint,
)
from app.schemas import ExerciseCreateRequest, ExerciseUpdateRequest


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

    def test_exercise_routes_are_registered(self) -> None:
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in main.app.routes
            if hasattr(route, "methods")
        }

        self.assertIn(("/api/v1/exercises", ("GET",)), routes)
        self.assertIn(("/api/v1/exercises", ("POST",)), routes)
        self.assertIn(("/api/v1/exercises/{exercise_id}", ("PATCH",)), routes)

    def test_get_exercises_returns_seeded_exercises_by_name(self) -> None:
        response = get_exercises()
        names = [exercise["name"] for exercise in response["exercises"]]

        self.assertEqual(names, sorted(names))
        self.assertIn("Deadlift", names)

    def test_create_exercise_strips_name_and_reports_created(self) -> None:
        response = create_exercise_endpoint(
            ExerciseCreateRequest(name="  Incline   Row  ")
        )

        self.assertTrue(response["created"])
        self.assertEqual(response["exercise"]["name"], "Incline Row")

        duplicate_response = create_exercise_endpoint(
            ExerciseCreateRequest(name="Incline Row")
        )

        self.assertFalse(duplicate_response["created"])
        self.assertEqual(
            duplicate_response["exercise"]["id"],
            response["exercise"]["id"],
        )

    def test_create_exercise_rejects_blank_name_after_stripping(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            create_exercise_endpoint(ExerciseCreateRequest(name="   "))

        self.assertEqual(exc.exception.status_code, 400)

    def test_update_exercise_renames_existing_row(self) -> None:
        deadlift_id = self.exercise_id("Deadlift")

        response = update_exercise_endpoint(
            deadlift_id,
            ExerciseUpdateRequest(name="  Trap Bar  Deadlift "),
        )

        self.assertEqual(response["exercise"]["id"], deadlift_id)
        self.assertEqual(response["exercise"]["name"], "Trap Bar Deadlift")

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
                ExerciseUpdateRequest(name="Goblet Squat"),
            )

        self.assertEqual(exc.exception.status_code, 409)

    def test_exercise_request_models_validate_lengths(self) -> None:
        with self.assertRaises(Exception):
            ExerciseCreateRequest(name="")

        with self.assertRaises(Exception):
            ExerciseUpdateRequest(name="")


if __name__ == "__main__":
    unittest.main()
