import json
import unittest
from pathlib import Path
from typing import Any

import app.main as main
from app.schemas import ExerciseUpdateRequest, WorkoutUpdateRequest


ROOT = Path(__file__).resolve().parents[1]


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        main.app.openapi_schema = None
        self.openapi = main.app.openapi()

    def assert_response_schema_ref(
        self,
        path: str,
        method: str,
        schema_name: str,
    ) -> None:
        operation: dict[str, Any] = self.openapi["paths"][path][method]
        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(schema.get("$ref"), f"#/components/schemas/{schema_name}")

    def test_openapi_declares_typed_api_response_models(self) -> None:
        self.assert_response_schema_ref("/api/v1/workouts", "get", "WorkoutsResponse")
        self.assert_response_schema_ref(
            "/api/v1/workouts/{workout_id}",
            "get",
            "WorkoutDetailResponse",
        )
        self.assert_response_schema_ref(
            "/api/v1/workouts/{workout_id}",
            "patch",
            "WorkoutDetailResponse",
        )
        self.assert_response_schema_ref("/api/v1/exercises", "get", "ExercisesResponse")
        self.assert_response_schema_ref(
            "/api/v1/exercises/{exercise_id}/stats",
            "get",
            "ExerciseStatsResponseModel",
        )
        self.assert_response_schema_ref(
            "/api/v1/current-workout",
            "get",
            "CurrentWorkoutResponse",
        )
        self.assert_response_schema_ref(
            "/api/v1/current-workout/finish",
            "post",
            "FinishCurrentWorkoutResponse",
        )
        self.assert_response_schema_ref("/api/v1/stats", "get", "StatsResponseModel")
        self.assert_response_schema_ref("/api/v1/backup", "get", "BackupPayloadResponse")

    def test_checked_in_openapi_schema_contains_generated_contract_refs(self) -> None:
        checked_in = json.loads((ROOT / "docs" / "openapi.json").read_text())

        self.assertEqual(
            checked_in["paths"]["/api/v1/workouts"]["get"]["responses"]["200"]
            ["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/WorkoutsResponse",
        )
        self.assertEqual(
            checked_in["paths"]["/api/v1/current-workout"]["get"]["responses"]["200"]
            ["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/CurrentWorkoutResponse",
        )
        self.assertEqual(
            checked_in["paths"]["/api/v1/backup"]["get"]["responses"]["200"]
            ["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/BackupPayloadResponse",
        )

    def test_generated_types_include_response_contracts(self) -> None:
        generated = (ROOT / "frontend" / "src" / "api" / "generated.ts").read_text()

        for name in (
            "WorkoutsResponse",
            "WorkoutDetailResponse",
            "CurrentWorkoutResponse",
            "ExerciseStatsResponseModel",
            "StatsResponseModel",
            "BackupPayloadResponse",
        ):
            self.assertIn(f"export type {name} =", generated)

        self.assertIn("started_at?: string | null;", generated)
        self.assertIn("load_metrics?: LoadMetricsResponse | null;", generated)

    def test_fields_set_distinguishes_omitted_fields_from_explicit_null(self) -> None:
        omitted_workout = WorkoutUpdateRequest()
        explicit_null_workout = WorkoutUpdateRequest(session_rpe=None)
        explicit_null_exercise = ExerciseUpdateRequest(name=None)

        self.assertNotIn("session_rpe", omitted_workout.model_fields_set)
        self.assertIn("session_rpe", explicit_null_workout.model_fields_set)
        self.assertIn("name", explicit_null_exercise.model_fields_set)


if __name__ == "__main__":
    unittest.main()
