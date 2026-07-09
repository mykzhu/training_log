export type SetEntry = {
  id: number;
  workout_exercise_id?: number;
  set_number: number;
  weight: number;
  reps: number;
  created_at: string;
};

export type ExerciseMeasurementType =
  | "weighted_reps"
  | "bodyweight_reps"
  | "loaded_carry_time"
  | "loaded_carry_distance"
  | "reps_only";

export type CurrentWorkoutExercise = {
  draft_exercise_id: number;
  exercise_id: number;
  exercise_name: string;
  profile_key: string;
  measurement_type: ExerciseMeasurementType;
  reps_unit: string;
  position: number;
  sets: SetEntry[];
  total_sets: number;
  total_reps: number;
  total_volume: number;
  total_volume_kg: number;
  bodyweight_reps: number;
  duration_seconds: number;
  distance_m: number;
  default_weight: number;
  default_reps: number;
  configured_weights: number[];
  weight_options: number[];
  reps_options: number[];
};

export type WorkoutExercise = {
  workout_exercise_id: number;
  exercise_id: number;
  exercise_name: string;
  profile_key: string;
  measurement_type: ExerciseMeasurementType;
  reps_unit: string;
  position: number;
  sets: SetEntry[];
  total_sets: number;
  total_reps: number;
  total_volume: number;
  total_volume_kg: number;
  bodyweight_reps: number;
  duration_seconds: number;
  distance_m: number;
  default_weight: number;
  default_reps: number;
  configured_weights: number[];
  weight_options: number[];
  reps_options: number[];
};

export type LoadMetrics = {
  load_score: number;
  load_label: string;
  compound_score: number;
  intensity_score: number | null;
  back_stress_score: number;
};

export type RecoveryWindow = {
  days: number;
  workout_count: number;
  load_score: number;
  load_label?: string;
  compound_score: number;
  back_stress_score: number;
  avg_rpe: number | null;
  avg_back_pain: number | null;
  weekly_load_equivalent: number;
  weekly_back_stress_equivalent: number;
  weekly_workout_average: number;
  first_workout_at: string | null;
  last_workout_at: string | null;
  coverage_days: number;
  active_week_count: number;
  avg_load_per_workout: number;
  avg_back_stress_per_workout: number;
};

export type OverallIntervalContext = {
  median_days: number | null;
  sample_count: number;
  confidence: "low" | "medium" | "high";
  current_ratio: number | null;
  status: string;
  status_label: string;
};

export type SuggestedSet = {
  set_number: number;
  weight: number;
  reps: number;
  strategy: string;
};

export type RecoveryContext = {
  as_of: string;
  has_history: boolean;
  previous_workout_id: number | null;
  previous_workout_at: string | null;
  hours_since_previous_workout: number | null;
  days_since_previous_workout: number | null;
  previous_gap_label: string;
  hint: string;
  last_7d: RecoveryWindow;
  previous_21d: RecoveryWindow;
  last_42d: RecoveryWindow;
  overall_interval: OverallIntervalContext;
  relative_load: {
    acute_to_baseline: number | null;
    acute_back_to_baseline: number | null;
    display_acute_to_baseline: number | null;
    display_acute_back_to_baseline: number | null;
    baseline_confidence: "low" | "medium" | "high";
    baseline_is_reliable: boolean;
  };
};

export type ExerciseRecommendation = {
  exercise_name: string;
  action: string;
  action_label: string;
  target: string;
  target_strategy: string;
  suggested_sets: SuggestedSet[];
  reason: string;
  gap_label: string;
  usual_gap_label: string;
  interval_sample_count: number;
  interval_confidence: "low" | "medium" | "high";
  gap_status_label: string;
  progression_status: string;
  progression_label: string;
  progression_summary: string;
  e1rm_change_label: string;
  volume_change_label: string;
};

export type GarminReadinessAdjustmentRule = {
  metric: string;
  label: string;
  source_date: string;
  current: number | null;
  baseline_median: number | null;
  baseline_sample_count: number;
  score_delta: number;
  status: string;
  message: string;
};

