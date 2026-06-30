// Generated from docs/openapi.json by scripts/generate_api_contracts.py.
// Do not edit manually.

export type AddExerciseRequest = {
  exercise_id: number;
};

export type AddSetRequest = {
  reps: number;
  weight: number;
};

export type BackupMutationResponse = {
  counts: Record<string, number>;
  reset?: boolean | null;
  restored?: boolean | null;
};

export type BackupPayloadResponse = {
  schema_version: number;
};

export type CurrentWorkoutExerciseResponse = {
  configured_weights: Array<number>;
  default_reps: number;
  default_weight: number;
  draft_exercise_id: number;
  exercise_id: number;
  exercise_name: string;
  position: number;
  profile_key: string;
  sets: Array<CurrentWorkoutSetEntryResponse>;
  total_reps: number;
  total_sets: number;
  total_volume: number;
};

export type CurrentWorkoutResponse = {
  active: boolean;
  elapsed_seconds: number;
  exercises: Array<CurrentWorkoutExerciseResponse>;
  garmin_recovery?: GarminRecoverySnapshotResponse | null;
  load_metrics?: LoadMetricsResponse | null;
  lower_back_pain?: number | null;
  next_workout_recommendation?: NextWorkoutRecommendationResponse | null;
  recovery_context?: RecoveryContextResponse | null;
  session_rpe?: number | null;
  started_at?: string | null;
  total_reps: number;
  total_sets: number;
  total_volume: number;
};

export type CurrentWorkoutSetEntryResponse = {
  created_at: string;
  id: number;
  reps: number;
  set_number: number;
  weight: number;
};

export type DeleteWorkoutResponse = {
  deleted: boolean;
  workout_id: number;
};

export type ExerciseCreateRequest = {
  is_active?: boolean | null;
  name: string;
  profile_key?: string | null;
  weights?: Array<number> | null;
};

export type ExerciseMutationResponse = {
  created?: boolean | null;
  exercise: ExerciseResponse;
};

export type ExerciseOrderUpdateRequest = {
  exercise_ids: Array<number>;
};

export type ExerciseProfileResponse = {
  category: string;
  key: string;
  label: string;
};

export type ExerciseProfilesResponse = {
  profiles: Array<ExerciseProfileResponse>;
};

export type ExerciseResponse = {
  id: number;
  is_active: boolean;
  name: string;
  profile_key: string;
  sort_order: number;
  weights: Array<number>;
};

export type ExerciseStatsResponseModel = {
  exercise: Record<string, unknown>;
  history: Array<Record<string, unknown>>;
  latest?: Record<string, unknown> | null;
  limit: number | string;
  per_workout_sets: Array<Record<string, unknown>>;
  profile: ExerciseProfileResponse;
  source_workout_ids: Array<number>;
  strength_progress: Record<string, unknown>;
  summary: Record<string, unknown>;
  trend: Record<string, unknown>;
};

export type ExerciseUpdateRequest = {
  is_active?: boolean | null;
  name?: string | null;
  profile_key?: string | null;
};

export type ExerciseWeightsResponse = {
  exercise_id: number;
  weights: Array<number>;
};

export type ExerciseWeightsUpdateRequest = {
  weights: Array<number>;
};

export type ExercisesResponse = {
  exercises: Array<ExerciseResponse>;
};

export type FinishCurrentWorkoutResponse = {
  current_workout: CurrentWorkoutResponse;
  workout_id: number;
};

export type GarminDailyMetricResponse = {
  body_battery_end?: number | null;
  body_battery_start?: number | null;
  date: string;
  hrv_ms?: number | null;
  raw_diagnostics: Record<string, unknown>;
  resting_heart_rate?: number | null;
  steps?: number | null;
  stress_avg?: number | null;
  synced_at: string;
};

export type GarminDailyMetricsResponse = {
  days: number;
  metrics: Array<GarminDailyMetricResponse>;
};

export type GarminDisconnectResponse = {
  connected: boolean;
  last_synced_at?: string | null;
  latest_metric?: GarminDailyMetricResponse | null;
  pending_mfa: boolean;
};

export type GarminLoginRequest = {
  password: string;
  username: string;
};

export type GarminLoginResponse = {
  connected: boolean;
  mfa_required: boolean;
  mfa_token?: string | null;
};

export type GarminMfaRequest = {
  code: string;
  mfa_token: string;
};

export type GarminReadinessAdjustmentResponse = {
  applied: boolean;
  available_rule_count: number;
  baseline_days: number;
  baseline_end_date: string;
  baseline_start_date: string;
  current_date: string;
  display_only_rule_count: number;
  insufficient_baseline_rule_count: number;
  local_date_source: string;
  max_score_delta: number;
  min_score_delta: number;
  minimum_baseline_samples: number;
  missing_rule_count: number;
  previous_date: string;
  raw_score_delta: number;
  rules: Array<Record<string, unknown>>;
  score_delta: number;
  scored_metrics_summary: string;
  scored_rule_count: number;
  status: string;
  summary: string;
};

