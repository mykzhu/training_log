from typing import Any

from pydantic import BaseModel, Field


class AppBaseModel(BaseModel):
    @property
    def model_fields_set(self) -> set[str]:
        return set(getattr(self, "__fields_set__", set()))


class FlexibleResponse(AppBaseModel):
    class Config:
        extra = "allow"


class WorkoutMetadataUpdate(AppBaseModel):
    session_rpe: int | None = Field(default=None, ge=1, le=10)
    lower_back_pain: int | None = Field(default=None, ge=0, le=10)


class WorkoutUpdateRequest(AppBaseModel):
    created_at: str | None = Field(default=None, min_length=16, max_length=19)
    session_rpe: int | None = Field(default=None, ge=1, le=10)
    lower_back_pain: int | None = Field(default=None, ge=0, le=10)


class AddExerciseRequest(AppBaseModel):
    exercise_id: int = Field(ge=1)


class ExerciseCreateRequest(AppBaseModel):
    name: str = Field(min_length=1, max_length=120)
    is_active: bool = True
    profile_key: str | None = Field(default=None, min_length=1, max_length=80)
    weights: list[float] = Field(default_factory=list)


class ExerciseUpdateRequest(AppBaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    profile_key: str | None = Field(default=None, min_length=1, max_length=80)


class ExerciseWeightsUpdateRequest(AppBaseModel):
    weights: list[float]


class ExerciseOrderUpdateRequest(AppBaseModel):
    exercise_ids: list[int]


class AddSetRequest(AppBaseModel):
    weight: float = Field(ge=0)
    reps: int = Field(ge=1, le=100)


class UpdateSetRequest(AppBaseModel):
    weight: float | None = Field(default=None, ge=0)
    reps: int | None = Field(default=None, ge=1, le=100)


class SetEntryResponse(AppBaseModel):
    id: int
    workout_exercise_id: int
    set_number: int
    weight: float
    reps: int
    created_at: str


class CurrentWorkoutSetEntryResponse(AppBaseModel):
    id: int
    set_number: int
    weight: float
    reps: int
    created_at: str


class LoadMetricsResponse(FlexibleResponse):
    load_score: float
    load_label: str
    compound_score: float
    intensity_score: float | None
    back_stress_score: float


class WorkoutCoreResponse(AppBaseModel):
    id: int
    workout_date: str
    created_at: str
    finished_at: str | None
    session_rpe: int | None
    lower_back_pain: int | None
    duration_seconds: int | None


class WorkoutExerciseResponse(AppBaseModel):
    workout_exercise_id: int
    exercise_id: int
    exercise_name: str
    profile_key: str
    position: int
    sets: list[SetEntryResponse]
    total_sets: int
    total_reps: int
    total_volume: float
    default_weight: float
    default_reps: int
    configured_weights: list[float]


class CurrentWorkoutExerciseResponse(AppBaseModel):
    draft_exercise_id: int
    exercise_id: int
    exercise_name: str
    profile_key: str
    position: int
    sets: list[CurrentWorkoutSetEntryResponse]
    total_sets: int
    total_reps: int
    total_volume: float
    default_weight: float
    default_reps: int
    configured_weights: list[float]


class WorkoutAnalysisExerciseResponse(FlexibleResponse):
    exercise_id: int
    exercise_name: str
    best_set: dict[str, Any] | None
    best_e1rm: float | None
    best_e1rm_set: dict[str, Any] | None
    pr_flags: list[str]


class WorkoutAnalysisPrResponse(AppBaseModel):
    exercise_name: str
    type: str


class WorkoutAnalysisResponse(AppBaseModel):
    exercises: list[WorkoutAnalysisExerciseResponse]
    prs: list[WorkoutAnalysisPrResponse]


class WorkoutSummaryResponse(WorkoutCoreResponse):
    total_volume: float
    total_reps: int
    total_sets: int
    exercises_count: int
    load_metrics: LoadMetricsResponse


class WorkoutsResponse(AppBaseModel):
    limit: int
    workouts: list[WorkoutSummaryResponse]


class WorkoutDetailResponse(AppBaseModel):
    workout: WorkoutCoreResponse
    exercises: list[WorkoutExerciseResponse]
    total_volume: float
    total_reps: int
    total_sets: int
    load_metrics: LoadMetricsResponse
    analysis: WorkoutAnalysisResponse


class DeleteWorkoutResponse(AppBaseModel):
    deleted: bool
    workout_id: int


class ExerciseResponse(AppBaseModel):
    id: int
    name: str
    is_active: bool
    sort_order: int
    profile_key: str
    weights: list[float]


class ExercisesResponse(AppBaseModel):
    exercises: list[ExerciseResponse]


class ExerciseMutationResponse(AppBaseModel):
    exercise: ExerciseResponse
    created: bool | None = None


class ExerciseWeightsResponse(AppBaseModel):
    exercise_id: int
    weights: list[float]


class ExerciseProfileResponse(AppBaseModel):
    key: str
    label: str
    category: str


class ExerciseProfilesResponse(AppBaseModel):
    profiles: list[ExerciseProfileResponse]


class RecoveryContextResponse(FlexibleResponse):
    as_of: str
    has_history: bool


class NextWorkoutRecommendationResponse(FlexibleResponse):
    status: str
    title: str
    score: float | None
    summary: str
    reasons: list[str]
    last_workout_id: int | None
    exercise_recommendations: list[dict[str, Any]]



class GarminDailyMetricResponse(AppBaseModel):
    date: str
    resting_heart_rate: int | None
    hrv_ms: float | None
    stress_avg: int | None
    body_battery_start: int | None
    body_battery_end: int | None
    steps: int | None
    synced_at: str
    raw_diagnostics: dict[str, Any]


class GarminStatusResponse(AppBaseModel):
    connected: bool
    last_synced_at: str | None
    latest_metric: GarminDailyMetricResponse | None
    pending_mfa: bool


class GarminRecoverySnapshotResponse(AppBaseModel):
    connected: bool
    today: GarminDailyMetricResponse | None
    yesterday: GarminDailyMetricResponse | None
    latest: GarminDailyMetricResponse | None
    last_synced_at: str | None
    sample_count_35d: int
    message: str


class GarminLoginRequest(AppBaseModel):
    username: str = Field(min_length=1, max_length=240)
    password: str = Field(min_length=1, max_length=240)


class GarminMfaRequest(AppBaseModel):
    mfa_token: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=40)


