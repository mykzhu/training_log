import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type { ReactNode } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useNavigate, useSearchParams } from "react-router-dom";

import { getExerciseStats } from "../api/exerciseStats";
import type {
  ExerciseStatsHistoryEntry,
  ExerciseStatsResponse,
  ExerciseStatsSet,
} from "../api/types";

const chartColors = {
  blue: "#0a84ff",
  green: "#30d158",
  orange: "#ff9f0a",
  purple: "#af52de",
  muted: "#999999",
  grid: "#2e2e2e",
  card: "#171717",
  text: "#f2f2f2",
};

type StatsLimit = 10 | 30 | 90 | "all";

const statsLimitOptions: Array<{ value: StatsLimit; label: string }> = [
  { value: 10, label: "10" },
  { value: 30, label: "30" },
  { value: 90, label: "90" },
  { value: "all", label: "All" },
];

type TrendPoint = {
  id: number;
  date: string;
  volume: number;
  bestE1rm: number | null;
  rollingBest: number | null;
  reps: number;
  sets: number;
};

type ChartClickState = {
  activePayload?: Array<{
    payload?: {
      id?: unknown;
    };
  }>;
};

function parseStatsLimit(value: string | null): StatsLimit {
  if (value === "10" || value === "30" || value === "90") {
    return Number(value) as StatsLimit;
  }

  if (value === "all") {
    return "all";
  }

  return 30;
}

function exerciseStatsLimitPath(exerciseId: number, limit: StatsLimit) {
  return `/exercises/${exerciseId}/stats?limit=${limit}`;
}

function formatNumber(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  return Number(value).toFixed(digits);
}

function formatKg(value: number | null | undefined, digits = 0) {
  return `${formatNumber(value, digits)} kg`;
}

function formatSet(set: ExerciseStatsSet) {
  return `${formatNumber(set.weight, 1)} kg x ${set.reps}`;
}

function workoutIdFromChartClick(state: unknown) {
  const payload = (state as ChartClickState | null)?.activePayload?.[0]?.payload;
  const id = payload?.id;
  return typeof id === "number" && Number.isFinite(id) ? id : null;
}

function commonTooltipProps() {
  return {
    contentStyle: {
      background: chartColors.card,
      border: `1px solid ${chartColors.grid}`,
      borderRadius: 14,
      color: chartColors.text,
    },
    labelStyle: {
      color: chartColors.text,
      fontWeight: 700,
    },
    formatter: (value: unknown, name: unknown): [ReactNode, string] => {
      const labels: Record<string, string> = {
        volume: "Volume",
        bestE1rm: "Best e1RM",
        rollingBest: "Rolling best",
        reps: "Reps",
        sets: "Sets",
      };
      const key = String(name);
      const numericValue =
        typeof value === "number" ? formatNumber(value, 1) : String(value);

      return [numericValue, labels[key] ?? key];
    },
  };
}


function SummaryCard({
  label,
  subvalue,
  value,
}: {
  label: string;
  subvalue: string;
  value: string;
}) {
  return (
    <div className="dashboard-card">
      <div className="dashboard-label">{label}</div>
      <div className="dashboard-value">{value}</div>
      <div className="dashboard-subvalue">{subvalue}</div>
    </div>
  );
}

function SetChips({ sets }: { sets: ExerciseStatsSet[] }) {
  if (sets.length === 0) {
    return <span className="muted">No sets</span>;
  }

  return (
    <div className="exercise-set-list">
      {sets.map((set) => (
        <span className="exercise-set-chip" key={set.id}>
          {formatSet(set)}
        </span>
      ))}
    </div>
  );
}

function PrFlags({ flags }: { flags: string[] }) {
  if (flags.length === 0) {
    return <span className="muted">None</span>;
  }

  return (
    <div className="exercise-pr-list">
      {flags.map((flag) => (
        <span className="status-badge metric-orange" key={flag}>
          {flag}
        </span>
      ))}
    </div>
  );
}

function buildTrendData(history: ExerciseStatsHistoryEntry[]): TrendPoint[] {
  return history.map((entry) => ({
    id: entry.workout_id,
    date: entry.date,
    volume: entry.total_volume,
    bestE1rm: entry.best_e1rm,
    rollingBest: entry.rolling_best_e1rm,
    reps: entry.total_reps,
    sets: entry.total_sets,
  }));
}

