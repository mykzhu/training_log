import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getStats } from "../api/stats";
import type { ExerciseStats, StatsResponse, StatsWorkout } from "../api/types";

const chartColors = {
  blue: "#0a84ff",
  green: "#30d158",
  orange: "#ff9f0a",
  red: "#ff453a",
  purple: "#af52de",
  muted: "#999999",
  grid: "#2e2e2e",
  card: "#171717",
  text: "#f2f2f2",
};

type LoadCalendarDay = {
  date: string;
  day: number;
  has_workout: boolean;
  count: number;
  value: number | null;
  workout_id: number | null;
};

type LoadCalendarWeek = {
  month_label: string;
  days: LoadCalendarDay[];
};

type LoadCalendar = {
  weeks: LoadCalendarWeek[];
};

type LoadCalendarLevel =
  | "rest"
  | "light"
  | "medium"
  | "hard"
  | "very-hard";

function loadCalendarLevel(
  day: LoadCalendarDay,
): LoadCalendarLevel {
  if (!day.has_workout || day.value === null) {
    return "rest";
  }

  if (day.value < 4) {
    return "light";
  }

  if (day.value < 8) {
    return "medium";
  }

  if (day.value < 14) {
    return "hard";
  }

  return "very-hard";
}

function loadCalendarDescription(day: LoadCalendarDay) {
  if (!day.has_workout) {
    return `${day.date} · rest day`;
  }

  const score =
    day.value === null
      ? "unknown load"
      : `load ${formatNumber(day.value, 1)}`;

  const workoutText =
    day.count === 1
      ? "1 workout"
      : `${day.count} workouts`;

  return `${day.date} · ${score} · ${workoutText}`;
}

type ChartPoint = {
  id: number;
  date: string;
  volume: number;
  volumePerRep: number | null;
  relativeIntensity: number | null;
  load: number;
  compound: number;
  backStress: number;
  rpe: number | null;
  backPain: number | null;
};

type StatsLimit = 10 | 30 | 90 | "all";

const statsLimitOptions: Array<{ value: StatsLimit; label: string }> = [
  { value: 10, label: "10" },
  { value: 30, label: "30" },
  { value: 90, label: "90" },
  { value: "all", label: "All" },
];

function parseStatsLimit(value: string | null): StatsLimit {
  if (value === "10" || value === "30" || value === "90") {
    return Number(value) as StatsLimit;
  }

  if (value === "all") {
    return "all";
  }

  return 30;
}

function readStatsLimitFromUrl() {
  return parseStatsLimit(new URLSearchParams(window.location.search).get("limit"));
}

function statsBasePath() {
  const exerciseStatsMatch = window.location.pathname.match(/^\/exercises\/\d+\/stats/);
  return exerciseStatsMatch ? exerciseStatsMatch[0] : "/stats";
}

function statsLimitPath(limit: StatsLimit) {
  return `${statsBasePath()}?limit=${limit}`;
}

type WorkoutChartClickState = {
  activePayload?: Array<{
    payload?: {
      id?: unknown;
    };
  }>;
};

type ExerciseBarClickData = {
  exercise_id?: unknown;
  payload?: {
    exercise_id?: unknown;
  };
};