class GarminSyncRequest(AppBaseModel):
    days: int | None = Field(default=None, ge=1, le=90)


class GarminLoginResponse(AppBaseModel):
    connected: bool
    mfa_required: bool
    mfa_token: str | None = None


class GarminDisconnectResponse(GarminStatusResponse):
    pass


class GarminSyncResponse(AppBaseModel):
    synced: bool
    days: int
    saved_dates: list[str]
    skipped_dates: list[str]
    errors: dict[str, str]
    status: GarminStatusResponse


class GarminDailyMetricsResponse(AppBaseModel):
    days: int
    metrics: list[GarminDailyMetricResponse]


class CurrentWorkoutResponse(AppBaseModel):
    active: bool
    started_at: str | None
    elapsed_seconds: int
    session_rpe: int | None
    lower_back_pain: int | None
    total_sets: int
    total_reps: int
    total_volume: float
    exercises: list[CurrentWorkoutExerciseResponse]
    load_metrics: LoadMetricsResponse | None
    recovery_context: RecoveryContextResponse | None
    next_workout_recommendation: NextWorkoutRecommendationResponse | None
    garmin_recovery: GarminRecoverySnapshotResponse | None


class FinishCurrentWorkoutResponse(AppBaseModel):
    workout_id: int
    current_workout: CurrentWorkoutResponse


class StatsResponseModel(FlexibleResponse):
    limit: int | str
    stats: dict[str, Any]
    charts: dict[str, Any]


class ExerciseStatsResponseModel(FlexibleResponse):
    limit: int | str
    exercise: dict[str, Any]
    profile: ExerciseProfileResponse
    summary: dict[str, Any]
    latest: dict[str, Any] | None
    history: list[dict[str, Any]]
    per_workout_sets: list[dict[str, Any]]
    trend: dict[str, Any]
    strength_progress: dict[str, Any]
    source_workout_ids: list[int]


class BackupPayloadResponse(FlexibleResponse):
    schema_version: int


class BackupMutationResponse(AppBaseModel):
    counts: dict[str, int]
    restored: bool | None = None
    reset: bool | None = None