export default function ExerciseStatsPage({ exerciseId }: { exerciseId: number }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const statsLimit = parseStatsLimit(searchParams.get("limit"));
  const {
    data: stats,
    error: statsQueryError,
    isLoading,
  } = useQuery<ExerciseStatsResponse>({
    queryKey: ["exercise-stats", exerciseId, statsLimit],
    queryFn: () => getExerciseStats(exerciseId, statsLimit),
  });
  const error = statsQueryError instanceof Error
    ? statsQueryError.message
    : statsQueryError
      ? "Failed to load."
      : null;

  function selectStatsLimit(limit: StatsLimit) {
    navigate(exerciseStatsLimitPath(exerciseId, limit));
  }

  function navigateToWorkout(workoutId: number) {
    navigate(`/workouts/${workoutId}`);
  }

  function openWorkoutFromChart(state: unknown) {
    const workoutId = workoutIdFromChartClick(state);
    if (workoutId !== null) {
      navigateToWorkout(workoutId);
    }
  }

  const trendData = useMemo(
    () => buildTrendData(stats?.history ?? []),
    [stats],
  );

  return (
    <section className="page-stack exercise-stats-page">
      <section className="stats-toolbar" aria-label="Stats range">
        <span className="stats-range-label">Last</span>
        <div className="stats-range-control">
          {statsLimitOptions.map((option) => (
            <button
              aria-pressed={statsLimit === option.value}
              className={
                statsLimit === option.value
                  ? "stats-range-button stats-range-button-active"
                  : "stats-range-button"
              }
              key={option.value}
              onClick={() => selectStatsLimit(option.value)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>

      {error && <div className="error-banner">{error}</div>}
      {isLoading && <section className="panel">Loading</section>}

      {stats && (
        <>
          <section className="panel exercise-stats-hero">
            <div className="exercise-stats-title-row">
              <div>
                <p className="eyebrow">{stats.profile.label}</p>
                <h2>{stats.exercise.name}</h2>
              </div>

              {!stats.exercise.is_active && (
                <span className="status-badge metric-yellow">Inactive</span>
              )}
            </div>

            <div className="exercise-stats-meta">
              <span>{stats.profile.category}</span>
              <span>{stats.summary.workout_count} workouts</span>
              <span>{stats.summary.total_sets} sets</span>
              <span>{stats.summary.pr_count} PR flags</span>
            </div>

            {stats.source_workout_ids.length > 0 && (
              <div className="exercise-source-links" aria-label="Source workouts">
                {stats.source_workout_ids.slice(-6).map((workoutId) => (
                  <button
                    className="strength-table-link strength-table-date"
                    key={workoutId}
                    onClick={() => navigateToWorkout(workoutId)}
                    type="button"
                  >
                    Workout #{workoutId}
                  </button>
                ))}
              </div>
            )}
          </section>

          {stats.history.length === 0 ? (
            <div className="empty">No history for this exercise yet.</div>
          ) : (
            <>
              <section className="dashboard-grid">
                <SummaryCard
                  label="Volume"
                  subvalue={`${formatNumber(stats.summary.total_reps)} reps`}
                  value={formatKg(stats.summary.total_volume)}
                />
                <SummaryCard
                  label="Best e1RM"
                  subvalue={
                    stats.summary.best_set
                      ? `${formatSet(stats.summary.best_set)}`
                      : "No eligible set"
                  }
                  value={formatKg(stats.summary.best_e1rm, 1)}
                />
                <SummaryCard
                  label="Best weight"
                  subvalue={`${formatNumber(stats.summary.best_reps)} max reps`}
                  value={formatKg(stats.summary.best_weight, 1)}
                />
                <SummaryCard
                  label="Latest"
                  subvalue={stats.latest?.date ?? "-"}
                  value={
                    stats.latest?.best_e1rm === null
                      ? formatKg(stats.latest?.total_volume)
                      : formatKg(stats.latest?.best_e1rm, 1)
                  }
                />
              </section>

              <section className="chart-card chart-card-wide">
                <div className="chart-heading">
                  <h2>Trend</h2>
                  <p className="muted">Volume, e1RM, and rolling best by workout</p>
                </div>

                <div className="chart-frame">
                  <ResponsiveContainer height={300} width="100%">
                    <LineChart
                      className="clickable-chart"
                      data={trendData}
                      margin={{ top: 18, right: 18, left: 0, bottom: 0 }}
                      onClick={openWorkoutFromChart}
                    >
                      <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                      <XAxis dataKey="date" stroke={chartColors.muted} tick={{ fontSize: 12 }} />
                      <YAxis stroke={chartColors.muted} tick={{ fontSize: 12 }} />
                      <Tooltip {...commonTooltipProps()} />
                      <Legend wrapperStyle={{ color: chartColors.muted }} />
                      <Line
                        activeDot={{ r: 5 }}
                        dataKey="volume"
                        dot={{ r: 3 }}
                        name="Volume"
                        stroke={chartColors.blue}
                        strokeWidth={2}
                        type="monotone"
                      />
                      <Line
                        activeDot={{ r: 5 }}
                        connectNulls={false}
                        dataKey="bestE1rm"
                        dot={{ r: 3 }}
                        name="Best e1RM"
                        stroke={chartColors.green}
                        strokeWidth={2}
                        type="monotone"
                      />
                      <Line
                        activeDot={{ r: 5 }}
                        connectNulls={false}
                        dataKey="rollingBest"
                        dot={{ r: 3 }}
                        name="Rolling best"
                        stroke={chartColors.orange}
                        strokeDasharray="5 5"
                        strokeWidth={2}
                        type="monotone"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </section>

              <section className="chart-card chart-card-wide">
                <div className="chart-heading">
                  <h2>Workout history</h2>
                  <p className="muted">Chronological source workouts and set results</p>
                </div>

                <div className="strength-table-scroll">
                  <table className="strength-table exercise-history-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Best e1RM</th>
                        <th>Volume</th>
                        <th>Sets</th>
                        <th>PRs</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.history.map((entry) => (
                        <tr key={entry.workout_id}>
                          <td>
                            <button
                              className="strength-table-link strength-table-date"
                              onClick={() => navigateToWorkout(entry.workout_id)}
                              type="button"
                            >
                              {entry.date}
                            </button>
                          </td>
                          <td className="strength-table-value">
                            {formatKg(entry.best_e1rm, 1)}
                          </td>
                          <td>{formatKg(entry.total_volume)}</td>
                          <td>
                            <SetChips sets={entry.sets} />
                          </td>
                          <td>
                            <PrFlags flags={entry.pr_flags} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
        </>
      )}
    </section>
  );
}