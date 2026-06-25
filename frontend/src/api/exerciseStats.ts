import { requestJson } from "./client";
import type { ExerciseStatsResponse } from "./types";

export function getExerciseStats(
  exerciseId: number,
  limit: number | "all" = 30,
) {
  return requestJson<ExerciseStatsResponse>(
    `/api/v1/exercises/${exerciseId}/stats?limit=${limit}`,
  );
}