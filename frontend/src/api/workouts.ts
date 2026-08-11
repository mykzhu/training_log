import { jsonBody, requestJson } from "./client";
import type {
  ExerciseFeedbackUpdate,
  WorkoutDetail,
  WorkoutSummary,
} from "./types";

export function getWorkouts(limit = 30) {
  return requestJson<{ limit: number; workouts: WorkoutSummary[] }>(
    `/api/v1/workouts?limit=${limit}`,
  );
}

export function getWorkout(workoutId: number) {
  return requestJson<WorkoutDetail>(`/api/v1/workouts/${workoutId}`);
}

export function updateWorkout(
  workoutId: number,
  payload: {
    created_at?: string;
    session_rpe?: number | null;
    lower_back_pain?: number | null;
  },
) {
  return requestJson<WorkoutDetail>(`/api/v1/workouts/${workoutId}`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function deleteWorkout(workoutId: number) {
  return requestJson<{ deleted: boolean; workout_id: number }>(
    `/api/v1/workouts/${workoutId}`,
    { method: "DELETE" },
  );
}

export function addWorkoutExercise(workoutId: number, exerciseId: number) {
  return requestJson<WorkoutDetail>(`/api/v1/workouts/${workoutId}/exercises`, {
    method: "POST",
    body: jsonBody({ exercise_id: exerciseId }),
  });
}

export function deleteWorkoutExercise(
  workoutId: number,
  workoutExerciseId: number,
) {
  return requestJson<WorkoutDetail>(
    `/api/v1/workouts/${workoutId}/exercises/${workoutExerciseId}`,
    { method: "DELETE" },
  );
}

export function addWorkoutExerciseSet(
  workoutExerciseId: number,
  payload: { weight: number; reps: number },
) {
  return requestJson<WorkoutDetail>(
    `/api/v1/workout-exercises/${workoutExerciseId}/sets`,
    {
      method: "POST",
      body: jsonBody(payload),
    },
  );
}

export function duplicateWorkoutExerciseSet(workoutExerciseId: number) {
  return requestJson<WorkoutDetail>(
    `/api/v1/workout-exercises/${workoutExerciseId}/sets/duplicate`,
    { method: "POST" },
  );
}

export function updateWorkoutSet(
  setId: number,
  payload: { weight?: number; reps?: number },
) {
  return requestJson<WorkoutDetail>(`/api/v1/sets/${setId}`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function deleteWorkoutSet(setId: number) {
  return requestJson<WorkoutDetail>(`/api/v1/sets/${setId}`, {
    method: "DELETE",
  });
}

export function updateWorkoutExerciseFeedback(
  workoutId: number,
  workoutExerciseId: number,
  payload: ExerciseFeedbackUpdate,
) {
  return requestJson<WorkoutDetail>(
    `/api/v1/workouts/${workoutId}/exercises/${workoutExerciseId}/feedback`,
    {
      method: "PATCH",
      body: jsonBody(payload),
    },
  );
}
