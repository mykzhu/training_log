export type SetEntry = {
  id: number;
  workout_exercise_id?: number;
  set_number: number;
  weight: number;
  reps: number;
  created_at: string;
};

export type CurrentWorkoutExercise = {
  draft_exercise_id: number;
  exercise_id: number;
  exercise_name: string;
  profile_key: string;
  position: number;
  sets: SetEntry[];
  total_sets: number;
  total_reps: number;
  total_volume: number;
  default_weight: number;
  default_reps: number;
  configured_weights: number[];
};

export type WorkoutExercise = {
  workout_exercise_id: number;
  exercise_id: number;
  exercise_name: string;
  profile_key: string;
  position: number;
  sets: SetEntry[];
  total_sets: number;
  total_reps: number;
  total_volume: number;
  default_weight: number;
  default_reps: number;
  configured_weights: number[];
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
  relative_load: {
    acute_to_baseline: number | null;
    acute_back_to_baseline: number | null;
    baseline_confidence: "low" | "medium" | "high";
  };
};

export type ExerciseRecommendation = {
  exercise_name: string;
  action: string;
  action_label: string;
  target: string;
  reason: string;
  gap_label: string;
  usual_gap_label: string;
  gap_status_label: string;
  progression_status: string;
  progression_label: string;
  progression_summary: string;
  e1rm_change_label: string;
  volume_change_label: string;
};

export type NextWorkoutRecommendation = {
  status: string;
  title: string;
  score: number | null;
  summary: string;
  reasons: string[];
  last_workout_id: number | null;
  last_workout_at?: string;
  exercise_recommendations: ExerciseRecommendation[];
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
  weights: number[];
};

export type ExerciseCreatePayload = {
  name: string;
  is_active?: boolean;
  profile_key?: string;
  weights?: number[];
};

export type ExerciseUpdatePayload = {
  name?: string;
  is_active?: boolean;
  profile_key?: string;
};

export type ExerciseProfile = {
  key: string;
  label: string;
  category: string;
};

export type StatsWorkout = {
  id: number;
  date: string;
  created_at: string;
  total_volume: number;
  total_reps: number;
  total_sets: number;
  avg_intensity: number | null;
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
  total_reps: number;
  total_sets: number;
  avg_intensity: number | null;
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

export type StatsSparkbars = {
  volume: string;
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

export type ExerciseWeeklyWorkloadPoint = {
  week_start: string;
  sets: number;
  reps: number;
  volume: number;
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
  };
  charts: StatsCharts;
};