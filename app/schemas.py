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
    measurement_type: str | None = Field(default=None, min_length=1, max_length=40)
    reps_unit: str | None = Field(default=None, min_length=1, max_length=16)
    weights: list[float] = Field(default_factory=list)
    default_weight: float | None = Field(default=None, ge=0)
    min_weight: float | None = Field(default=None, ge=0)
    max_weight: float | None = Field(default=None, ge=0)
    weight_step: float | None = Field(default=None, gt=0)
    default_reps: int | None = Field(default=None, ge=1, le=1000)
    min_reps: int | None = Field(default=None, ge=1, le=1000)
    max_reps: int | None = Field(default=None, ge=1, le=1000)
    reps_step: int | None = Field(default=None, ge=1, le=1000)


class ExerciseUpdateRequest(AppBaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    profile_key: str | None = Field(default=None, min_length=1, max_length=80)
    measurement_type: str | None = Field(default=None, min_length=1, max_length=40)
    reps_unit: str | None = Field(default=None, min_length=1, max_length=16)
    default_weight: float | None = Field(default=None, ge=0)
    min_weight: float | None = Field(default=None, ge=0)
    max_weight: float | None = Field(default=None, ge=0)
    weight_step: float | None = Field(default=None, gt=0)
    default_reps: int | None = Field(default=None, ge=1, le=1000)
    min_reps: int | None = Field(default=None, ge=1, le=1000)
    max_reps: int | None = Field(default=None, ge=1, le=1000)
    reps_step: int | None = Field(default=None, ge=1, le=1000)


class ExerciseWeightsUpdateRequest(AppBaseModel):
    weights: list[float]


class ExerciseOrderUpdateRequest(AppBaseModel):
    exercise_ids: list[int]


class ExerciseProfileCreateRequest(AppBaseModel):
    key: str | None = Field(default=None, min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    exercise_factor: float = Field(ge=0, le=5)
    compound_factor: float = Field(ge=0, le=5)
    back_factor: float = Field(ge=0, le=5)


class ExerciseProfileUpdateRequest(AppBaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=120)
    exercise_factor: float | None = Field(default=None, ge=0, le=5)
    compound_factor: float | None = Field(default=None, ge=0, le=5)
    back_factor: float | None = Field(default=None, ge=0, le=5)
    is_active: bool | None = None


class AddSetRequest(AppBaseModel):
    weight: float = Field(ge=0)
    reps: int = Field(ge=1, le=1000)


class UpdateSetRequest(AppBaseModel):
    weight: float | None = Field(default=None, ge=0)
    reps: int | None = Field(default=None, ge=1, le=1000)


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
    measurement_type: str
    reps_unit: str
    position: int
    sets: list[SetEntryResponse]
    total_sets: int
    total_reps: int
    total_volume: float
    total_volume_kg: float
    bodyweight_reps: int
    duration_seconds: int
    distance_m: int
    default_weight: float
    default_reps: int
    configured_weights: list[float]
    weight_options: list[float]
    reps_options: list[int]


class CurrentWorkoutExerciseResponse(AppBaseModel):
    draft_exercise_id: int
    exercise_id: int
    exercise_name: str
    profile_key: str
    measurement_type: str
    reps_unit: str
    position: int
    sets: list[CurrentWorkoutSetEntryResponse]
    total_sets: int
    total_reps: int
    total_volume: float
    total_volume_kg: float
    bodyweight_reps: int
    duration_seconds: int
    distance_m: int
    default_weight: float
    default_reps: int
    configured_weights: list[float]
    weight_options: list[float]
    reps_options: list[int]


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
    measurement_type: str
    reps_unit: str
    default_weight: float
    min_weight: float
    max_weight: float
    weight_step: float
    default_reps: int
    min_reps: int
    max_reps: int
    reps_step: int
    weights: list[float]


class ExercisesResponse(AppBaseModel):
    exercises: list[ExerciseResponse]


class ExerciseMutationResponse(AppBaseModel):
    exercise: ExerciseResponse
    created: bool | None = None


class DeleteExerciseResponse(AppBaseModel):
    deleted: bool
    exercise_id: int
    exercise: dict[str, Any] | None = None
    usage: dict[str, int] | None = None


class ExerciseWeightsResponse(AppBaseModel):
    exercise_id: int
    weights: list[float]


class ExerciseProfileResponse(AppBaseModel):
    key: str
    label: str
    category: str
    exercise_factor: float
    compound_factor: float
    back_factor: float
    is_builtin: bool
    is_active: bool
    sort_order: int
    exercise_count: int


class ExerciseProfilesResponse(AppBaseModel):
    profiles: list[ExerciseProfileResponse]


class ExerciseProfileMutationResponse(AppBaseModel):
    profile: ExerciseProfileResponse
    created: bool | None = None


class DeleteExerciseProfileResponse(AppBaseModel):
    deleted: bool
    profile_key: str
    profile: ExerciseProfileResponse | None = None


class LogEntryResponse(AppBaseModel):
    id: int
    timestamp: str
    level: str
    logger: str
    message: str
    module: str | None = None
    function: str | None = None
    line: int | None = None
    exception: str | None = None


class LogsResponse(AppBaseModel):
    limit: int
    count: int
    total_available: int
    truncated: bool
    entries: list[LogEntryResponse]


class RecoveryContextResponse(FlexibleResponse):
    as_of: str
    has_history: bool


class GarminReadinessAdjustmentResponse(FlexibleResponse):
    applied: bool
    status: str
    score_delta: int
    raw_score_delta: int
    min_score_delta: int
    max_score_delta: int
    baseline_days: int
    minimum_baseline_samples: int
    current_date: str
    previous_date: str
    baseline_start_date: str
    baseline_end_date: str
    local_date_source: str
    available_rule_count: int
    scored_rule_count: int
    missing_rule_count: int
    insufficient_baseline_rule_count: int
    display_only_rule_count: int
    scored_metrics_summary: str
    summary: str
    rules: list[dict[str, Any]]

class NextWorkoutRecommendationResponse(FlexibleResponse):
    status: str
    title: str
    score: float | None
    summary: str
    reasons: list[str]
    last_workout_id: int | None
    garmin_adjustment: GarminReadinessAdjustmentResponse | None = None
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
    is_complete: bool | None = None
    completeness_status: str | None = None
    completeness_message: str | None = None


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
    current_date: str
    previous_date: str
    local_date_source: str
    today_present: bool
    yesterday_present: bool
    latest_metric_date: str | None
    freshness_status: str
    missing_today_metrics: list[str]
    message: str


class GarminLoginRequest(AppBaseModel):
    username: str = Field(min_length=1, max_length=240)
    password: str = Field(min_length=1, max_length=240)


class GarminMfaRequest(AppBaseModel):
    mfa_token: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=40)


class GarminSyncRequest(AppBaseModel):
    days: int | None = Field(default=None, ge=1, le=90)


class GarminAutoSyncSettingsUpdateRequest(AppBaseModel):
    enabled: bool | None = None
    sync_after_local_time: str | None = Field(
        default=None,
        pattern=r"^\d{2}:\d{2}$",
    )
    sync_days: int | None = Field(default=None, ge=1, le=90)


class GarminAutoSyncSettingsResponse(AppBaseModel):
    enabled: bool
    sync_after_local_time: str
    sync_days: int
    last_attempt_at: str | None
    last_success_at: str | None
    last_error: str | None
    last_result: dict[str, Any] | None
    next_eligible_at: str | None
    timezone: str


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


class GarminStatsPointResponse(AppBaseModel):
    date: str
    resting_heart_rate: int | None
    hrv_ms: float | None
    stress_avg: int | None
    body_battery_start: int | None
    body_battery_end: int | None
    steps: int | None
    is_complete: bool | None = None
    completeness_status: str | None = None
    completeness_message: str | None = None


class GarminStatsCoverageResponse(AppBaseModel):
    expected_days: int | None
    available_days: int
    missing_days: int | None


class GarminStatsLatestMetricResponse(AppBaseModel):
    date: str
    synced_at: str
    is_complete: bool | None = None
    completeness_status: str | None = None
    completeness_message: str | None = None


class GarminStatsBaselinesResponse(AppBaseModel):
    resting_heart_rate: float | None
    hrv_ms: float | None
    stress_avg: float | None
    body_battery_start: float | None
    steps: float | None


class GarminStatsFreshnessResponse(AppBaseModel):
    status: str
    latest_metric_date: str | None
    days_since_latest_metric: int | None
    message: str


class GarminStatsReadinessImpactResponse(AppBaseModel):
    score_delta: int
    raw_score_delta: int
    min_score_delta: int
    max_score_delta: int
    used_metric_count: int
    display_only_metric_count: int


class GarminStatsSignalResponse(AppBaseModel):
    metric: str
    label: str
    unit: str
    source_date: str
    current: float | None
    baseline_median: float | None
    baseline_sample_count: int
    delta: float | None
    delta_percent: float | None
    status: str
    direction: str
    used_for_readiness: bool
    score_delta: int
    message: str


class GarminStatsInsightsResponse(AppBaseModel):
    current_date: str
    previous_date: str
    baseline_start_date: str
    baseline_end_date: str
    readiness_scoring_date: str | None = None
    readiness_scoring_date_source: str | None = None
    readiness_previous_date: str | None = None
    current_metric_completeness: dict[str, Any] | None = None
    scoring_metric_completeness: dict[str, Any] | None = None
    baseline_days: int
    minimum_baseline_samples: int
    freshness: GarminStatsFreshnessResponse
    overall_status: str
    overall_message: str
    readiness_impact: GarminStatsReadinessImpactResponse
    signals: list[GarminStatsSignalResponse]


class GarminStatsResponse(AppBaseModel):
    range: str
    date_from: str | None
    date_to: str | None
    metric_count: int
    coverage: GarminStatsCoverageResponse
    latest_metric: GarminStatsLatestMetricResponse | None
    series: list[GarminStatsPointResponse]
    baselines: GarminStatsBaselinesResponse
    insights: GarminStatsInsightsResponse


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
    training_load: dict[str, Any]
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
