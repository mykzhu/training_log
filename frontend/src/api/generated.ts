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
  bodyweight_reps: number;
  configured_weights: Array<number>;
  default_reps: number;
  default_weight: number;
  distance_m: number;
  draft_exercise_id: number;
  duration_seconds: number;
  exercise_id: number;
  exercise_name: string;
  measurement_type: string;
  position: number;
  profile_key: string;
  reps_options: Array<number>;
  reps_unit: string;
  sets: Array<CurrentWorkoutSetEntryResponse>;
  total_reps: number;
  total_sets: number;
  total_volume: number;
  total_volume_kg: number;
  weight_options: Array<number>;
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

export type DeleteExerciseProfileResponse = {
  deleted: boolean;
  profile?: ExerciseProfileResponse | null;
  profile_key: string;
};

export type DeleteExerciseResponse = {
  deleted: boolean;
  exercise?: Record<string, unknown> | null;
  exercise_id: number;
  usage?: Record<string, number> | null;
};

export type DeleteWorkoutResponse = {
  deleted: boolean;
  workout_id: number;
};

export type ExerciseCreateRequest = {
  default_reps?: number | null;
  default_weight?: number | null;
  is_active?: boolean | null;
  max_reps?: number | null;
  max_weight?: number | null;
  measurement_type?: string | null;
  min_reps?: number | null;
  min_weight?: number | null;
  name: string;
  profile_key?: string | null;
  reps_step?: number | null;
  reps_unit?: string | null;
  weight_step?: number | null;
  weights?: Array<number> | null;
};

export type ExerciseMutationResponse = {
  created?: boolean | null;
  exercise: ExerciseResponse;
};

export type ExerciseOrderUpdateRequest = {
  exercise_ids: Array<number>;
};

export type ExerciseProfileCreateRequest = {
  back_factor: number;
  category: string;
  compound_factor: number;
  exercise_factor: number;
  key?: string | null;
  label: string;
};

export type ExerciseProfileMutationResponse = {
  created?: boolean | null;
  profile: ExerciseProfileResponse;
};

export type ExerciseProfileResponse = {
  back_factor: number;
  category: string;
  compound_factor: number;
  exercise_count: number;
  exercise_factor: number;
  is_active: boolean;
  is_builtin: boolean;
  key: string;
  label: string;
  sort_order: number;
};

export type ExerciseProfileUpdateRequest = {
  back_factor?: number | null;
  category?: string | null;
  compound_factor?: number | null;
  exercise_factor?: number | null;
  is_active?: boolean | null;
  label?: string | null;
};

export type ExerciseProfilesResponse = {
  profiles: Array<ExerciseProfileResponse>;
};

