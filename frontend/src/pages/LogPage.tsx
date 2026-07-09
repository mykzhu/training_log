import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getLogs } from "../api/logs";
import type { LogEntry } from "../api/types";

const levelOptions = ["", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
const limitOptions = [100, 500, 1000, 2000];

function formatLogTimestamp(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function LogEntryCard({ entry }: { entry: LogEntry }) {
  const tone = entry.level.toLowerCase();

  return (
    <article className={`log-entry log-entry-${tone}`}>
      <span className="log-time">{formatLogTimestamp(entry.timestamp)}</span>
      <span className={`log-level log-level-${tone}`}>{entry.level}</span>
      <span className="log-logger">{entry.logger}</span>
      <span className="log-message">{entry.message}</span>
      {entry.exception && (
        <details className="log-exception">
          <summary>Exception</summary>
          <pre>{entry.exception}</pre>
        </details>
      )}
    </article>
  );
}

export default function LogPage() {
  const [limit, setLimit] = useState(500);
  const [level, setLevel] = useState("");
  const [loggerFilter, setLoggerFilter] = useState("");
  const [query, setQuery] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);

  const logsQuery = useQuery({
    queryKey: ["logs", limit, level, loggerFilter, query],
    queryFn: () =>
      getLogs({
        limit,
        level: level || undefined,
        logger: loggerFilter || undefined,
        query: query || undefined,
        order: "desc",
      }),
    refetchInterval: autoRefresh ? 5000 : false,
  });

  const logs = logsQuery.data;
  const hasFilters = Boolean(level || loggerFilter.trim() || query.trim());

  return (
    <section className="page-stack">
      <section className="panel log-summary-panel">
        <div>
          <h2>Latest logs</h2>
          <p className="muted">
            {logs
              ? hasFilters
                ? `${logs.count} shown, ${logs.filtered_available} matching, ${logs.total_available} total${
                    logs.truncated ? ", truncated by limit" : ""
                  }`
                : `${logs.count} shown, ${logs.total_available} available${
                    logs.truncated ? ", truncated by limit" : ""
                  }`
              : "Loading logs"}
          </p>
        </div>
        <div className="log-summary-actions">
          <label className="log-auto-refresh">
            <input
              checked={autoRefresh}
              onChange={(event) => setAutoRefresh(event.target.checked)}
              type="checkbox"
            />
            Auto-refresh
          </label>
          <button
            className="secondary-button compact-action"
            disabled={logsQuery.isFetching}
            onClick={() => logsQuery.refetch()}
            type="button"
          >
            Refresh
          </button>
        </div>
      </section>

      <section className="panel log-controls">
        <label>
          Level
          <select
            onChange={(event) => setLevel(event.target.value)}
            value={level}
          >
            {levelOptions.map((option) => (
              <option key={option || "all"} value={option}>
                {option || "All"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Logger
          <input
            onChange={(event) => setLoggerFilter(event.target.value)}
            placeholder="training_log"
            value={loggerFilter}
          />
        </label>
        <label>
          Search
          <input
            onChange={(event) => setQuery(event.target.value)}
            placeholder="request.end"
            value={query}
          />
        </label>
        <label>
          Limit
          <select
            onChange={(event) => setLimit(Number(event.target.value))}
            value={limit}
          >
            {limitOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </section>

      {logsQuery.isError && (
        <div className="error-banner">
          Could not load logs:{" "}
          {logsQuery.error instanceof Error
            ? logsQuery.error.message
            : "Unknown error"}
        </div>
      )}

      {logsQuery.isLoading && <section className="panel muted">Loading logs...</section>}

      {logs && logs.entries.length === 0 && (
        <section className="panel">
          <p>{hasFilters ? "No logs match current filters." : "No logs yet."}</p>
        </section>
      )}

      {logs && logs.entries.length > 0 && (
        <section className="log-list" aria-label="Application logs">
          {logs.entries.map((entry) => (
            <LogEntryCard entry={entry} key={entry.id} />
          ))}
        </section>
      )}
    </section>
  );
}
