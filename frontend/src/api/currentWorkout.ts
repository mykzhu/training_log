import { jsonBody, requestJson } from "./client";
import type { CurrentWorkout, ExerciseFeedbackUpdate } from "./types";

const base = "/api/v1/current-workout";

export function getCurrentWorkout() {
  return requestJson<CurrentWorkout>(base);
}

export function startCurrentWorkout() {
  return requestJson<CurrentWorkout>(`${base}/start`, { method: "POST" });
}

export function clearCurrentWorkout() {
  return requestJson<CurrentWorkout>(base, { method: "DELETE" });
}

export function updateCurrentWorkoutMetadata(payload: {
  session_rpe: number | null;
  lower_back_pain: number | null;
}) {
  return requestJson<CurrentWorkout>(`${base}/metadata`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function addCurrentWorkoutExercise(exerciseId: number) {
  return requestJson<CurrentWorkout>(`${base}/exercises`, {
    method: "POST",
    body: jsonBody({ exercise_id: exerciseId }),
  });
}

export function deleteCurrentWorkoutExercise(draftExerciseId: number) {
  return requestJson<CurrentWorkout>(`${base}/exercises/${draftExerciseId}`, {
    method: "DELETE",
  });
}

export function addCurrentWorkoutSet(
  draftExerciseId: number,
  payload: { weight: number; reps: number },
) {
  return requestJson<CurrentWorkout>(
    `${base}/exercises/${draftExerciseId}/sets`,
    {
      method: "POST",
      body: jsonBody(payload),
    },
  );
}

export function duplicateCurrentWorkoutSet(draftExerciseId: number) {
  return requestJson<CurrentWorkout>(
    `${base}/exercises/${draftExerciseId}/sets/duplicate`,
    { method: "POST" },
  );
}

export function updateCurrentWorkoutSet(
  draftSetId: number,
  payload: { weight?: number; reps?: number },
) {
  return requestJson<CurrentWorkout>(`${base}/sets/${draftSetId}`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function deleteCurrentWorkoutSet(draftSetId: number) {
  return requestJson<CurrentWorkout>(`${base}/sets/${draftSetId}`, {
    method: "DELETE",
  });
}

export function updateCurrentWorkoutExerciseFeedback(
  draftExerciseId: number,
  payload: ExerciseFeedbackUpdate,
) {
  return requestJson<CurrentWorkout>(
    `${base}/exercises/${draftExerciseId}/feedback`,
    {
      method: "PATCH",
      body: jsonBody(payload),
    },
  );
}

export function finishCurrentWorkout() {
  return requestJson<{ workout_id: number; current_workout: CurrentWorkout }>(
    `${base}/finish`,
    { method: "POST" },
  );
}
