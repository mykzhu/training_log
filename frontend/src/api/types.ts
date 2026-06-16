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
  position: number;
  sets: SetEntry[];
  total_sets: number;
  total_reps: number;
  total_volume: number;
  default_weight: number;
  default_reps: number;
};

export type WorkoutExercise = {
  workout_exercise_id: number;
  exercise_id: number;
  exercise_name: string;
  position: number;
  sets: SetEntry[];
  total_sets: number;
  total_reps: number;
  total_volume: number;
  default_weight: number;
  default_reps: number;
};

export type LoadMetrics = {
  load_score: number;
  load_label: string;
  compound_score: number;
  intensity_score: number | null;
  back_stress_score: number;
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

export type StatsResponse = {
  limit: number | "all";
  stats: {
    summary: StatsSummary;
    workouts: StatsWorkout[];
    exercise_stats: ExerciseStats[];
  };
  charts: Record<string, unknown>;
};
