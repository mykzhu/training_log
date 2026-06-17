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

  const topExercises = useMemo(
    () => [...(stats?.stats.exercise_stats ?? [])]
      .sort((a, b) => b.total_volume - a.total_volume)
      .slice(0, 8),
    [stats],
  );

  const bestStrength = useMemo(
    () => [...(stats?.stats.exercise_stats ?? [])]
      .filter((exercise): exercise is ExerciseStats & { best_e1rm: number } =>
        exercise.best_e1rm !== null,
      )
      .sort((a, b) => b.best_e1rm - a.best_e1rm)
      .slice(0, 8),
    [stats],
  );

  const summary = stats?.stats.summary;
  const sparkbars = stats?.charts.sparkbars;
  const workouts = stats?.stats.workouts ?? [];
  const workoutCount = summary?.workout_count ?? 0;

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
              subtitle="Average recorded weight per repetition"
              title="Volume per rep"
            >
              <ResponsiveContainer height={240} width="100%">
                <LineChart
                  className="clickable-chart"
                  data={workoutData}
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
                    stroke={chartColors.muted}
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value) => `${formatNumber(value, 1)}`}
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
                </LineChart>
              </ResponsiveContainer>
              <ChartInsight
                question="Was the session generally heavier or lighter?"
                explanation="Volume per rep shows the average recorded weight moved per repetition."
              >
                <div className="chart-insight-scale">
                  <div>
                    <strong>Lower</strong>
                    <span>Lighter weights or more high-rep work</span>
                  </div>

                  <div>
                    <strong>Stable</strong>
                    <span>Similar average loading to recent workouts</span>
                  </div>

                  <div>
                    <strong>Higher</strong>
                    <span>Heavier weights or more low-rep work</span>
                  </div>
                </div>

                <p className="chart-insight-footnote">
                  Compare this with total volume: a workout can have high total volume but
                  low volume per rep when many lighter repetitions were performed.
                </p>
              </ChartInsight>
            </ChartCard>

            <ChartCard
              subtitle="Average estimated intensity versus previous personal bests"
              title="Relative intensity"
            >
              <ResponsiveContainer height={240} width="100%">
                <LineChart
                  className="clickable-chart"
                  data={workoutData}
                  margin={{ top: 12, right: 12, left: 0, bottom: 0 }}
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
                      (dataMax: number) => Math.max(110, dataMax * 1.05),
                    ]}
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

                  <ReferenceLine
                    label={{
                      value: "Previous best",
                      position: "insideTopRight",
                      fill: chartColors.muted,
                      fontSize: 11,
                    }}
                    stroke={chartColors.muted}
                    strokeDasharray="4 4"
                    y={100}
                  />

                  <Line
                    activeDot={{ r: 5 }}
                    dataKey="relativeIntensity"
                    dot={{ r: 3 }}
                    stroke={chartColors.purple}
                    strokeWidth={2}
                    type="monotone"
                  />
                </LineChart>
              </ResponsiveContainer>
              <ChartInsight
                question="How close were working sets to previous strength levels?"
                explanation="Relative intensity compares estimated set strength with the best historical e1RM available before that workout."
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
              subtitle="Load, compound contribution, and back stress"
              title="Session load"
            >
              <ResponsiveContainer height={240} width="100%">
                <LineChart
                  className="clickable-chart"
                  data={workoutData}
                  onClick={openWorkoutFromChart}
                >
                  <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="date" stroke={chartColors.muted} tick={{ fontSize: 12 }} />
                  <YAxis stroke={chartColors.muted} tick={{ fontSize: 12 }} />
                  <Tooltip {...commonTooltipProps()} />
                  <Legend wrapperStyle={{ color: chartColors.muted }} />
                  <Line
                    dataKey="load"
                    dot={false}
                    stroke={chartColors.blue}
                    strokeWidth={2}
                    type="monotone"
                  />
                  <Line
                    dataKey="compound"
                    dot={false}
                    stroke={chartColors.green}
                    strokeWidth={2}
                    type="monotone"
                  />
                  <Line
                    dataKey="backStress"
                    dot={false}
                    stroke={chartColors.orange}
                    strokeWidth={2}
                    type="monotone"
                  />
                </LineChart>
              </ResponsiveContainer>
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
              subtitle="Best estimated 1RM per exercise"
              title="Strength leaders"
            >
              <ResponsiveContainer height={260} width="100%">
                <BarChart
                  className="clickable-bar-chart"
                  data={bestStrength}
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
                    dataKey="best_e1rm"
                    fill={chartColors.green}
                    onClick={(data: unknown) => openExerciseFromBar(data)}
                    radius={[0, 8, 8, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
        </>
      )}
    </section>
  );
}