export type GarminRecoverySnapshotResponse = {
  connected: boolean;
  current_date: string;
  freshness_status: string;
  last_synced_at?: string | null;
  latest?: GarminDailyMetricResponse | null;
  latest_metric_date?: string | null;
  local_date_source: string;
  message: string;
  missing_today_metrics: Array<string>;
  previous_date: string;
  sample_count_35d: number;
  today?: GarminDailyMetricResponse | null;
  today_present: boolean;
  yesterday?: GarminDailyMetricResponse | null;
  yesterday_present: boolean;
};

export type GarminStatsBaselinesResponse = {
  hrv_ms?: number | null;
  resting_heart_rate?: number | null;
  steps?: number | null;
  stress_avg?: number | null;
};

export type GarminStatsCoverageResponse = {
  available_days: number;
  expected_days?: number | null;
  missing_days?: number | null;
};

export type GarminStatsLatestMetricResponse = {
  date: string;
  synced_at: string;
};

export type GarminStatsPointResponse = {
  body_battery_end?: number | null;
  body_battery_start?: number | null;
  date: string;
  hrv_ms?: number | null;
  resting_heart_rate?: number | null;
  steps?: number | null;
  stress_avg?: number | null;
};

export type GarminStatsResponse = {
  baselines: GarminStatsBaselinesResponse;
  coverage: GarminStatsCoverageResponse;
  date_from?: string | null;
  date_to?: string | null;
  latest_metric?: GarminStatsLatestMetricResponse | null;
  metric_count: number;
  range: string;
  series: Array<GarminStatsPointResponse>;
};

export type GarminStatusResponse = {
  connected: boolean;
  last_synced_at?: string | null;
  latest_metric?: GarminDailyMetricResponse | null;
  pending_mfa: boolean;
};

export type GarminSyncRequest = {
  days?: number | null;
};

export type GarminSyncResponse = {
  days: number;
  errors: Record<string, string>;
  saved_dates: Array<string>;
  skipped_dates: Array<string>;
  status: GarminStatusResponse;
  synced: boolean;
};

export type HTTPValidationError = {
  detail?: Array<ValidationError> | null;
};

export type LoadMetricsResponse = {
  back_stress_score: number;
  compound_score: number;
  intensity_score?: number | null;
  load_label: string;
  load_score: number;
};

export type NextWorkoutRecommendationResponse = {
  exercise_recommendations: Array<Record<string, unknown>>;
  garmin_adjustment?: GarminReadinessAdjustmentResponse | null;
  last_workout_id?: number | null;
  reasons: Array<string>;
  score?: number | null;
  status: string;
  summary: string;
  title: string;
};

export type RecoveryContextResponse = {
  as_of: string;
  has_history: boolean;
};

export type SetEntryResponse = {
  created_at: string;
  id: number;
  reps: number;
  set_number: number;
  weight: number;
  workout_exercise_id: number;
};

export type StatsResponseModel = {
  charts: Record<string, unknown>;
  limit: number | string;
  stats: Record<string, unknown>;
};

export type UpdateSetRequest = {
  reps?: number | null;
  weight?: number | null;
};

export type ValidationError = {
  loc: Array<string | number>;
  msg: string;
  type: string;
};

export type WorkoutAnalysisExerciseResponse = {
  best_e1rm?: number | null;
  best_e1rm_set?: Record<string, unknown> | null;
  best_set?: Record<string, unknown> | null;
  exercise_id: number;
  exercise_name: string;
  pr_flags: Array<string>;
};

export type WorkoutAnalysisPrResponse = {
  exercise_name: string;
  type: string;
};

export type WorkoutAnalysisResponse = {
  exercises: Array<WorkoutAnalysisExerciseResponse>;
  prs: Array<WorkoutAnalysisPrResponse>;
};

export type WorkoutCoreResponse = {
  created_at: string;
  duration_seconds?: number | null;
  finished_at?: string | null;
  id: number;
  lower_back_pain?: number | null;
  session_rpe?: number | null;
  workout_date: string;
};

export type WorkoutDetailResponse = {
  analysis: WorkoutAnalysisResponse;
  exercises: Array<WorkoutExerciseResponse>;
  load_metrics: LoadMetricsResponse;
  total_reps: number;
  total_sets: number;
  total_volume: number;
  workout: WorkoutCoreResponse;
};