export type GarminReadinessAdjustment = {
  applied: boolean;
  status: string;
  score_delta: number;
  raw_score_delta: number;
  min_score_delta: number;
  max_score_delta: number;
  baseline_days: number;
  minimum_baseline_samples: number;
  current_date: string;
  previous_date: string;
  baseline_start_date: string;
  baseline_end_date: string;
  local_date_source: string;
  available_rule_count: number;
  scored_rule_count: number;
  missing_rule_count: number;
  insufficient_baseline_rule_count: number;
  display_only_rule_count: number;
  scored_metrics_summary: string;
  summary: string;
  rules: GarminReadinessAdjustmentRule[];
};

export type NextWorkoutRecommendation = {
  status: string;
  title: string;
  score: number | null;
  summary: string;
  reasons: string[];
  last_workout_id: number | null;
  last_workout_at?: string;
  garmin_adjustment?: GarminReadinessAdjustment | null;
  exercise_recommendations: ExerciseRecommendation[];
};

export type GarminDailyMetric = {
  date: string;
  resting_heart_rate: number | null;
  hrv_ms: number | null;
  stress_avg: number | null;
  body_battery_start: number | null;
  body_battery_end: number | null;
  steps: number | null;
  synced_at: string;
  raw_diagnostics: Record<string, unknown>;
  is_complete?: boolean | null;
  completeness_status?: string | null;
  completeness_message?: string | null;
};

export type GarminStatus = {
  connected: boolean;
  last_synced_at: string | null;
  latest_metric: GarminDailyMetric | null;
  pending_mfa: boolean;
};

export type GarminAutoSyncSettings = {
  enabled: boolean;
  sync_after_local_time: string;
  sync_days: number;
  last_attempt_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  last_result: Record<string, unknown> | null;
  next_eligible_at: string | null;
  timezone: string;
};

export type GarminAutoSyncSettingsUpdate = {
  enabled?: boolean;
  sync_after_local_time?: string;
  sync_days?: number;
};

export type GarminRecoverySnapshot = {
  connected: boolean;
  today: GarminDailyMetric | null;
  yesterday: GarminDailyMetric | null;
  latest: GarminDailyMetric | null;
  last_synced_at: string | null;
  sample_count_35d: number;
  current_date: string;
  previous_date: string;
  local_date_source: string;
  today_present: boolean;
  yesterday_present: boolean;
  latest_metric_date: string | null;
  freshness_status: string;
  missing_today_metrics: string[];
  message: string;
};

export type GarminLoginResponse = {
  connected: boolean;
  mfa_required: boolean;
  mfa_token: string | null;
};

export type LogEntry = {
  id: number;
  timestamp: string;
  level: string;
  logger: string;
  message: string;
  module?: string | null;
  function?: string | null;
  line?: number | null;
  exception?: string | null;
};

export type LogsResponse = {
  limit: number;
  count: number;
  total_available: number;
  filtered_available: number;
  truncated: boolean;
  entries: LogEntry[];
};

export type GarminSyncResponse = {
  synced: boolean;
  days: number;
  saved_dates: string[];
  skipped_dates: string[];
  errors: Record<string, string>;
  status: GarminStatus;
};

export type GarminDailyMetricsResponse = {
  days: number;
  metrics: GarminDailyMetric[];
};

export type GarminStatsRange = "35" | "90" | "180" | "365" | "all";

export type GarminStatsPoint = {
  date: string;
  resting_heart_rate: number | null;
  hrv_ms: number | null;
  stress_avg: number | null;
  body_battery_start: number | null;
  body_battery_end: number | null;
  steps: number | null;
  is_complete?: boolean | null;
  completeness_status?: string | null;
  completeness_message?: string | null;
};


export type GarminStatsFreshness = {
  status: string;
  latest_metric_date: string | null;
  days_since_latest_metric: number | null;
  message: string;
};

export type GarminStatsReadinessImpact = {
  score_delta: number;
  raw_score_delta: number;
  min_score_delta: number;
  max_score_delta: number;
  used_metric_count: number;
  display_only_metric_count: number;
};

export type GarminStatsSignal = {
  metric: string;
  label: string;
  unit: string;
  source_date: string;
  current: number | null;
  baseline_median: number | null;
  baseline_sample_count: number;
  delta: number | null;
  delta_percent: number | null;
  status: string;
  direction: string;
  used_for_readiness: boolean;
  score_delta: number;
  message: string;
};