function numericId(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function workoutIdFromChartClick(state: unknown) {
  const payload = (state as WorkoutChartClickState | null)?.activePayload?.[0]?.payload;
  return numericId(payload?.id);
}

function exerciseIdFromBarClick(data: unknown) {
  const barData = data as ExerciseBarClickData | null;
  return numericId(barData?.exercise_id) ?? numericId(barData?.payload?.exercise_id);
}

function formatNumber(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return Number(value).toFixed(digits);
}

function formatKg(value: number | null | undefined) {
  return `${formatNumber(value)} kg`;
}

function buildWorkoutData(workouts: StatsWorkout[]): ChartPoint[] {
  return workouts.map((workout) => ({
    id: workout.id,
    date: workout.date,
    volume: workout.total_volume,
    volumePerRep: workout.avg_intensity,
    relativeIntensity: workout.intensity_score,
    load: workout.load_score,
    compound: workout.compound_score,
    backStress: workout.back_stress_score,
    rpe: workout.session_rpe,
    backPain: workout.lower_back_pain,
  }));
}

function chartTooltipFormatter(value: unknown, name: unknown): [ReactNode, string] {
  const labels: Record<string, string> = {
    volume: "Volume",
    load: "Load",
    compound: "Compound",
    backStress: "Back stress",
    intensity: "Intensity",
    rpe: "RPE",
    backPain: "Back pain",
    total_volume: "Volume",
    best_e1rm: "Best e1RM",
  };
  const key = String(name);
  const numericValue = typeof value === "number" ? formatNumber(value, 1) : String(value);

  return [numericValue, labels[key] ?? key];
}

function EmptyStats() {
  return <div className="empty">No workout data yet.</div>;
}

type DashboardCardProps = {
  label: string;
  value: string;
  subvalue: string;
  spark?: string;
  color?: "blue" | "green" | "orange" | "red" | "purple";
  tone?: "green" | "yellow" | "orange" | "red";
};

function DashboardCard({
  color = "blue",
  label,
  spark,
  subvalue,
  tone,
  value,
}: DashboardCardProps) {
  return (
    <div className={tone ? `dashboard-card metric-${tone}` : "dashboard-card"}>
      <div className="dashboard-label">{label}</div>
      <div className="dashboard-value">{value}</div>
      <div className="dashboard-subvalue">{subvalue}</div>
      {spark && <div className={`dashboard-sparkbar ${color}`}>{spark}</div>}
    </div>
  );
}

type ChartInsightProps = {
  question: string;
  explanation: string;
  children?: ReactNode;
};

function ChartInsight({
  children,
  explanation,
  question,
}: ChartInsightProps) {
  return (
    <div className="chart-insight">
      <div className="chart-insight-heading">
        <strong>{question}</strong>
        <span>{explanation}</span>
      </div>

      {children}
    </div>
  );
}

type ChartCardProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  wide?: boolean;
};

function ChartCard({
  children,
  subtitle,
  title,
  wide = false,
}: ChartCardProps) {
  return (
    <section className={wide ? "chart-card chart-card-wide" : "chart-card"}>
      <div className="chart-heading">
        <h2>{title}</h2>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>

      <div className="chart-frame">{children}</div>
    </section>
  );
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
    formatter: chartTooltipFormatter,
  };
}

type MetricTone = "green" | "yellow" | "orange" | "red";

type SummaryMetricProps = {
  label: string;
  value: ReactNode;
  detail?: string;
  tone?: MetricTone;
};

function SummaryMetric({
  detail,
  label,
  tone,
  value,
}: SummaryMetricProps) {
  return (
    <div
      className={
        tone
          ? `stats-summary-metric metric-${tone}`
          : "stats-summary-metric"
      }
    >
      <strong>{value}</strong>
      <span>{label}</span>
      {detail && <small>{detail}</small>}
    </div>
  );
}

function rpeTone(value: number | null | undefined): MetricTone | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  if (value <= 4) {
    return "green";
  }
  if (value <= 6) {
    return "yellow";
  }
  if (value <= 8) {
    return "orange";
  }
  return "red";
}

function backPainTone(
  value: number | null | undefined,
): MetricTone | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  if (value <= 2) {
    return "green";
  }
  if (value <= 4) {
    return "yellow";
  }
  if (value <= 6) {
    return "orange";
  }
  return "red";
}

