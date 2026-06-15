import { requestJson } from "./client";
import type { StatsResponse } from "./types";

export function getStats(limit: number | "all" = 30) {
  return requestJson<StatsResponse>(`/api/v1/stats?limit=${limit}`);
}
