import { jsonBody, requestJson } from "./client";
import type {
  Exercise,
  ExerciseCreatePayload,
  DeletedExercise,
  ExerciseProfile,
  ExerciseProfileCreatePayload,
  ExerciseProfileUpdatePayload,
  ExerciseUpdatePayload,
  ExerciseUsage,
} from "./types";

export type GetExercisesOptions = {
  includeInactive?: boolean;
};

export function getExercises(options: GetExercisesOptions = {}) {
  const params = new URLSearchParams();
  if (options.includeInactive) {
    params.set("include_inactive", "true");
  }
  const query = params.toString();

  return requestJson<{ exercises: Exercise[] }>(
    `/api/v1/exercises${query ? `?${query}` : ""}`,
  );
}

export function createExercise(payload: ExerciseCreatePayload) {
  return requestJson<{ exercise: Exercise; created: boolean }>(
    "/api/v1/exercises",
    {
      method: "POST",
      body: jsonBody(payload),
    },
  );
}

export function updateExercise(
  exerciseId: number,
  payload: ExerciseUpdatePayload,
) {
  return requestJson<{ exercise: Exercise }>(`/api/v1/exercises/${exerciseId}`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function deleteExercise(exerciseId: number) {
  return requestJson<{
    deleted: boolean;
    exercise_id: number;
    exercise?: DeletedExercise | null;
    usage?: ExerciseUsage | null;
  }>(`/api/v1/exercises/${exerciseId}`, {
    method: "DELETE",
  });
}

export function replaceExerciseWeights(exerciseId: number, weights: number[]) {
  return requestJson<{ exercise_id: number; weights: number[] }>(
    `/api/v1/exercises/${exerciseId}/weights`,
    {
      method: "PUT",
      body: jsonBody({ weights }),
    },
  );
}

export function reorderExercises(exerciseIds: number[]) {
  return requestJson<{ exercises: Exercise[] }>("/api/v1/exercises/order", {
    method: "PUT",
    body: jsonBody({ exercise_ids: exerciseIds }),
  });
}

export function getExerciseProfiles() {
  return requestJson<{ profiles: ExerciseProfile[] }>("/api/v1/exercise-profiles");
}

export function createExerciseProfile(payload: ExerciseProfileCreatePayload) {
  return requestJson<{ profile: ExerciseProfile; created: boolean }>(
    "/api/v1/exercise-profiles",
    {
      method: "POST",
      body: jsonBody(payload),
    },
  );
}

export function updateExerciseProfile(
  profileKey: string,
  payload: ExerciseProfileUpdatePayload,
) {
  return requestJson<{ profile: ExerciseProfile }>(
    `/api/v1/exercise-profiles/${profileKey}`,
    {
      method: "PATCH",
      body: jsonBody(payload),
    },
  );
}

export function deleteExerciseProfile(profileKey: string) {
  return requestJson<{
    deleted: boolean;
    profile_key: string;
    profile?: ExerciseProfile | null;
  }>(`/api/v1/exercise-profiles/${encodeURIComponent(profileKey)}`, {
    method: "DELETE",
  });
}
