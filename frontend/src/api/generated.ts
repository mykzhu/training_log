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