export type GarminStatsInsights = {
  current_date: string;
  previous_date: string;
  baseline_start_date: string;
  baseline_end_date: string;
  readiness_scoring_date?: string | null;
  readiness_scoring_date_source?: string | null;
  readiness_previous_date?: string | null;
  current_metric_completeness?: Record<string, unknown> | null;
  scoring_metric_completeness?: Record<string, unknown> | null;
  baseline_days: number;
  minimum_baseline_samples: number;
  freshness: GarminStatsFreshness;
  overall_status: string;
  overall_message: string;
  readiness_impact: GarminStatsReadinessImpact;
  signals: GarminStatsSignal[];
};

export type GarminStatsResponse = {
  range: GarminStatsRange;
  date_from: string | null;
  date_to: string | null;
  metric_count: number;
  coverage: {
    expected_days: number | null;
    available_days: number;
    missing_days: number | null;
  };
  latest_metric: {
    date: string;
    synced_at: string;
    is_complete?: boolean | null;
    completeness_status?: string | null;
    completeness_message?: string | null;
  } | null;
  series: GarminStatsPoint[];
  baselines: {
    resting_heart_rate: number | null;
    hrv_ms: number | null;
    stress_avg: number | null;
    body_battery_start: number | null;
    steps: number | null;
  };
  insights: GarminStatsInsights;
};

export type CurrentWorkout = {
  active: boolean;
  started_at: string | null;
  elapsed_seconds: number;
  session_rpe: number | null;
  lower_back_pain: number | null;
  total_sets: number;
  total_reps: number;
  total_volume: number;
  exercises: CurrentWorkoutExercise[];
  load_metrics: LoadMetrics | null;
  recovery_context: RecoveryContext | null;
  next_workout_recommendation: NextWorkoutRecommendation | null;
  garmin_recovery: GarminRecoverySnapshot | null;
};

export type WorkoutCore = {
  id: number;
  workout_date: string;
  created_at: string;
  finished_at: string | null;
  session_rpe: number | null;
  lower_back_pain: number | null;
  duration_seconds: number | null;
};

export type WorkoutSummary = WorkoutCore & {
  total_volume: number;
  total_reps: number;
  total_sets: number;
  exercises_count: number;
  load_metrics: LoadMetrics;
};

export type WorkoutDetail = {
  workout: WorkoutCore;
  exercises: WorkoutExercise[];
  total_volume: number;
  total_reps: number;
  total_sets: number;
  load_metrics: LoadMetrics;
  analysis: WorkoutAnalysis;
};

export type WorkoutAnalysis = {
  exercises: Array<{
    exercise_id: number;
    exercise_name: string;
    best_set: { weight: number; reps: number } | null;
    best_e1rm: number | null;
    best_e1rm_set: { weight: number; reps: number } | null;
    pr_flags: string[];
  }>;
  prs: Array<{
    exercise_name: string;
    type: string;
  }>;
};

export type Exercise = {
  id: number;
  name: string;
  is_active: boolean;
  sort_order: number;
  profile_key: string;
  measurement_type: ExerciseMeasurementType;
  reps_unit: string;
  default_weight: number;
  min_weight: number;
  max_weight: number;
  weight_step: number;
  default_reps: number;
  min_reps: number;
  max_reps: number;
  reps_step: number;
  weights: number[];
};

export type ExerciseCreatePayload = {
  name: string;
  is_active?: boolean;
  profile_key?: string;
  measurement_type?: ExerciseMeasurementType;
  reps_unit?: string;
  weights?: number[];
  default_weight?: number;
  min_weight?: number;
  max_weight?: number;
  weight_step?: number;
  default_reps?: number;
  min_reps?: number;
  max_reps?: number;
  reps_step?: number;
};

export type ExerciseUpdatePayload = {
  name?: string;
  is_active?: boolean;
  profile_key?: string;
  measurement_type?: ExerciseMeasurementType;
  reps_unit?: string;
  default_weight?: number;
  min_weight?: number;
  max_weight?: number;
  weight_step?: number;
  default_reps?: number;
  min_reps?: number;
  max_reps?: number;
  reps_step?: number;
};

