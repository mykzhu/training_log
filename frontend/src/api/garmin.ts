import { jsonBody, requestJson } from "./client";
import type {
  GarminDailyMetricsResponse,
  GarminLoginResponse,
  GarminStatsRange,
  GarminStatsResponse,
  GarminStatus,
  GarminSyncResponse,
} from "./types";

const base = "/api/v1/garmin";

export function getGarminStatus() {
  return requestJson<GarminStatus>(`${base}/status`);
}

export function loginGarmin(username: string, password: string) {
  return requestJson<GarminLoginResponse>(`${base}/login`, {
    method: "POST",
    body: jsonBody({ username, password }),
  });
}

export function submitGarminMfa(mfaToken: string, code: string) {
  return requestJson<GarminLoginResponse>(`${base}/mfa`, {
    method: "POST",
    body: jsonBody({ mfa_token: mfaToken, code }),
  });
}

export function disconnectGarmin() {
  return requestJson<GarminStatus>(`${base}/disconnect`, { method: "POST" });
}

export function syncGarmin(days?: number) {
  return requestJson<GarminSyncResponse>(`${base}/sync`, {
    method: "POST",
    body: days === undefined ? undefined : jsonBody({ days }),
  });
}

export function getGarminDailyMetrics(days = 35) {
  return requestJson<GarminDailyMetricsResponse>(
    `${base}/daily?days=${encodeURIComponent(String(days))}`,
  );
}

export function getGarminStats(range: GarminStatsRange = "90") {
  return requestJson<GarminStatsResponse>(
    `${base}/stats?range=${encodeURIComponent(range)}`,
  );
}
