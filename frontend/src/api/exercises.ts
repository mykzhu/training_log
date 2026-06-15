import { jsonBody, requestJson } from "./client";
import type { Exercise } from "./types";

export function getExercises() {
  return requestJson<{ exercises: Exercise[] }>("/api/v1/exercises");
}

export function createExercise(name: string) {
  return requestJson<{ exercise: Exercise; created: boolean }>(
    "/api/v1/exercises",
    {
      method: "POST",
      body: jsonBody({ name }),
    },
  );
}