export type ExerciseResponse = {
  default_reps: number;
  default_weight: number;
  id: number;
  is_active: boolean;
  max_reps: number;
  max_weight: number;
  measurement_type: string;
  min_reps: number;
  min_weight: number;
  name: string;
  profile_key: string;
  reps_step: number;
  reps_unit: string;
  sort_order: number;
  weight_step: number;
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
  default_reps?: number | null;
  default_weight?: number | null;
  is_active?: boolean | null;
  max_reps?: number | null;
  max_weight?: number | null;
  measurement_type?: string | null;
  min_reps?: number | null;
  min_weight?: number | null;
  name?: string | null;
  profile_key?: string | null;
  reps_step?: number | null;
  reps_unit?: string | null;
  weight_step?: number | null;
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

export type GarminAutoSyncSettingsResponse = {
  enabled: boolean;
  last_attempt_at?: string | null;
  last_error?: string | null;
  last_result?: Record<string, unknown> | null;
  last_success_at?: string | null;
  next_eligible_at?: string | null;
  sync_after_local_time: string;
  sync_days: number;
  timezone: string;
};

export type GarminAutoSyncSettingsUpdateRequest = {
  enabled?: boolean | null;
  sync_after_local_time?: string | null;
  sync_days?: number | null;
};

export type GarminDailyMetricResponse = {
  body_battery_end?: number | null;
  body_battery_start?: number | null;
  completeness_message?: string | null;
  completeness_status?: string | null;
  date: string;
  hrv_ms?: number | null;
  is_complete?: boolean | null;
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
  body_battery_start?: number | null;
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

export type GarminStatsFreshnessResponse = {
  days_since_latest_metric?: number | null;
  latest_metric_date?: string | null;
  message: string;
  status: string;
};

export type GarminStatsInsightsResponse = {
  baseline_days: number;
  baseline_end_date: string;
  baseline_start_date: string;
  current_date: string;
  current_metric_completeness?: Record<string, unknown> | null;
  freshness: GarminStatsFreshnessResponse;
  minimum_baseline_samples: number;
  overall_message: string;
  overall_status: string;
  previous_date: string;
  readiness_impact: GarminStatsReadinessImpactResponse;
  readiness_previous_date?: string | null;
  readiness_scoring_date?: string | null;
  readiness_scoring_date_source?: string | null;
  scoring_metric_completeness?: Record<string, unknown> | null;
  signals: Array<GarminStatsSignalResponse>;
};

export type GarminStatsLatestMetricResponse = {
  completeness_message?: string | null;
  completeness_status?: string | null;
  date: string;
  is_complete?: boolean | null;
  synced_at: string;
};

export type GarminStatsPointResponse = {
  body_battery_end?: number | null;
  body_battery_start?: number | null;
  completeness_message?: string | null;
  completeness_status?: string | null;
  date: string;
  hrv_ms?: number | null;
  is_complete?: boolean | null;
  resting_heart_rate?: number | null;
  steps?: number | null;
  stress_avg?: number | null;
};

export type GarminStatsReadinessImpactResponse = {
  display_only_metric_count: number;
  max_score_delta: number;
  min_score_delta: number;
  raw_score_delta: number;
  score_delta: number;
  used_metric_count: number;
};

export type GarminStatsResponse = {
  baselines: GarminStatsBaselinesResponse;
  coverage: GarminStatsCoverageResponse;
  date_from?: string | null;
  date_to?: string | null;
  insights: GarminStatsInsightsResponse;
  latest_metric?: GarminStatsLatestMetricResponse | null;
  metric_count: number;
  range: string;
  series: Array<GarminStatsPointResponse>;
};

export type GarminStatsSignalResponse = {
  baseline_median?: number | null;
  baseline_sample_count: number;
  current?: number | null;
  delta?: number | null;
  delta_percent?: number | null;
  direction: string;
  label: string;
  message: string;
  metric: string;
  score_delta: number;
  source_date: string;
  status: string;
  unit: string;
  used_for_readiness: boolean;
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

export type LogEntryResponse = {
  exception?: string | null;
  function?: string | null;
  id: number;
  level: string;
  line?: number | null;
  logger: string;
  message: string;
  module?: string | null;
  timestamp: string;
};

export type LogsResponse = {
  count: number;
  entries: Array<LogEntryResponse>;
  filtered_available: number;
  limit: number;
  total_available: number;
  truncated: boolean;
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
  training_load: Record<string, unknown>;
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
  bodyweight_reps: number;
  configured_weights: Array<number>;
  default_reps: number;
  default_weight: number;
  distance_m: number;
  duration_seconds: number;
  exercise_id: number;
  exercise_name: string;
  measurement_type: string;
  position: number;
  profile_key: string;
  reps_options: Array<number>;
  reps_unit: string;
  sets: Array<SetEntryResponse>;
  total_reps: number;
  total_sets: number;
  total_volume: number;
  total_volume_kg: number;
  weight_options: Array<number>;
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
  DeleteExerciseProfileResponse: DeleteExerciseProfileResponse;
  DeleteExerciseResponse: DeleteExerciseResponse;
  DeleteWorkoutResponse: DeleteWorkoutResponse;
  ExerciseCreateRequest: ExerciseCreateRequest;
  ExerciseMutationResponse: ExerciseMutationResponse;
  ExerciseOrderUpdateRequest: ExerciseOrderUpdateRequest;
  ExerciseProfileCreateRequest: ExerciseProfileCreateRequest;
  ExerciseProfileMutationResponse: ExerciseProfileMutationResponse;
  ExerciseProfileResponse: ExerciseProfileResponse;
  ExerciseProfileUpdateRequest: ExerciseProfileUpdateRequest;
  ExerciseProfilesResponse: ExerciseProfilesResponse;
  ExerciseResponse: ExerciseResponse;
  ExerciseStatsResponseModel: ExerciseStatsResponseModel;
  ExerciseUpdateRequest: ExerciseUpdateRequest;
  ExerciseWeightsResponse: ExerciseWeightsResponse;
  ExerciseWeightsUpdateRequest: ExerciseWeightsUpdateRequest;
  ExercisesResponse: ExercisesResponse;
  FinishCurrentWorkoutResponse: FinishCurrentWorkoutResponse;
  GarminAutoSyncSettingsResponse: GarminAutoSyncSettingsResponse;
  GarminAutoSyncSettingsUpdateRequest: GarminAutoSyncSettingsUpdateRequest;
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
  GarminStatsFreshnessResponse: GarminStatsFreshnessResponse;
  GarminStatsInsightsResponse: GarminStatsInsightsResponse;
  GarminStatsLatestMetricResponse: GarminStatsLatestMetricResponse;
  GarminStatsPointResponse: GarminStatsPointResponse;
  GarminStatsReadinessImpactResponse: GarminStatsReadinessImpactResponse;
  GarminStatsResponse: GarminStatsResponse;
  GarminStatsSignalResponse: GarminStatsSignalResponse;
  GarminStatusResponse: GarminStatusResponse;
  GarminSyncRequest: GarminSyncRequest;
  GarminSyncResponse: GarminSyncResponse;
  HTTPValidationError: HTTPValidationError;
  LoadMetricsResponse: LoadMetricsResponse;
  LogEntryResponse: LogEntryResponse;
  LogsResponse: LogsResponse;
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