export type WorkoutExerciseResponse = {
  configured_weights: Array<number>;
  default_reps: number;
  default_weight: number;
  exercise_id: number;
  exercise_name: string;
  position: number;
  profile_key: string;
  sets: Array<SetEntryResponse>;
  total_reps: number;
  total_sets: number;
  total_volume: number;
  workout_exercise_id: number;
};

export type WorkoutMetadataUpdate = {
  lower_back_pain?: number | null;
  session_rpe?: number | null;
};

export type WorkoutSummaryResponse = {
  created_at: string;
  duration_seconds?: number | null;
  exercises_count: number;
  finished_at?: string | null;
  id: number;
  load_metrics: LoadMetricsResponse;
  lower_back_pain?: number | null;
  session_rpe?: number | null;
  total_reps: number;
  total_sets: number;
  total_volume: number;
  workout_date: string;
};

export type WorkoutUpdateRequest = {
  created_at?: string | null;
  lower_back_pain?: number | null;
  session_rpe?: number | null;
};

export type WorkoutsResponse = {
  limit: number;
  workouts: Array<WorkoutSummaryResponse>;
};

export type ApiSchemas = {
  AddExerciseRequest: AddExerciseRequest;
  AddSetRequest: AddSetRequest;
  BackupMutationResponse: BackupMutationResponse;
  BackupPayloadResponse: BackupPayloadResponse;
  CurrentWorkoutExerciseResponse: CurrentWorkoutExerciseResponse;
  CurrentWorkoutResponse: CurrentWorkoutResponse;
  CurrentWorkoutSetEntryResponse: CurrentWorkoutSetEntryResponse;
  DeleteWorkoutResponse: DeleteWorkoutResponse;
  ExerciseCreateRequest: ExerciseCreateRequest;
  ExerciseMutationResponse: ExerciseMutationResponse;
  ExerciseOrderUpdateRequest: ExerciseOrderUpdateRequest;
  ExerciseProfileResponse: ExerciseProfileResponse;
  ExerciseProfilesResponse: ExerciseProfilesResponse;
  ExerciseResponse: ExerciseResponse;
  ExerciseStatsResponseModel: ExerciseStatsResponseModel;
  ExerciseUpdateRequest: ExerciseUpdateRequest;
  ExerciseWeightsResponse: ExerciseWeightsResponse;
  ExerciseWeightsUpdateRequest: ExerciseWeightsUpdateRequest;
  ExercisesResponse: ExercisesResponse;
  FinishCurrentWorkoutResponse: FinishCurrentWorkoutResponse;
  GarminDailyMetricResponse: GarminDailyMetricResponse;
  GarminDailyMetricsResponse: GarminDailyMetricsResponse;
  GarminDisconnectResponse: GarminDisconnectResponse;
  GarminLoginRequest: GarminLoginRequest;
  GarminLoginResponse: GarminLoginResponse;
  GarminMfaRequest: GarminMfaRequest;
  GarminReadinessAdjustmentResponse: GarminReadinessAdjustmentResponse;
  GarminRecoverySnapshotResponse: GarminRecoverySnapshotResponse;
  GarminStatsBaselinesResponse: GarminStatsBaselinesResponse;
  GarminStatsCoverageResponse: GarminStatsCoverageResponse;
  GarminStatsLatestMetricResponse: GarminStatsLatestMetricResponse;
  GarminStatsPointResponse: GarminStatsPointResponse;
  GarminStatsResponse: GarminStatsResponse;
  GarminStatusResponse: GarminStatusResponse;
  GarminSyncRequest: GarminSyncRequest;
  GarminSyncResponse: GarminSyncResponse;
  HTTPValidationError: HTTPValidationError;
  LoadMetricsResponse: LoadMetricsResponse;
  NextWorkoutRecommendationResponse: NextWorkoutRecommendationResponse;
  RecoveryContextResponse: RecoveryContextResponse;
  SetEntryResponse: SetEntryResponse;
  StatsResponseModel: StatsResponseModel;
  UpdateSetRequest: UpdateSetRequest;
  ValidationError: ValidationError;
  WorkoutAnalysisExerciseResponse: WorkoutAnalysisExerciseResponse;
  WorkoutAnalysisPrResponse: WorkoutAnalysisPrResponse;
  WorkoutAnalysisResponse: WorkoutAnalysisResponse;
  WorkoutCoreResponse: WorkoutCoreResponse;
  WorkoutDetailResponse: WorkoutDetailResponse;
  WorkoutExerciseResponse: WorkoutExerciseResponse;
  WorkoutMetadataUpdate: WorkoutMetadataUpdate;
  WorkoutSummaryResponse: WorkoutSummaryResponse;
  WorkoutUpdateRequest: WorkoutUpdateRequest;
  WorkoutsResponse: WorkoutsResponse;
};