export default function StatsPage() {
  const [statsLimit, setStatsLimit] = useState<StatsLimit>(() => readStatsLimitFromUrl());
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function syncLimitFromUrl() {
      setStatsLimit(readStatsLimitFromUrl());
    }

    window.history.replaceState(null, "", statsLimitPath(readStatsLimitFromUrl()));
    window.addEventListener("popstate", syncLimitFromUrl);
    return () => window.removeEventListener("popstate", syncLimitFromUrl);
  }, []);

  useEffect(() => {
    let cancelled = false;

    setError(null);
    setStats(null);

    getStats(statsLimit)
      .then((response) => {
        if (!cancelled) {
          setStats(response);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "Failed to load.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [statsLimit]);

  function selectStatsLimit(limit: StatsLimit) {
    setStatsLimit(limit);
    window.history.pushState(null, "", statsLimitPath(limit));
  }

  function navigateToWorkout(workoutId: number) {
    window.history.pushState(null, "", `/workouts/${workoutId}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function navigateToExerciseStats(exerciseId: number) {
    window.history.pushState(null, "", `/exercises/${exerciseId}/stats?limit=${statsLimit}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function openWorkoutFromChart(state: unknown) {
    const workoutId = workoutIdFromChartClick(state);
    if (workoutId !== null) {
      navigateToWorkout(workoutId);
    }
  }

  function openExerciseFromBar(data: unknown) {
    const exerciseId = exerciseIdFromBarClick(data);
    if (exerciseId !== null) {
      navigateToExerciseStats(exerciseId);
    }
  }

  const workoutData = useMemo(
    () => buildWorkoutData(stats?.stats.workouts ?? []),
    [stats],
  );

  const topVolumePoint = useMemo(() => {
    if (workoutData.length === 0) {
      return null;
    }

    return workoutData.reduce((highest, workout) =>
      workout.volume > highest.volume ? workout : highest,
    );
  }, [workoutData]);

  const topVolumePerRepPoint = useMemo(() => {
    const validPoints = workoutData.filter(
      (
        point,
      ): point is ChartPoint & {
        volumePerRep: number;
      } =>
        point.volumePerRep !== null &&
        Number.isFinite(point.volumePerRep),
    );

    if (validPoints.length === 0) {
      return null;
    }

    return validPoints.reduce((highest, point) =>
      point.volumePerRep > highest.volumePerRep
        ? point
        : highest,
    );
  }, [workoutData]);

  const relativeIntensityDomain = useMemo<[number, number]>(() => {
    const values = workoutData
      .map((point) => point.relativeIntensity)
      .filter(
        (value): value is number =>
          value !== null && Number.isFinite(value),
      );

    if (values.length === 0) {
      return [0, 110];
    }

    /*
    * Include the 100% historical baseline, but avoid always displaying
    * the full 0–110 range. This makes small changes easier to see.
    */
    const minimum = Math.min(...values, 100);
    const maximum = Math.max(...values, 100);
    const span = Math.max(maximum - minimum, 5);
    const padding = Math.max(2, span * 0.12);

    return [
      Math.max(0, Math.floor(minimum - padding)),
      Math.ceil(maximum + padding),
    ];
  }, [workoutData]);

  const topExercises = useMemo(
    () => [...(stats?.stats.exercise_stats ?? [])]
      .sort((a, b) => b.total_volume - a.total_volume)
      .slice(0, 8),
    [stats],
  );

  const bestStrength = useMemo(
    () =>
      [...(stats?.stats.exercise_stats ?? [])]
        .filter(
          (
            exercise,
          ): exercise is ExerciseStats & {
            best_e1rm: number;
            best_set: NonNullable<ExerciseStats["best_set"]>;
          } =>
            exercise.best_e1rm !== null &&
            exercise.best_set !== null,
        )
        .sort((a, b) => b.best_e1rm - a.best_e1rm),
    [stats],
  );

  const summary = stats?.stats.summary;
  const sparkbars = stats?.charts.sparkbars;
  const workouts = stats?.stats.workouts ?? [];
  const workoutCount = summary?.workout_count ?? 0;

  const loadCalendar = (
    stats?.charts as {
      load_calendar?: LoadCalendar;
    } | undefined
  )?.load_calendar;

  const uniqueExerciseCount =
    stats?.stats.exercise_stats.length ?? 0;

  const setsPerWorkout =
    workoutCount > 0 && summary
      ? summary.total_sets / workoutCount
      : null;

  const repsPerWorkout =
    workoutCount > 0 && summary
      ? summary.total_reps / workoutCount
      : null;

  const rpeLoggedCount = workouts.filter(
    (workout) => workout.session_rpe !== null,
  ).length;

  const backPainLoggedCount = workouts.filter(
    (workout) => workout.lower_back_pain !== null,
  ).length;

  return (
    <section className="page-stack">
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
      {!stats && !error && <section className="panel">Loading</section>}
      {stats && workoutData.length === 0 && <EmptyStats />}

      {stats && summary && workoutData.length > 0 && (
        <>
          <section className="dashboard-grid">
            <DashboardCard
              color="blue"
              label="Workouts"
              spark={sparkbars?.load}
              subvalue={`${formatNumber(summary.total_sets)} sets · ${formatNumber(
                summary.total_reps,
              )} reps`}
              value={formatNumber(summary.workout_count)}
            />
            <DashboardCard
              color="green"
              label="Volume"
              spark={sparkbars?.volume}
              subvalue={`${formatNumber(summary.avg_intensity, 1)} kg volume / rep`}
              value={formatKg(summary.total_volume)}
            />
            <DashboardCard
              color="orange"
              label="Load"
              spark={sparkbars?.load}
              subvalue={`${formatNumber(summary.avg_load_score, 1)} avg load`}
              value={formatNumber(summary.total_load_score, 1)}
            />
            <DashboardCard
              color="red"
              label="Back stress"
              spark={sparkbars?.back_stress}
              subvalue={`${formatNumber(summary.avg_back_pain, 1)} avg pain`}
              tone={
                summary.avg_back_pain && summary.avg_back_pain >= 7
                  ? "red"
                  : summary.avg_back_pain && summary.avg_back_pain >= 5
                    ? "orange"
                    : undefined
              }
              value={formatNumber(summary.total_back_stress_score, 1)}
            />
          </section>

          <section className="stats-summary-panel">
            <h2>Summary</h2>

            <div className="stats-summary-grid">
              <SummaryMetric
                label="unique exercises"
                value={formatNumber(uniqueExerciseCount)}
              />

              <SummaryMetric
                detail={`${formatNumber(setsPerWorkout, 1)} per workout`}
                label="sets"
                value={formatNumber(summary.total_sets)}
              />

              <SummaryMetric
                detail={`${formatNumber(repsPerWorkout, 1)} per workout`}
                label="reps"
                value={formatNumber(summary.total_reps)}
              />

              <SummaryMetric
                label="kg volume / rep"
                value={formatNumber(summary.avg_intensity, 1)}
              />

              <SummaryMetric
                label="avg compound"
                value={formatNumber(summary.avg_compound_score, 1)}
              />

              <SummaryMetric
                detail={`${rpeLoggedCount}/${workoutCount} workouts logged`}
                label="avg RPE"
                tone={rpeTone(summary.avg_rpe)}
                value={
                  summary.avg_rpe === null
                    ? "—"
                    : `${formatNumber(summary.avg_rpe, 1)}/10`
                }
              />

              <SummaryMetric
                detail={`${backPainLoggedCount}/${workoutCount} workouts logged`}
                label="avg back pain"
                tone={backPainTone(summary.avg_back_pain)}
                value={
                  summary.avg_back_pain === null
                    ? "—"
                    : `${formatNumber(summary.avg_back_pain, 1)}/10`
                }
              />
            </div>
          </section>

          <div className="stats-chart-grid">
            <ChartCard
              wide
              subtitle="Total training volume by workout"
              title="Volume trend"
            >
              <ResponsiveContainer height={240} width="100%">
                <AreaChart
                  className="clickable-chart"
                  data={workoutData}
                  margin={{ top: 18, right: 18, left: 0, bottom: 0 }}
                  onClick={openWorkoutFromChart}
                >
                  <defs>
                    <linearGradient
                      id="volumeGradient"
                      x1="0"
                      x2="0"
                      y1="0"
                      y2="1"
                    >
                      <stop
                        offset="5%"
                        stopColor={chartColors.blue}
                        stopOpacity={0.55}
                      />
                      <stop
                        offset="95%"
                        stopColor={chartColors.blue}
                        stopOpacity={0.04}
                      />
                    </linearGradient>
                  </defs>

                  <CartesianGrid
                    stroke={chartColors.grid}
                    strokeDasharray="3 3"
                  />

                  <XAxis
                    dataKey="date"
                    stroke={chartColors.muted}
                    tick={{ fontSize: 12 }}
                  />

                  <YAxis
                    domain={[
                      0,
                      (dataMax: number) => Math.max(1, dataMax * 1.1),
                    ]}
                    stroke={chartColors.muted}
                    tick={{ fontSize: 12 }}
                  />

                  <Tooltip {...commonTooltipProps()} />

                  <Area
                    dataKey="volume"
                    fill="url(#volumeGradient)"
                    stroke={chartColors.blue}
                    strokeWidth={2}
                    type="monotone"
                  />

                  {topVolumePoint && (
                    <>
                      <ReferenceLine
                        label={{
                          value: `Peak ${formatNumber(topVolumePoint.volume)} kg`,
                          position: "insideTopRight",
                          fill: chartColors.orange,
                          fontSize: 12,
                        }}
                        stroke={chartColors.orange}
                        strokeDasharray="5 5"
                        y={topVolumePoint.volume}
                      />

                      <ReferenceDot
                        fill={chartColors.orange}
                        r={5}
                        stroke={chartColors.card}
                        strokeWidth={2}
                        x={topVolumePoint.date}
                        y={topVolumePoint.volume}
                      />
                    </>
                  )}
                </AreaChart>
              </ResponsiveContainer>

              <ChartInsight
                question="How much weighted work was logged?"
                explanation="Higher values mean a larger sum of weight × repetitions across the workout."
              >
                <div className="chart-insight-details">
                  <span>
                    Volume is calculated as weight × repetitions across all weighted sets.
                  </span>

                  <span>
                    It can increase through heavier weights, more repetitions, more sets,
                    or additional exercises.
                  </span>

                  <span>
                    Compare workouts with a similar exercise mix; higher volume does not
                    necessarily mean greater strength or a better workout.
                  </span>
                </div>
              </ChartInsight>
            </ChartCard>

            <ChartCard
              wide
              subtitle="Average recorded weight moved per repetition"
              title="Volume per rep"
            >
              <ResponsiveContainer height={240} width="100%">
                <LineChart
                  className="clickable-chart"
                  data={workoutData}
                  margin={{ top: 18, right: 18, left: 0, bottom: 0 }}
                  onClick={openWorkoutFromChart}
                >
                  <CartesianGrid
                    stroke={chartColors.grid}
                    strokeDasharray="3 3"
                  />

                  <XAxis
                    dataKey="date"
                    stroke={chartColors.muted}
                    tick={{ fontSize: 12 }}
                  />

                  <YAxis
                    domain={[
                      0,
                      (dataMax: number) => Math.max(1, dataMax * 1.1),
                    ]}
                    stroke={chartColors.muted}
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value) => formatNumber(value, 1)}
                  />

                  <Tooltip
                    {...commonTooltipProps()}
                    formatter={(value: unknown) => [
                      `${formatNumber(Number(value), 1)} kg/rep`,
                      "Volume per rep",
                    ]}
                  />

                  <Line
                    activeDot={{ r: 5 }}
                    dataKey="volumePerRep"
                    dot={{ r: 3 }}
                    stroke={chartColors.green}
                    strokeWidth={2}
                    type="monotone"
                  />

                  {topVolumePerRepPoint && (
                    <>
                      <ReferenceLine
                        label={{
                          value: `Peak ${formatNumber(
                            topVolumePerRepPoint.volumePerRep,
                            1,
                          )} kg/rep`,
                          position: "insideTopRight",
                          fill: chartColors.orange,
                          fontSize: 12,
                        }}
                        stroke={chartColors.orange}
                        strokeDasharray="5 5"
                        y={topVolumePerRepPoint.volumePerRep}
                      />

                      <ReferenceDot
                        fill={chartColors.orange}
                        r={5}
                        stroke={chartColors.card}
                        strokeWidth={2}
                        x={topVolumePerRepPoint.date}
                        y={topVolumePerRepPoint.volumePerRep}
                      />
                    </>
                  )}
                </LineChart>
              </ResponsiveContainer>

              <ChartInsight
                question="Was the session generally heavier or lighter?"
                explanation="Volume per rep shows the average recorded weight moved per repetition."
              >
                <div className="chart-insight-scale">
                  <div>
                    <strong>Lower</strong>
                    <span>Lighter weights or more high-repetition work</span>
                  </div>

                  <div>
                    <strong>Stable</strong>
                    <span>Similar average loading to nearby workouts</span>
                  </div>

                  <div>
                    <strong>Higher</strong>
                    <span>Heavier weights or more low-repetition work</span>
                  </div>
                </div>

                <p className="chart-insight-footnote">
                  Compare workouts with a similar exercise mix. A workout may have high
                  total volume but low volume per rep when it contains many lighter
                  repetitions.
                </p>
              </ChartInsight>
            </ChartCard>

            <ChartCard
              wide
              subtitle="Estimated set strength compared with previous exercise bests"
              title="Strength vs prior best"
            >
              <ResponsiveContainer height={240} width="100%">
                <LineChart
                  className="clickable-chart"
                  data={workoutData}
                  margin={{ top: 18, right: 18, left: 0, bottom: 0 }}
                  onClick={openWorkoutFromChart}
                >
                  <CartesianGrid
                    stroke={chartColors.grid}
                    strokeDasharray="3 3"
                  />

                  <XAxis
                    dataKey="date"
                    stroke={chartColors.muted}
                    tick={{ fontSize: 12 }}
                  />

                  <YAxis
                    allowDecimals={false}
                    domain={relativeIntensityDomain}
                    stroke={chartColors.muted}
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value) => `${formatNumber(value)}%`}
                  />

                  <Tooltip
                    {...commonTooltipProps()}
                    formatter={(value: unknown) => [
                      `${formatNumber(Number(value), 1)}%`,
                      "Relative intensity",
                    ]}
                  />

                  <Line
                    activeDot={{ r: 5 }}
                    connectNulls={false}
                    dataKey="relativeIntensity"
                    dot={{ r: 3 }}
                    stroke={chartColors.purple}
                    strokeWidth={2}
                    type="monotone"
                  />

                  <ReferenceLine
                    label={{
                      value: "100% prior best",
                      position: "insideTopRight",
                      fill: chartColors.muted,
                      fontSize: 11,
                    }}
                    stroke={chartColors.muted}
                    strokeDasharray="4 4"
                    y={100}
                  />
                </LineChart>
              </ResponsiveContainer>
              <ChartInsight
                question="How close were the performed sets to previous strength levels?"
                explanation="Each eligible set is compared with the previous best estimated 1RM for the same exercise, then averaged across the workout."
              >
                <div className="chart-insight-scale">
                  <div>
                    <strong>&lt;100%</strong>
                    <span>Below the prior e1RM baseline</span>
                  </div>

                  <div>
                    <strong>≈100%</strong>
                    <span>Near the prior e1RM baseline</span>
                  </div>

                  <div>
                    <strong>&gt;100%</strong>
                    <span>Above the prior e1RM baseline</span>
                  </div>
                </div>

                <p className="chart-insight-footnote">
                  Each workout is compared with the best estimated 1RM recorded before that
                  workout. Sessions without enough previous exercise history may have missing
                  values.
                </p>
              </ChartInsight>
            </ChartCard>

            <ChartCard
              wide
              subtitle="Overall load, compound demand, and estimated back stress by workout"
              title="Session load"
            >
              <ResponsiveContainer height={260} width="100%">
                <LineChart
                  className="clickable-chart"
                  data={workoutData}
                  margin={{ top: 12, right: 18, left: 0, bottom: 0 }}
                  onClick={openWorkoutFromChart}
                >
                  <CartesianGrid
                    stroke={chartColors.grid}
                    strokeDasharray="3 3"
                  />

                  <XAxis
                    dataKey="date"
                    stroke={chartColors.muted}
                    tick={{ fontSize: 12 }}
                  />

                  <YAxis
                    domain={[
                      0,
                      (dataMax: number) => Math.max(5, dataMax * 1.1),
                    ]}
                    stroke={chartColors.muted}
                    tick={{ fontSize: 12 }}
                  />

                  <Tooltip {...commonTooltipProps()} />

                  <Legend
                    formatter={(value) => {
                      const labels: Record<string, string> = {
                        load: "Overall load",
                        compound: "Compound demand",
                        backStress: "Back stress",
                      };

                      return labels[String(value)] ?? String(value);
                    }}
                    wrapperStyle={{ color: chartColors.muted }}
                  />

                  <Line
                    activeDot={{ r: 5 }}
                    dataKey="load"
                    dot={{ r: 3 }}
                    name="Overall load"
                    stroke={chartColors.blue}
                    strokeWidth={2}
                    type="monotone"
                  />

                  <Line
                    activeDot={{ r: 5 }}
                    dataKey="compound"
                    dot={{ r: 3 }}
                    name="Compound demand"
                    stroke={chartColors.green}
                    strokeWidth={2}
                    type="monotone"
                  />

                  <Line
                    activeDot={{ r: 5 }}
                    dataKey="backStress"
                    dot={{ r: 3 }}
                    name="Back stress"
                    stroke={chartColors.orange}
                    strokeWidth={2}
                    type="monotone"
                  />
                </LineChart>
              </ResponsiveContainer>

              <ChartInsight
                question="How demanding was the workout overall?"
                explanation="The chart separates general training demand, compound-exercise contribution, and estimated lower-back stress."
              >
                <div className="chart-insight-metrics">
                  <div>
                    <strong>Overall load</strong>
                    <span>
                      Combines exercise difficulty, repetition range, relative intensity,
                      number of working sets, and session RPE.
                    </span>
                  </div>

                  <div>
                    <strong>Compound demand</strong>
                    <span>
                      Shows how much of the workout came from larger compound movements
                      such as deadlifts, squats, presses, and rows.
                    </span>
                  </div>

                  <div>
                    <strong>Back stress</strong>
                    <span>
                      Estimates lower-back demand using each exercise&apos;s configured
                      back factor, repetition range, and relative intensity.
                    </span>
                  </div>
                </div>

                <div className="chart-insight-scale chart-insight-scale-four">
                  <div>
                    <strong>&lt;4</strong>
                    <span>Light overall load</span>
                  </div>

                  <div>
                    <strong>4–8</strong>
                    <span>Medium overall load</span>
                  </div>

                  <div>
                    <strong>8–14</strong>
                    <span>Hard overall load</span>
                  </div>

                  <div>
                    <strong>14+</strong>
                    <span>Very hard overall load</span>
                  </div>
                </div>

                <div className="chart-insight-details">
                  <span>
                    Rising overall load means recent sessions are becoming more demanding,
                    but the other two lines help explain why.
                  </span>

                  <span>
                    High compound demand with moderate back stress may indicate a demanding
                    session that is not especially back-heavy.
                  </span>

                  <span>
                    High back stress can occur even when total workout volume is moderate,
                    especially when back-loaded exercises are performed near previous
                    strength levels.
                  </span>

                  <span>
                    Compare these scores mainly against your own workout history. They are
                    personalized app scores, not standardized physical units.
                  </span>
                </div>

                <p className="chart-insight-footnote">
                  The Light, Medium, Hard, and Very hard ranges apply only to the blue
                  Overall load line. Compound demand and Back stress are separate supporting
                  scores and do not use the same category thresholds.
                </p>
              </ChartInsight>
            </ChartCard>

            <ChartCard
              wide
              subtitle="Daily distribution of calculated session load"
              title="Load calendar"
            >
              {loadCalendar?.weeks.length ? (
                <>
                  <div className="load-calendar-scroll">
                    <div className="load-calendar-shell">
                      <div />

                      <div
                        className="load-calendar-months"
                        style={{
                          gridTemplateColumns: `repeat(${loadCalendar.weeks.length}, 16px)`,
                        }}
                      >
                        {loadCalendar.weeks.map((week, weekIndex) => (
                          <span
                            className="load-calendar-month"
                            key={`month-${weekIndex}`}
                          >
                            {week.month_label}
                          </span>
                        ))}
                      </div>

                      <div
                        aria-hidden="true"
                        className="load-calendar-weekdays"
                      >
                        <span>Mon</span>
                        <span />
                        <span>Wed</span>
                        <span />
                        <span>Fri</span>
                        <span />
                        <span>Sun</span>
                      </div>

                      <div className="load-calendar-weeks">
                        {loadCalendar.weeks.map((week, weekIndex) => (
                          <div
                            className="load-calendar-week"
                            key={`week-${weekIndex}`}
                          >
                            {week.days.map((day) => {
                              const level = loadCalendarLevel(day);
                              const description =
                                loadCalendarDescription(day);

                              if (
                                day.has_workout &&
                                day.workout_id !== null
                              ) {
                                return (
                                  <button
                                    aria-label={`${description}. Open workout.`}
                                    className={
                                      `load-calendar-cell ` +
                                      `load-calendar-cell-${level}`
                                    }
                                    key={day.date}
                                    onClick={() =>
                                      navigateToWorkout(day.workout_id!)
                                    }
                                    title={description}
                                    type="button"
                                  />
                                );
                              }

                              return (
                                <span
                                  aria-label={description}
                                  className={
                                    `load-calendar-cell ` +
                                    `load-calendar-cell-${level}`
                                  }
                                  key={day.date}
                                  role="img"
                                  title={description}
                                />
                              );
                            })}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div
                    aria-label="Load calendar legend"
                    className="load-calendar-legend"
                  >
                    <div>
                      <span className="load-calendar-legend-cell load-calendar-cell-rest" />
                      <span>Rest</span>
                    </div>

                    <div>
                      <span className="load-calendar-legend-cell load-calendar-cell-light" />
                      <span>Light · &lt;4</span>
                    </div>

                    <div>
                      <span className="load-calendar-legend-cell load-calendar-cell-medium" />
                      <span>Medium · 4–&lt;8</span>
                    </div>

                    <div>
                      <span className="load-calendar-legend-cell load-calendar-cell-hard" />
                      <span>Hard · 8–&lt;14</span>
                    </div>

                    <div>
                      <span className="load-calendar-legend-cell load-calendar-cell-very-hard" />
                      <span>Very hard · 14+</span>
                    </div>
                  </div>

                  <ChartInsight
                    question="How are demanding workouts distributed over time?"
                    explanation="Each square represents one calendar day. Warmer colors indicate a higher calculated session load."
                  >
                    <div className="chart-insight-details">
                      <span>
                        Isolated hard days followed by rest or lighter sessions usually
                        show better load spacing.
                      </span>

                      <span>
                        Several orange or red squares close together indicate a cluster of
                        demanding sessions that may require more recovery.
                      </span>

                      <span>
                        Dark squares are days without a workout. They do not indicate
                        missing data.
                      </span>

                      <span>
                        Select a colored square to open that workout and inspect which
                        exercises, set intensities, and RPE contributed to its score.
                      </span>
                    </div>

                    <p className="chart-insight-footnote">
                      Load is a personalized app score based on exercise type, repetition
                      range, relative intensity, and session RPE. The calendar helps reveal
                      scheduling patterns; it does not directly measure whether you have
                      recovered.
                    </p>
                  </ChartInsight>
                </>
              ) : (
                <div className="empty">
                  No load calendar data.
                </div>
              )}
            </ChartCard>

            <ChartCard
              subtitle="Session RPE and lower-back pain scores"
              title="Recovery markers"
            >
              <ResponsiveContainer height={240} width="100%">
                <LineChart
                  className="clickable-chart"
                  data={workoutData}
                  onClick={openWorkoutFromChart}
                >
                  <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="date" stroke={chartColors.muted} tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 10]} stroke={chartColors.muted} tick={{ fontSize: 12 }} />
                  <Tooltip {...commonTooltipProps()} />
                  <Legend wrapperStyle={{ color: chartColors.muted }} />
                  <Line
                    connectNulls
                    dataKey="rpe"
                    stroke={chartColors.purple}
                    strokeWidth={2}
                    type="monotone"
                  />
                  <Line
                    connectNulls
                    dataKey="backPain"
                    stroke={chartColors.red}
                    strokeWidth={2}
                    type="monotone"
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard
              subtitle="Top exercises by accumulated volume"
              title="Exercise volume"
            >
              <ResponsiveContainer height={260} width="100%">
                <BarChart
                  className="clickable-bar-chart"
                  data={topExercises}
                  layout="vertical"
                  margin={{ left: 18 }}
                >
                  <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                  <XAxis stroke={chartColors.muted} tick={{ fontSize: 12 }} type="number" />
                  <YAxis
                    dataKey="name"
                    stroke={chartColors.muted}
                    tick={{ fontSize: 12 }}
                    type="category"
                    width={116}
                  />
                  <Tooltip {...commonTooltipProps()} />
                  <Bar
                    dataKey="total_volume"
                    fill={chartColors.blue}
                    onClick={(data: unknown) => openExerciseFromBar(data)}
                    radius={[0, 8, 8, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard
              wide
              subtitle="e1RM is shown only for weighted sets with 3–12 reps"
              title="Best strength estimates"
            >
              {bestStrength.length > 0 ? (
                <div className="strength-table-scroll">
                  <table className="strength-table">
                    <thead>
                      <tr>
                        <th>Exercise</th>
                        <th>Best e1RM</th>
                        <th>From set</th>
                        <th>Date</th>
                      </tr>
                    </thead>

                    <tbody>
                      {bestStrength.map((exercise) => (
                        <tr key={exercise.exercise_id}>
                          <td>
                            <button
                              className="strength-table-link"
                              onClick={() =>
                                navigateToExerciseStats(exercise.exercise_id)
                              }
                              type="button"
                            >
                              {exercise.name}
                            </button>
                          </td>

                          <td className="strength-table-value">
                            {formatNumber(exercise.best_e1rm, 1)} kg
                          </td>

                          <td className="strength-table-set">
                            {formatNumber(exercise.best_set.weight, 1)}
                            {" × "}
                            {exercise.best_set.reps}
                          </td>

                          <td>
                            <button
                              className="strength-table-link strength-table-date"
                              onClick={() =>
                                navigateToWorkout(exercise.best_set.workout_id)
                              }
                              type="button"
                            >
                              {exercise.best_set.date}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty">
                  No eligible strength estimates yet.
                </div>
              )}

              <ChartInsight
                question="What does the estimated 1RM represent?"
                explanation="e1RM estimates the maximum weight you could lift once, based on a recorded working set."
              >
                <div className="chart-insight-details">
                  <span>
                    The estimate is calculated only from weighted sets containing 3–12
                    repetitions.
                  </span>

                  <span>
                    The From set column shows the exact weight and repetitions that produced
                    the highest estimate for each exercise.
                  </span>

                  <span>
                    Compare e1RM changes within the same exercise. Values from different
                    exercises are not directly comparable.
                  </span>

                  <span>
                    Select an exercise to open its statistics, or select the date to open
                    the source workout.
                  </span>
                </div>

                <p className="chart-insight-footnote">
                  Sets such as 50 × 2, 20 × 15, and bodyweight sets such as 0 × 50 are
                  intentionally excluded from the e1RM calculation.
                </p>
              </ChartInsight>
            </ChartCard>
          </div>
        </>
      )}
    </section>
  );
}