export type ExerciseProfile = {
  key: string;
  label: string;
  category: string;
  exercise_factor: number;
  compound_factor: number;
  back_factor: number;
  is_builtin: boolean;
  is_active: boolean;
  sort_order: number;
  exercise_count: number;
};

export type ExerciseProfileCreatePayload = {
  key?: string;
  label: string;
  category: string;
  exercise_factor: number;
  compound_factor: number;
  back_factor: number;
};

export type ExerciseProfileUpdatePayload = {
  label?: string;
  category?: string;
  exercise_factor?: number;
  compound_factor?: number;
  back_factor?: number;
  is_active?: boolean;
};

export type StatsWorkout = {
  id: number;
  date: string;
  created_at: string;
  total_volume: number;
  total_volume_kg: number;
  bodyweight_reps: number;
  duration_seconds: number;
  distance_m: number;
  weighted_reps: number;
  total_reps: number;
  total_sets: number;
  avg_intensity: number | null;
  avg_kg_per_rep: number | null;
  session_rpe: number | null;
  lower_back_pain: number | null;
  load_score: number;
  load_label: string;
  compound_score: number;
  intensity_score: number | null;
  back_stress_score: number;
};

export type ExerciseStats = {
  exercise_id: number;
  name: string;
  total_volume: number;
  total_volume_kg: number;
  bodyweight_reps: number;
  duration_seconds: number;
  distance_m: number;
  weighted_reps: number;
  total_reps: number;
  total_sets: number;
  best_e1rm: number | null;
  best_set: {
    weight: number;
    reps: number;
    workout_id: number;
    date: string;
  } | null;
};

export type ExerciseStrengthPoint = {
  workout_id: number;
  date: string;
  e1rm: number;
  rolling_best: number;
  weight: number;
  reps: number;
  is_pr: boolean;
};

export type ExerciseStrengthProgress = {
  exercise_id: number;
  name: string;
  points: ExerciseStrengthPoint[];
};

export type ExerciseRepWeightPoint = {
  workout_id: number;
  date: string;
  weight: number;
  rolling_best: number;
  is_pr: boolean;
};

export type ExerciseRepTargetProgress = {
  reps: number;
  points: ExerciseRepWeightPoint[];
};

export type ExerciseRepProgress = {
  exercise_id: number;
  name: string;
  rep_targets: ExerciseRepTargetProgress[];
};

export type StatsSummary = {
  workout_count: number;
  total_volume: number;
  total_volume_kg: number;
  bodyweight_reps: number;
  duration_seconds: number;
  distance_m: number;
  weighted_reps: number;
  total_reps: number;
  total_sets: number;
  avg_intensity: number | null;
  avg_kg_per_rep: number | null;
  avg_rpe: number | null;
  avg_back_pain: number | null;
  total_load_score: number;
  avg_load_score: number | null;
  total_compound_score: number;
  avg_compound_score: number | null;
  total_back_stress_score: number;
  avg_back_stress_score: number | null;
  avg_relative_intensity: number | null;
};

export type DataQualityWarning = {
  key: string;
  severity: "info" | "watch" | "risk" | string;
  title: string;
  message: string;
  count?: number | null;
  workout_id?: number | null;
};

export type StatsSparkbars = {
  volume: string;
  volume_kg: string;
  bodyweight_reps: string;
  intensity: string;
  rpe: string;
  back: string;
  load: string;
  compound: string;
  back_stress: string;
};

export type StatsCharts = {
  sparkbars: StatsSparkbars;
};

export type MetricStatus = "good" | "watch" | "bad" | "neutral" | "info";

export type MetricZone = {
  from_value: number;
  to_value: number;
  status: MetricStatus;
  label: string;
};

export type TrainingLoadPoint = {
  date: string;
  load: number;
  atl: number;
  ctl: number;
  tsb: number;
  ac_ratio: number | null;
  atl_percent: number | null;
  ctl_percent: number | null;
};

export type TrainingLoadMetric = {
  key: string;
  label: string;
  description: string;
  value: number | null;
  formatted: string;
  status: MetricStatus;
  percent: number | null;
  min: number;
  max: number;
  zones: MetricZone[];
};

export type TrainingLoadSummary = {
  latest_date: string | null;
  daily_load: Array<{ date: string; load: number }>;
  series: TrainingLoadPoint[];
  weekly_load: number | null;
  weekly_mean: number | null;
  weekly_std: number | null;
  monotony: number | null;
  strain: number | null;
  atl_reference: number | null;
  ctl_reference: number | null;
  metrics: TrainingLoadMetric[];
};

