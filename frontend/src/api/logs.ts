import { requestJson } from "./client";
import type { LogsResponse } from "./types";

export type GetLogsOptions = {
  limit?: number;
  level?: string;
  logger?: string;
  query?: string;
  order?: "asc" | "desc";
};

export function getLogs(options: GetLogsOptions = {}) {
  const params = new URLSearchParams();

  if (options.limit) {
    params.set("limit", String(options.limit));
  }
  if (options.level) {
    params.set("level", options.level);
  }
  if (options.logger) {
    params.set("logger", options.logger);
  }
  if (options.query) {
    params.set("query", options.query);
  }
  if (options.order) {
    params.set("order", options.order);
  }

  const query = params.toString();
  return requestJson<LogsResponse>(`/api/v1/logs${query ? `?${query}` : ""}`);
}
