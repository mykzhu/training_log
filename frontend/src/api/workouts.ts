import { requestJson } from "./client";
import type { WorkoutDetail, WorkoutSummary } from "./types";

export function getWorkouts(limit = 30) {
  return requestJson<{ limit: number; workouts: WorkoutSummary[] }>(
    `/api/v1/workouts?limit=${limit}`,
  );
}

export function getWorkout(workoutId: number) {
  return requestJson<WorkoutDetail>(`/api/v1/workouts/${workoutId}`);
}