export type ExerciseWeeklyWorkloadPoint = {
  week_start: string;
  sets: number;
  reps: number;
  volume: number;
  volume_kg: number;
  bodyweight_reps: number;
  duration_seconds: number;
  distance_m: number;
  workouts: number;
};

export type ExerciseWeeklyWorkload = {
  exercise_id: number;
  name: string;
  weeks: ExerciseWeeklyWorkloadPoint[];
};

export type StatsResponse = {
  limit: number | "all";
  stats: {
    summary: StatsSummary;
    workouts: StatsWorkout[];
    exercise_stats: ExerciseStats[];
    exercise_progress: ExerciseStrengthProgress[];
    exercise_rep_progress: ExerciseRepProgress[];
    exercise_weekly_workload: ExerciseWeeklyWorkload[];
    data_quality_warnings: DataQualityWarning[];
    training_load: TrainingLoadSummary;
  };
  training_load: TrainingLoadSummary;
  charts: StatsCharts;
};

export type ExerciseStatsSet = {
  id: number;
  workout_exercise_id: number;
  set_number: number;
  weight: number;
  reps: number;
  created_at: string;
  volume?: number;
  e1rm?: number | null;
};

export type ExerciseStatsBestSet = ExerciseStatsSet & {
  workout_id?: number;
  date?: string;
  volume: number;
  e1rm: number | null;
};

export type ExerciseStatsHistoryEntry = {
  workout_id: number;
  date: string;
  created_at: string;
  workout_exercise_ids: number[];
  sets: ExerciseStatsSet[];
  total_volume: number;
  total_volume_kg: number;
  total_reps: number;
  total_sets: number;
  bodyweight_reps: number;
  duration_seconds: number;
  distance_m: number;
  weighted_reps: number;
  avg_kg_per_rep: number | null;
  avg_intensity: number | null;
  measurement_type: ExerciseMeasurementType;
  reps_unit: string;
  best_weight: number | null;
  best_reps: number | null;
  best_e1rm: number | null;
  rolling_best_e1rm: number | null;
  best_set: ExerciseStatsBestSet | null;
  pr_flags: string[];
};

export type ExerciseStatsSummary = {
  workout_count: number;
  total_volume: number;
  total_volume_kg: number;
  total_reps: number;
  total_sets: number;
  bodyweight_reps: number;
  duration_seconds: number;
  distance_m: number;
  weighted_reps: number;
  avg_kg_per_rep: number | null;
  avg_intensity: number | null;
  best_weight: number | null;
  best_reps: number | null;
  best_e1rm: number | null;
  best_set: ExerciseStatsBestSet | null;
  pr_count: number;
  first_workout_at: string | null;
  latest_workout_at: string | null;
};

export type ExerciseStatsTrendSeries = {
  points: string;
  area_points: string;
  markers: Array<{
    x: number;
    y: number;
    value: number;
    date: string;
    workout_id: number;
  }>;
  max_value: number | null;
};

export type ExerciseStatsResponse = {
  limit: number | "all";
  exercise: {
    id: number;
    name: string;
    is_active: boolean;
    sort_order: number;
    profile_key: string;
    measurement_type: ExerciseMeasurementType;
    reps_unit: string;
  };
  profile: ExerciseProfile;
  summary: ExerciseStatsSummary;
  latest: ExerciseStatsHistoryEntry | null;
  history: ExerciseStatsHistoryEntry[];
  per_workout_sets: Array<{
    workout_id: number;
    date: string;
    sets: ExerciseStatsSet[];
  }>;
  trend: {
    volume: ExerciseStatsTrendSeries;
    volume_kg: ExerciseStatsTrendSeries;
    bodyweight_reps: ExerciseStatsTrendSeries;
    duration_seconds: ExerciseStatsTrendSeries;
    distance_m: ExerciseStatsTrendSeries;
    best_e1rm: ExerciseStatsTrendSeries;
    reps: ExerciseStatsTrendSeries;
  };
  strength_progress: ExerciseStrengthProgress;
  source_workout_ids: number[];
};
