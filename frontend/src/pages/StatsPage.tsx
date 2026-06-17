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

import type {
  ExerciseRepProgress,
  ExerciseRepTargetProgress,
  ExerciseRepWeightPoint,
  ExerciseStats,
  ExerciseStrengthPoint,
  ExerciseWeeklyWorkload,
  ExerciseWeeklyWorkloadPoint,
  StatsResponse,
  StatsWorkout,
} from "../api/types";

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

const benchmarkPalette = [
  chartColors.blue,
  chartColors.green,
  chartColors.orange,
  chartColors.purple,
  chartColors.red,
];

type BenchmarkNormalizedPoint = {
  date: string;
  workoutId: number;
  index: number;
  e1rm: number;
};

type BenchmarkSeriesModel = {
  exerciseId: number;
  name: string;
  color: string;
  valueKey: string;
  rawKey: string;
  baselineE1rm: number;
  latestIndex: number;
  gain: number;
  points: BenchmarkNormalizedPoint[];
};

type BenchmarkChartPoint = {
  date: string;
  chartKey: string;
  [key: string]: string | number | null;
};

type StrengthWorkloadChartPoint = {
  id: number | null;
  week_start: string;
  weekLabel: string;
  weeklyE1rm: number | null;
  rollingBest: number | null;
  workload: number;
  sets: number;
  reps: number;
  volume: number;
  workouts: number;
  hasPr: boolean;
};

type WeeklyWorkloadMetric = "sets" | "reps" | "volume";

type WeeklyWorkloadChartPoint =
  ExerciseWeeklyWorkloadPoint & {
    weekLabel: string;
  };

function formatWeekLabel(weekStart: string) {
  const [year, month, day] = weekStart
    .split("-")
    .map(Number);

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(new Date(year, month - 1, day));
}

function weekStartForDate(dateValue: string) {
  const [year, month, day] = dateValue
    .slice(0, 10)
    .split("-")
    .map(Number);

  const workoutDate = new Date(year, month - 1, day);
  const daysSinceMonday =
    (workoutDate.getDay() + 6) % 7;

  workoutDate.setDate(
    workoutDate.getDate() - daysSinceMonday,
  );

  const weekYear = workoutDate.getFullYear();
  const weekMonth = String(
    workoutDate.getMonth() + 1,
  ).padStart(2, "0");
  const weekDay = String(
    workoutDate.getDate(),
  ).padStart(2, "0");

  return `${weekYear}-${weekMonth}-${weekDay}`;
}

function weeklyMetricLabel(
  metric: WeeklyWorkloadMetric,
) {
  if (metric === "sets") {
    return "Working sets";
  }

  if (metric === "reps") {
    return "Repetitions";
  }

  return "Volume";
}

function formatWeeklyMetric(
  value: number | null | undefined,
  metric: WeeklyWorkloadMetric,
) {
  if (value === null || value === undefined) {
    return "—";
  }

  if (metric === "volume") {
    return `${formatNumber(value, 0)} kg`;
  }

  return formatNumber(value, 0);
}

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

type StrengthChartPoint = ExerciseStrengthPoint & {
  id: number;
  chartKey: string;
};

type RepWeightChartPoint = ExerciseRepWeightPoint & {
  id: number;
  chartKey: string;
  reps: number;
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
  actions?: ReactNode;
  wide?: boolean;
};

function ChartCard({
  actions,
  children,
  subtitle,
  title,
  wide = false,
}: ChartCardProps) {
  return (
    <section className={wide ? "chart-card chart-card-wide" : "chart-card"}>
      <div
        className={
          actions
            ? "chart-heading chart-heading-with-actions"
            : "chart-heading"
        }
      >
        <div>
          <h2>{title}</h2>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>

        {actions && (
          <div className="chart-heading-actions">
            {actions}
          </div>
        )}
      </div>

      <div className="chart-frame">{children}</div>
    </section>
  );
}

type BenchmarkProgressTooltipProps = {
  active?: boolean;
  payload?: Array<{
    payload?: BenchmarkChartPoint;
  }>;
  series: BenchmarkSeriesModel[];
};

function BenchmarkProgressTooltip({
  active,
  payload,
  series,
}: BenchmarkProgressTooltipProps) {
  const point = payload?.find(
    (item) => item.payload,
  )?.payload;

  if (!active || !point) {
    return null;
  }

  const visibleSeries = series.filter(
    (item) =>
      typeof point[item.valueKey] === "number",
  );

  if (visibleSeries.length === 0) {
    return null;
  }

  return (
    <div className="benchmark-progress-tooltip">
      <strong>{point.date}</strong>

      {visibleSeries.map((item) => {
        const normalizedValue = Number(
          point[item.valueKey],
        );

        const e1rm = Number(
          point[item.rawKey],
        );

        return (
          <div
            className="benchmark-tooltip-row"
            key={item.exerciseId}
          >
            <span
              aria-hidden="true"
              className="benchmark-tooltip-dot"
              style={{
                background: item.color,
              }}
            />

            <div>
              <b>{item.name}</b>

              <span>
                {formatNumber(
                  normalizedValue,
                  1,
                )}
                %
                {" · "}
                {formatNumber(e1rm, 1)} kg e1RM
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

type WeeklyWorkloadTooltipProps = {
  active?: boolean;
  metric: WeeklyWorkloadMetric;
  payload?: Array<{
    payload?: WeeklyWorkloadChartPoint;
  }>;
};

function WeeklyWorkloadTooltip({
  active,
  metric,
  payload,
}: WeeklyWorkloadTooltipProps) {
  const point = payload?.[0]?.payload;

  if (!active || !point) {
    return null;
  }

  return (
    <div className="strength-progress-tooltip">
      <strong>
        Week of {formatWeekLabel(point.week_start)}
      </strong>

      <div>
        <span>{weeklyMetricLabel(metric)}</span>
        <b>
          {formatWeeklyMetric(point[metric], metric)}
        </b>
      </div>

      <div>
        <span>Workouts</span>
        <b>{point.workouts}</b>
      </div>

      <div>
        <span>Sets</span>
        <b>{point.sets}</b>
      </div>

      <div>
        <span>Reps</span>
        <b>{point.reps}</b>
      </div>

      <div>
        <span>Volume</span>
        <b>{formatNumber(point.volume, 0)} kg</b>
      </div>
    </div>
  );
}

type StrengthWorkloadTooltipProps = {
  active?: boolean;
  metric: WeeklyWorkloadMetric;
  mode: "strength" | "workload";
  payload?: Array<{
    payload?: StrengthWorkloadChartPoint;
  }>;
};

function StrengthWorkloadTooltip({
  active,
  metric,
  mode,
  payload,
}: StrengthWorkloadTooltipProps) {
  const point = payload?.find(
    (item) => item.payload,
  )?.payload;

  if (!active || !point) {
    return null;
  }

  return (
    <div className="strength-progress-tooltip">
      <strong>
        Week of {formatWeekLabel(point.week_start)}
      </strong>

      {mode === "strength" ? (
        <>
          <div>
            <span>Weekly best e1RM</span>
            <b>
              {point.weeklyE1rm === null
                ? "—"
                : `${formatNumber(
                    point.weeklyE1rm,
                    1,
                  )} kg`}
            </b>
          </div>

          <div>
            <span>Historical best</span>
            <b>
              {point.rollingBest === null
                ? "—"
                : `${formatNumber(
                    point.rollingBest,
                    1,
                  )} kg`}
            </b>
          </div>

          {point.hasPr && (
            <div className="strength-progress-pr">
              New e1RM PR this week
            </div>
          )}
        </>
      ) : (
        <>
          <div>
            <span>{weeklyMetricLabel(metric)}</span>
            <b>
              {formatWeeklyMetric(
                point.workload,
                metric,
              )}
            </b>
          </div>

          <div>
            <span>Workouts</span>
            <b>{point.workouts}</b>
          </div>

          <div>
            <span>Sets</span>
            <b>{point.sets}</b>
          </div>

          <div>
            <span>Reps</span>
            <b>{point.reps}</b>
          </div>

          <div>
            <span>Volume</span>
            <b>
              {formatNumber(point.volume, 0)} kg
            </b>
          </div>
        </>
      )}
    </div>
  );
}

type StrengthTooltipProps = {
  active?: boolean;
  payload?: Array<{
    payload?: StrengthChartPoint;
  }>;
};

function StrengthProgressTooltip({
  active,
  payload,
}: StrengthTooltipProps) {
  const point = payload?.[0]?.payload;

  if (!active || !point) {
    return null;
  }

  return (
    <div className="strength-progress-tooltip">
      <strong>{point.date}</strong>

      <div>
        <span>Session e1RM</span>
        <b>{formatNumber(point.e1rm, 1)} kg</b>
      </div>

      <div>
        <span>Rolling best</span>
        <b>{formatNumber(point.rolling_best, 1)} kg</b>
      </div>

      <div>
        <span>From set</span>
        <b>
          {formatNumber(point.weight, 1)} × {point.reps}
        </b>
      </div>

      {point.is_pr && (
        <div className="strength-progress-pr">
          New e1RM PR
        </div>
      )}
    </div>
  );
}

type RepWeightTooltipProps = {
  active?: boolean;
  payload?: Array<{
    payload?: RepWeightChartPoint;
  }>;
};

function RepWeightProgressTooltip({
  active,
  payload,
}: RepWeightTooltipProps) {
  const point = payload?.[0]?.payload;

  if (!active || !point) {
    return null;
  }

  return (
    <div className="strength-progress-tooltip">
      <strong>{point.date}</strong>

      <div>
        <span>Best {point.reps}-rep weight</span>
        <b>{formatNumber(point.weight, 1)} kg</b>
      </div>

      <div>
        <span>Historical best</span>
        <b>{formatNumber(point.rolling_best, 1)} kg</b>
      </div>

      {point.is_pr && (
        <div className="strength-progress-pr">
          New {point.reps}-rep PR
        </div>
      )}
    </div>
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

  const [selectedStrengthExerciseId, setSelectedStrengthExerciseId] =
  useState<number | null>(null);

  const [selectedRepExerciseId, setSelectedRepExerciseId] =
  useState<number | null>(null);

  const [selectedRepTarget, setSelectedRepTarget] =
    useState<number | null>(null);

  const [
    selectedWorkloadExerciseId,
    setSelectedWorkloadExerciseId,
  ] = useState<number | null>(null);

  const [
    weeklyWorkloadMetric,
    setWeeklyWorkloadMetric,
  ] = useState<WeeklyWorkloadMetric>("sets");

  const [
    selectedComparisonExerciseId,
    setSelectedComparisonExerciseId,
  ] = useState<number | null>(null);

  const [
    comparisonWorkloadMetric,
    setComparisonWorkloadMetric,
  ] = useState<WeeklyWorkloadMetric>("sets");

  const [
    selectedBenchmarkExerciseIds,
    setSelectedBenchmarkExerciseIds,
  ] = useState<number[]>([]);

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

  const exerciseWeeklyWorkload =
    useMemo<ExerciseWeeklyWorkload[]>(
      () =>
        stats?.stats.exercise_weekly_workload ?? [],
      [stats],
    );

  useEffect(() => {
    if (exerciseWeeklyWorkload.length === 0) {
      setSelectedWorkloadExerciseId(null);
      return;
    }

    setSelectedWorkloadExerciseId((current) => {
      const currentStillExists =
        exerciseWeeklyWorkload.some(
          (exercise) =>
            exercise.exercise_id === current,
        );

      return currentStillExists
        ? current
        : exerciseWeeklyWorkload[0].exercise_id;
    });
  }, [exerciseWeeklyWorkload]);

  const selectedWeeklyWorkload = useMemo(
    () =>
      exerciseWeeklyWorkload.find(
        (exercise) =>
          exercise.exercise_id ===
          selectedWorkloadExerciseId,
      ) ??
      exerciseWeeklyWorkload[0] ??
      null,
    [
      exerciseWeeklyWorkload,
      selectedWorkloadExerciseId,
    ],
  );

  const weeklyWorkloadData =
    useMemo<WeeklyWorkloadChartPoint[]>(
      () =>
        (selectedWeeklyWorkload?.weeks ?? []).map(
          (week) => ({
            ...week,
            weekLabel: formatWeekLabel(
              week.week_start,
            ),
          }),
        ),
      [selectedWeeklyWorkload],
    );

  const activeWorkloadWeeks = weeklyWorkloadData.filter(
    (week) => week.workouts > 0,
  );

  const totalWeeklyMetric =
    weeklyWorkloadData.reduce(
      (total, week) =>
        total + week[weeklyWorkloadMetric],
      0,
    );

  const averageActiveWeek =
    activeWorkloadWeeks.length > 0
      ? totalWeeklyMetric /
        activeWorkloadWeeks.length
      : null;

  const latestWorkloadWeek =
    weeklyWorkloadData[
      weeklyWorkloadData.length - 1
    ] ?? null;

  const weeklyBarColor =
    weeklyWorkloadMetric === "sets"
      ? chartColors.blue
      : weeklyWorkloadMetric === "reps"
        ? chartColors.green
        : chartColors.orange;

  const weeklyChartWidth = Math.max(
    680,
    weeklyWorkloadData.length * 54,
  );

  const exerciseProgress = useMemo(
    () => stats?.stats.exercise_progress ?? [],
    [stats],
  );

  const benchmarkCandidates = useMemo(
    () =>
      exerciseProgress.filter(
        (exercise) =>
          exercise.points.length >= 2,
      ),
    [exerciseProgress],
  );

  useEffect(() => {
    const validExerciseIds = new Set(
      benchmarkCandidates.map(
        (exercise) => exercise.exercise_id,
      ),
    );

    setSelectedBenchmarkExerciseIds(
      (current) => {
        const retained = current
          .filter((exerciseId) =>
            validExerciseIds.has(exerciseId),
          )
          .slice(0, 5);

        if (retained.length > 0) {
          return retained;
        }

        return benchmarkCandidates
          .slice(0, 3)
          .map(
            (exercise) =>
              exercise.exercise_id,
          );
      },
    );
  }, [benchmarkCandidates]);

  useEffect(() => {
    if (exerciseProgress.length === 0) {
      setSelectedStrengthExerciseId(null);
      return;
    }

    setSelectedStrengthExerciseId((current) => {
      const currentStillExists = exerciseProgress.some(
        (exercise) => exercise.exercise_id === current,
      );

      return currentStillExists
        ? current
        : exerciseProgress[0].exercise_id;
    });
  }, [exerciseProgress]);

  const selectedStrengthProgress = useMemo(
    () =>
      exerciseProgress.find(
        (exercise) =>
          exercise.exercise_id === selectedStrengthExerciseId,
      ) ??
      exerciseProgress[0] ??
      null,
    [exerciseProgress, selectedStrengthExerciseId],
  );

  const exerciseRepProgress = useMemo<ExerciseRepProgress[]>(
    () => stats?.stats.exercise_rep_progress ?? [],
    [stats],
  );

  useEffect(() => {
    if (exerciseRepProgress.length === 0) {
      setSelectedRepExerciseId(null);
      return;
    }

    setSelectedRepExerciseId((current) => {
      const currentStillExists = exerciseRepProgress.some(
        (exercise) => exercise.exercise_id === current,
      );

      return currentStillExists
        ? current
        : exerciseRepProgress[0].exercise_id;
    });
  }, [exerciseRepProgress]);

  const selectedRepExercise = useMemo(
    () =>
      exerciseRepProgress.find(
        (exercise) =>
          exercise.exercise_id === selectedRepExerciseId,
      ) ??
      exerciseRepProgress[0] ??
      null,
    [exerciseRepProgress, selectedRepExerciseId],
  );

  useEffect(() => {
    const targets = selectedRepExercise?.rep_targets ?? [];

    if (targets.length === 0) {
      setSelectedRepTarget(null);
      return;
    }

    setSelectedRepTarget((current) => {
      const currentStillExists = targets.some(
        (target) => target.reps === current,
      );

      if (currentStillExists) {
        return current;
      }

      const preferredTarget = [...targets].sort(
        (
          first: ExerciseRepTargetProgress,
          second: ExerciseRepTargetProgress,
        ) =>
          second.points.length - first.points.length ||
          first.reps - second.reps,
      )[0];

      return preferredTarget?.reps ?? null;
    });
  }, [selectedRepExercise]);

  const selectedRepTargetProgress = useMemo(
    () =>
      selectedRepExercise?.rep_targets.find(
        (target) => target.reps === selectedRepTarget,
      ) ??
      selectedRepExercise?.rep_targets[0] ??
      null,
    [selectedRepExercise, selectedRepTarget],
  );

  const repWeightChartData = useMemo<RepWeightChartPoint[]>(
    () =>
      (selectedRepTargetProgress?.points ?? []).map(
        (point) => ({
          ...point,
          id: point.workout_id,
          chartKey: `${point.date}-${point.workout_id}`,
          reps: selectedRepTargetProgress?.reps ?? 0,
        }),
      ),
    [selectedRepTargetProgress],
  );

  const repWeightDomain = useMemo<[number, number]>(() => {
    const values = repWeightChartData.flatMap((point) => [
      point.weight,
      point.rolling_best,
    ]);

    if (values.length === 0) {
      return [0, 1];
    }

    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const minimumSpan = Math.max(maximum * 0.08, 2);
    const span = Math.max(maximum - minimum, minimumSpan);
    const padding = span * 0.15;

    return [
      Math.max(
        0,
        Math.floor((minimum - padding) * 10) / 10,
      ),
      Math.ceil((maximum + padding) * 10) / 10,
    ];
  }, [repWeightChartData]);

  const firstRepWeightPoint = repWeightChartData[0] ?? null;

  const latestRepWeightPoint =
    repWeightChartData[repWeightChartData.length - 1] ?? null;

  const visibleRepWeightChange =
    firstRepWeightPoint && latestRepWeightPoint
      ? latestRepWeightPoint.weight - firstRepWeightPoint.weight
      : null;

  const strengthChartData = useMemo<StrengthChartPoint[]>(
    () =>
      (selectedStrengthProgress?.points ?? []).map((point) => ({
        ...point,
        id: point.workout_id,
        chartKey: `${point.date}-${point.workout_id}`,
      })),
    [selectedStrengthProgress],
  );

  const strengthProgressDomain = useMemo<[number, number]>(() => {
    const values = strengthChartData.flatMap((point) => [
      point.e1rm,
      point.rolling_best,
    ]);

    if (values.length === 0) {
      return [0, 1];
    }

    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const minimumSpan = Math.max(maximum * 0.08, 2);
    const span = Math.max(maximum - minimum, minimumSpan);
    const padding = span * 0.15;

    return [
      Math.max(
        0,
        Math.floor((minimum - padding) * 10) / 10,
      ),
      Math.ceil((maximum + padding) * 10) / 10,
    ];
  }, [strengthChartData]);

  const firstStrengthPoint = strengthChartData[0] ?? null;
  const latestStrengthPoint =
    strengthChartData[strengthChartData.length - 1] ?? null;

  const visibleStrengthChange =
    firstStrengthPoint && latestStrengthPoint
      ? latestStrengthPoint.e1rm - firstStrengthPoint.e1rm
      : null;

  const comparisonExercises = useMemo(() => {
  const workloadExerciseIds = new Set(
    exerciseWeeklyWorkload.map(
      (exercise) => exercise.exercise_id,
    ),
  );

  return exerciseProgress
    .filter((exercise) =>
      workloadExerciseIds.has(
        exercise.exercise_id,
      ),
    )
    .map((exercise) => ({
      exercise_id: exercise.exercise_id,
      name: exercise.name,
    }));
}, [
  exerciseProgress,
  exerciseWeeklyWorkload,
]);

useEffect(() => {
  if (comparisonExercises.length === 0) {
    setSelectedComparisonExerciseId(null);
    return;
  }

  setSelectedComparisonExerciseId((current) => {
    const currentStillExists =
      comparisonExercises.some(
        (exercise) =>
          exercise.exercise_id === current,
      );

    return currentStillExists
      ? current
      : comparisonExercises[0].exercise_id;
  });
}, [comparisonExercises]);

const selectedComparisonStrength = useMemo(
  () =>
    exerciseProgress.find(
      (exercise) =>
        exercise.exercise_id ===
        selectedComparisonExerciseId,
    ) ?? null,
  [
    exerciseProgress,
    selectedComparisonExerciseId,
  ],
);

const selectedComparisonWorkload = useMemo(
  () =>
    exerciseWeeklyWorkload.find(
      (exercise) =>
        exercise.exercise_id ===
        selectedComparisonExerciseId,
    ) ?? null,
  [
    exerciseWeeklyWorkload,
    selectedComparisonExerciseId,
  ],
);

const strengthWorkloadData =
  useMemo<StrengthWorkloadChartPoint[]>(
    () => {
      if (
        !selectedComparisonStrength ||
        !selectedComparisonWorkload
      ) {
        return [];
      }

      const strengthByWeek = new Map<
        string,
        {
          weeklyE1rm: number;
          rollingBest: number;
          hasPr: boolean;
          workoutId: number;
        }
      >();

      for (
        const point
        of selectedComparisonStrength.points
      ) {
        const weekStart = weekStartForDate(
          point.date,
        );

        const existing =
          strengthByWeek.get(weekStart);

        if (!existing) {
          strengthByWeek.set(weekStart, {
            weeklyE1rm: point.e1rm,
            rollingBest: point.rolling_best,
            hasPr: point.is_pr,
            workoutId: point.workout_id,
          });

          continue;
        }

        existing.rollingBest = Math.max(
          existing.rollingBest,
          point.rolling_best,
        );

        existing.hasPr =
          existing.hasPr || point.is_pr;

        if (
          point.e1rm > existing.weeklyE1rm
        ) {
          existing.weeklyE1rm = point.e1rm;
          existing.workoutId =
            point.workout_id;
        }
      }

      let carriedRollingBest:
        number | null = null;

      return selectedComparisonWorkload.weeks.map(
        (week) => {
          const strength =
            strengthByWeek.get(
              week.week_start,
            );

          if (strength) {
            carriedRollingBest =
              carriedRollingBest === null
                ? strength.rollingBest
                : Math.max(
                    carriedRollingBest,
                    strength.rollingBest,
                  );
          }

          return {
            id: strength?.workoutId ?? null,
            week_start: week.week_start,
            weekLabel: formatWeekLabel(
              week.week_start,
            ),
            weeklyE1rm:
              strength?.weeklyE1rm ?? null,
            rollingBest:
              carriedRollingBest,
            workload:
              week[comparisonWorkloadMetric],
            sets: week.sets,
            reps: week.reps,
            volume: week.volume,
            workouts: week.workouts,
            hasPr: strength?.hasPr ?? false,
          };
        },
      );
    },
    [
      comparisonWorkloadMetric,
      selectedComparisonStrength,
      selectedComparisonWorkload,
    ],
  );

  const strengthWorkloadDomain =
    useMemo<[number, number]>(() => {
      const values: number[] = [];

      for (const point of strengthWorkloadData) {
        if (point.weeklyE1rm !== null) {
          values.push(point.weeklyE1rm);
        }

        if (point.rollingBest !== null) {
          values.push(point.rollingBest);
        }
      }

      if (values.length === 0) {
        return [0, 1];
      }

      const minimum = Math.min(...values);
      const maximum = Math.max(...values);
      const minimumSpan = Math.max(
        maximum * 0.08,
        2,
      );
      const span = Math.max(
        maximum - minimum,
        minimumSpan,
      );
      const padding = span * 0.15;

      return [
        Math.max(
          0,
          Math.floor(
            (minimum - padding) * 10,
          ) / 10,
        ),
        Math.ceil(
          (maximum + padding) * 10,
        ) / 10,
      ];
    }, [strengthWorkloadData]);

  const comparisonBestValues =
    strengthWorkloadData
      .map((point) => point.rollingBest)
      .filter(
        (value): value is number =>
          value !== null,
      );

  const firstComparisonBest =
    comparisonBestValues[0] ?? null;

  const latestComparisonBest =
    comparisonBestValues[
      comparisonBestValues.length - 1
    ] ?? null;

  const comparisonStrengthGain =
    firstComparisonBest !== null &&
    latestComparisonBest !== null
      ? latestComparisonBest -
        firstComparisonBest
      : null;

  const comparisonActiveWeeks =
    strengthWorkloadData.filter(
      (point) => point.workouts > 0,
    );

  const averageComparisonWorkload =
    comparisonActiveWeeks.length > 0
      ? comparisonActiveWeeks.reduce(
          (total, point) =>
            total + point.workload,
          0,
        ) / comparisonActiveWeeks.length
      : null;

  const comparisonBarColor =
    comparisonWorkloadMetric === "sets"
      ? chartColors.blue
      : comparisonWorkloadMetric === "reps"
        ? chartColors.green
        : chartColors.orange;

  const strengthWorkloadChartWidth = Math.max(
    680,
    strengthWorkloadData.length * 54,
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

  function toggleBenchmarkExercise(
    exerciseId: number,
  ) {
    setSelectedBenchmarkExerciseIds(
      (current) => {
        const isSelected =
          current.includes(exerciseId);

        if (isSelected) {
          if (current.length === 1) {
            return current;
          }

          return current.filter(
            (selectedId) =>
              selectedId !== exerciseId,
          );
        }

        if (current.length >= 5) {
          return current;
        }

        return [...current, exerciseId];
      },
    );
  }

  const benchmarkSeries =
    useMemo<BenchmarkSeriesModel[]>(
      () =>
        selectedBenchmarkExerciseIds
          .map((exerciseId, index) => {
            const exercise =
              benchmarkCandidates.find(
                (candidate) =>
                  candidate.exercise_id ===
                  exerciseId,
              );

            if (!exercise) {
              return null;
            }

            const sortedPoints = [
              ...exercise.points,
            ].sort(
              (first, second) =>
                first.date.localeCompare(
                  second.date,
                ) ||
                first.workout_id -
                  second.workout_id,
            );

            /*
            * Normally an exercise has one point
            * per date. If more than one workout
            * exists on the same date, retain the
            * highest e1RM for that date.
            */
            const bestPointByDate = new Map<
              string,
              ExerciseStrengthPoint
            >();

            for (const point of sortedPoints) {
              const existing =
                bestPointByDate.get(
                  point.date,
                );

              if (
                !existing ||
                point.e1rm > existing.e1rm
              ) {
                bestPointByDate.set(
                  point.date,
                  point,
                );
              }
            }

            const uniquePoints = [
              ...bestPointByDate.values(),
            ].sort(
              (first, second) =>
                first.date.localeCompare(
                  second.date,
                ),
            );

            const baselineE1rm =
              uniquePoints[0]?.e1rm;

            if (
              baselineE1rm === undefined ||
              baselineE1rm <= 0
            ) {
              return null;
            }

            const points =
              uniquePoints.map(
                (point) => ({
                  date: point.date,
                  workoutId:
                    point.workout_id,
                  e1rm: point.e1rm,
                  index:
                    point.e1rm /
                    baselineE1rm *
                    100,
                }),
              );

            const latestIndex =
              points[
                points.length - 1
              ]?.index ?? 100;

            return {
              exerciseId:
                exercise.exercise_id,
              name: exercise.name,
              color:
                benchmarkPalette[
                  index %
                    benchmarkPalette.length
                ],
              valueKey:
                `benchmark_${exercise.exercise_id}`,
              rawKey:
                `benchmark_raw_${exercise.exercise_id}`,
              baselineE1rm,
              latestIndex,
              gain: latestIndex - 100,
              points,
            };
          })
          .filter(
            (
              series,
            ): series is BenchmarkSeriesModel =>
              series !== null,
          ),
      [
        benchmarkCandidates,
        selectedBenchmarkExerciseIds,
      ],
    );

  const benchmarkChartData =
    useMemo<BenchmarkChartPoint[]>(
      () => {
        const pointsByDate = new Map<
          string,
          BenchmarkChartPoint
        >();

        for (const series of benchmarkSeries) {
          for (const point of series.points) {
            const row =
              pointsByDate.get(point.date) ??
              {
                date: point.date,
                chartKey: point.date,
              };

            row[series.valueKey] =
              point.index;

            row[series.rawKey] =
              point.e1rm;

            pointsByDate.set(
              point.date,
              row,
            );
          }
        }

        return [...pointsByDate.values()].sort(
          (first, second) =>
            first.date.localeCompare(
              second.date,
            ),
        );
      },
      [benchmarkSeries],
    );

  const benchmarkProgressDomain =
    useMemo<[number, number]>(() => {
      const values =
        benchmarkSeries.flatMap(
          (series) =>
            series.points.map(
              (point) => point.index,
            ),
        );

      if (values.length === 0) {
        return [90, 110];
      }

      const minimum = Math.min(
        ...values,
        100,
      );

      const maximum = Math.max(
        ...values,
        100,
      );

      const span = Math.max(
        maximum - minimum,
        10,
      );

      const padding = Math.max(
        3,
        span * 0.12,
      );

      return [
        Math.max(
          0,
          Math.floor(minimum - padding),
        ),
        Math.ceil(maximum + padding),
      ];
    }, [benchmarkSeries]);

  const averageBenchmarkIndex =
    benchmarkSeries.length > 0
      ? benchmarkSeries.reduce(
          (total, series) =>
            total + series.latestIndex,
          0,
        ) / benchmarkSeries.length
      : null;

  const strongestBenchmark =
    benchmarkSeries.length > 0
      ? benchmarkSeries.reduce(
          (strongest, series) =>
            series.gain > strongest.gain
              ? series
              : strongest,
        )
      : null;

  const benchmarkChartWidth = Math.max(
    680,
    benchmarkChartData.length * 48,
  );

  const benchmarkNeedsScroll =
    benchmarkChartData.length > 20;

  const benchmarkChartMinWidth =
    benchmarkNeedsScroll
      ? benchmarkChartData.length * 48
      : "100%";

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

            <ChartCard
              wide
              actions={
                selectedStrengthProgress ? (
                  <label className="chart-exercise-select">
                    <span>Exercise</span>

                    <select
                      onChange={(event) =>
                        setSelectedStrengthExerciseId(
                          Number(event.target.value),
                        )
                      }
                      value={
                        selectedStrengthExerciseId ??
                        selectedStrengthProgress.exercise_id
                      }
                    >
                      {exerciseProgress.map((exercise) => (
                        <option
                          key={exercise.exercise_id}
                          value={exercise.exercise_id}
                        >
                          {exercise.name}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null
              }
              subtitle="Best valid e1RM from each workout, compared with the historical all-time best"
              title="Exercise strength progress"
            >
              {selectedStrengthProgress && strengthChartData.length > 0 ? (
                <>
                  <div className="strength-progress-summary">
                    <div>
                      <strong>
                        {formatNumber(latestStrengthPoint?.e1rm, 1)} kg
                      </strong>
                      <span>latest session e1RM</span>
                    </div>

                    <div>
                      <strong>
                        {formatNumber(
                          latestStrengthPoint?.rolling_best,
                          1,
                        )}{" "}
                        kg
                      </strong>
                      <span>historical rolling best</span>
                    </div>

                    <div>
                      <strong>
                        {visibleStrengthChange === null
                          ? "—"
                          : `${visibleStrengthChange >= 0 ? "+" : ""}${formatNumber(
                              visibleStrengthChange,
                              1,
                            )} kg`}
                      </strong>
                      <span>change in selected range</span>
                    </div>
                  </div>

                  <ResponsiveContainer height={300} width="100%">
                    <LineChart
                      className="clickable-chart"
                      data={strengthChartData}
                      margin={{
                        top: 18,
                        right: 18,
                        left: 0,
                        bottom: 0,
                      }}
                      onClick={openWorkoutFromChart}
                    >
                      <CartesianGrid
                        stroke={chartColors.grid}
                        strokeDasharray="3 3"
                      />

                      <XAxis
                        dataKey="chartKey"
                        stroke={chartColors.muted}
                        tick={{ fontSize: 12 }}
                        tickFormatter={(value) =>
                          String(value).slice(0, 10)
                        }
                      />

                      <YAxis
                        domain={strengthProgressDomain}
                        stroke={chartColors.muted}
                        tick={{ fontSize: 12 }}
                        tickFormatter={(value) =>
                          formatNumber(Number(value), 1)
                        }
                      />

                      <Tooltip content={<StrengthProgressTooltip />} />

                      <Legend
                        wrapperStyle={{ color: chartColors.muted }}
                      />

                      <Line
                        activeDot={{ r: 5 }}
                        dataKey="e1rm"
                        dot={{ r: 3 }}
                        name="Session e1RM"
                        stroke={chartColors.blue}
                        strokeWidth={2}
                        type="monotone"
                      />

                      <Line
                        activeDot={false}
                        dataKey="rolling_best"
                        dot={false}
                        name="Rolling best"
                        stroke={chartColors.green}
                        strokeWidth={3}
                        type="stepAfter"
                      />

                      {strengthChartData
                        .filter((point) => point.is_pr)
                        .map((point) => (
                          <ReferenceDot
                            fill={chartColors.orange}
                            key={`pr-${point.workout_id}`}
                            r={6}
                            stroke={chartColors.card}
                            strokeWidth={2}
                            x={point.chartKey}
                            y={point.e1rm}
                          />
                        ))}
                    </LineChart>
                  </ResponsiveContainer>

                  <ChartInsight
                    question="Am I becoming stronger at this exercise?"
                    explanation="The blue line shows the best estimated 1RM achieved in each workout. The green stepped line shows the historical all-time best available after that workout."
                  >
                    <div className="chart-insight-details">
                      <span>
                        Orange markers identify genuine new e1RM personal
                        records. The first valid result establishes the
                        baseline and is not marked as a PR.
                      </span>

                      <span>
                        A rising green line is the clearest indication of
                        measurable strength progress.
                      </span>

                      <span>
                        Temporary drops in the blue line are normal and may
                        reflect fatigue, lighter programming, or different
                        repetition targets.
                      </span>

                      <span>
                        Select a chart point to open its source workout.
                      </span>
                    </div>

                    <p className="chart-insight-footnote">
                      e1RM is calculated only from weighted sets containing
                      3–12 repetitions. The rolling best includes workouts
                      before the selected 10, 30, or 90-workout range.
                    </p>
                  </ChartInsight>
                </>
              ) : (
                <div className="empty">
                  No eligible exercise strength history yet.
                </div>
              )}
            </ChartCard>

            <ChartCard
              wide
              actions={
                selectedRepExercise ? (
                  <div className="chart-filter-row">
                    <label className="chart-exercise-select">
                      <span>Exercise</span>

                      <select
                        onChange={(event) =>
                          setSelectedRepExerciseId(
                            Number(event.target.value),
                          )
                        }
                        value={
                          selectedRepExerciseId ??
                          selectedRepExercise.exercise_id
                        }
                      >
                        {exerciseRepProgress.map((exercise) => (
                          <option
                            key={exercise.exercise_id}
                            value={exercise.exercise_id}
                          >
                            {exercise.name}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="chart-rep-select">
                      <span>Reps</span>

                      <select
                        onChange={(event) =>
                          setSelectedRepTarget(
                            Number(event.target.value),
                          )
                        }
                        value={
                          selectedRepTarget ??
                          selectedRepTargetProgress?.reps ??
                          ""
                        }
                      >
                        {selectedRepExercise.rep_targets.map((target) => (
                          <option
                            key={target.reps}
                            value={target.reps}
                          >
                            {target.reps} reps
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                ) : null
              }
              subtitle="Best actual weight lifted for the same repetition target in each workout"
              title="Weight at fixed reps"
            >
              {selectedRepExercise &&
              selectedRepTargetProgress &&
              repWeightChartData.length > 0 ? (
                <>
                  <div className="strength-progress-summary">
                    <div>
                      <strong>
                        {formatNumber(
                          latestRepWeightPoint?.weight,
                          1,
                        )}{" "}
                        kg
                      </strong>
                      <span>
                        latest {selectedRepTargetProgress.reps}-rep weight
                      </span>
                    </div>

                    <div>
                      <strong>
                        {formatNumber(
                          latestRepWeightPoint?.rolling_best,
                          1,
                        )}{" "}
                        kg
                      </strong>
                      <span>
                        historical {selectedRepTargetProgress.reps}-rep best
                      </span>
                    </div>

                    <div>
                      <strong>
                        {visibleRepWeightChange === null
                          ? "—"
                          : `${
                              visibleRepWeightChange >= 0 ? "+" : ""
                            }${formatNumber(
                              visibleRepWeightChange,
                              1,
                            )} kg`}
                      </strong>
                      <span>change in selected range</span>
                    </div>
                  </div>

                  <ResponsiveContainer height={300} width="100%">
                    <LineChart
                      className="clickable-chart"
                      data={repWeightChartData}
                      margin={{
                        top: 18,
                        right: 18,
                        left: 0,
                        bottom: 0,
                      }}
                      onClick={openWorkoutFromChart}
                    >
                      <CartesianGrid
                        stroke={chartColors.grid}
                        strokeDasharray="3 3"
                      />

                      <XAxis
                        dataKey="chartKey"
                        stroke={chartColors.muted}
                        tick={{ fontSize: 12 }}
                        tickFormatter={(value) =>
                          String(value).slice(0, 10)
                        }
                      />

                      <YAxis
                        domain={repWeightDomain}
                        stroke={chartColors.muted}
                        tick={{ fontSize: 12 }}
                        tickFormatter={(value) =>
                          formatNumber(Number(value), 1)
                        }
                      />

                      <Tooltip
                        content={<RepWeightProgressTooltip />}
                      />

                      <Legend
                        wrapperStyle={{ color: chartColors.muted }}
                      />

                      <Line
                        activeDot={{ r: 5 }}
                        dataKey="weight"
                        dot={{ r: 3 }}
                        name={`Best ${selectedRepTargetProgress.reps}-rep weight`}
                        stroke={chartColors.blue}
                        strokeWidth={2}
                        type="monotone"
                      />

                      <Line
                        activeDot={false}
                        dataKey="rolling_best"
                        dot={false}
                        name="Historical best"
                        stroke={chartColors.green}
                        strokeWidth={3}
                        type="stepAfter"
                      />

                      {repWeightChartData
                        .filter((point) => point.is_pr)
                        .map((point) => (
                          <ReferenceDot
                            fill={chartColors.orange}
                            key={`rep-pr-${point.workout_id}`}
                            r={6}
                            stroke={chartColors.card}
                            strokeWidth={2}
                            x={point.chartKey}
                            y={point.weight}
                          />
                        ))}
                    </LineChart>
                  </ResponsiveContainer>

                  <ChartInsight
                    question={`Can I lift more actual weight for ${selectedRepTargetProgress.reps} repetitions?`}
                    explanation="This chart compares only sets from the same exercise with exactly the same number of repetitions."
                  >
                    <div className="chart-insight-details">
                      <span>
                        The blue line shows the heaviest qualifying set
                        performed in each workout.
                      </span>

                      <span>
                        The green stepped line shows the historical best
                        weight recorded for this exact exercise and rep
                        count.
                      </span>

                      <span>
                        Orange markers indicate genuine fixed-rep personal
                        records. The first recorded result establishes the
                        baseline.
                      </span>

                      <span>
                        Workouts where this exact rep target was not
                        performed are omitted rather than interpolated.
                      </span>

                      <span>
                        For the most accurate comparison, keep technique,
                        range of motion, equipment, and exercise variation
                        consistent.
                      </span>
                    </div>

                    <p className="chart-insight-footnote">
                      Unlike e1RM, this is a direct recorded-performance
                      metric and does not use a strength-estimation formula.
                      Only sets with positive recorded weight are included.
                    </p>
                  </ChartInsight>
                </>
              ) : (
                <div className="empty">
                  No fixed-repetition weight history for this exercise.
                </div>
              )}
            </ChartCard>

            <ChartCard
              wide
              actions={
                selectedWeeklyWorkload ? (
                  <div className="chart-filter-row">
                    <label className="chart-exercise-select">
                      <span>Exercise</span>

                      <select
                        onChange={(event) =>
                          setSelectedWorkloadExerciseId(
                            Number(event.target.value),
                          )
                        }
                        value={
                          selectedWorkloadExerciseId ??
                          selectedWeeklyWorkload.exercise_id
                        }
                      >
                        {exerciseWeeklyWorkload.map(
                          (exercise) => (
                            <option
                              key={exercise.exercise_id}
                              value={exercise.exercise_id}
                            >
                              {exercise.name}
                            </option>
                          ),
                        )}
                      </select>
                    </label>

                    <div className="weekly-metric-select">
                      <span>Metric</span>

                      <div
                        aria-label="Weekly workload metric"
                        className="weekly-metric-buttons"
                        role="group"
                      >
                        {(
                          [
                            ["sets", "Sets"],
                            ["reps", "Reps"],
                            ["volume", "Volume"],
                          ] as Array<
                            [WeeklyWorkloadMetric, string]
                          >
                        ).map(([metric, label]) => (
                          <button
                            aria-pressed={
                              weeklyWorkloadMetric === metric
                            }
                            className={
                              weeklyWorkloadMetric === metric
                                ? "weekly-metric-button weekly-metric-button-active"
                                : "weekly-metric-button"
                            }
                            key={metric}
                            onClick={() =>
                              setWeeklyWorkloadMetric(metric)
                            }
                            type="button"
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null
              }
              subtitle="Weekly training exposure for one exercise"
              title="Weekly exercise workload"
            >
              {selectedWeeklyWorkload &&
              weeklyWorkloadData.length > 0 ? (
                <>
                  <div className="strength-progress-summary">
                    <div>
                      <strong>
                        {formatWeeklyMetric(
                          latestWorkloadWeek?.[
                            weeklyWorkloadMetric
                          ],
                          weeklyWorkloadMetric,
                        )}
                      </strong>
                      <span>latest calendar week</span>
                    </div>

                    <div>
                      <strong>
                        {formatWeeklyMetric(
                          averageActiveWeek,
                          weeklyWorkloadMetric,
                        )}
                      </strong>
                      <span>average active week</span>
                    </div>

                    <div>
                      <strong>
                        {activeWorkloadWeeks.length}
                      </strong>
                      <span>
                        weeks with this exercise
                      </span>
                    </div>
                  </div>

                  <div className="weekly-workload-chart-scroll">
                    <div
                      className="weekly-workload-chart"
                      style={{ width: weeklyChartWidth }}
                    >
                      <ResponsiveContainer
                        height={300}
                        width="100%"
                      >
                        <BarChart
                          data={weeklyWorkloadData}
                          margin={{
                            top: 18,
                            right: 18,
                            left: 0,
                            bottom: 0,
                          }}
                        >
                          <CartesianGrid
                            stroke={chartColors.grid}
                            strokeDasharray="3 3"
                          />

                          <XAxis
                            dataKey="weekLabel"
                            stroke={chartColors.muted}
                            tick={{ fontSize: 12 }}
                          />

                          <YAxis
                            allowDecimals={
                              weeklyWorkloadMetric === "volume"
                            }
                            domain={[0, "auto"]}
                            stroke={chartColors.muted}
                            tick={{ fontSize: 12 }}
                          />

                          <Tooltip
                            content={
                              <WeeklyWorkloadTooltip
                                metric={weeklyWorkloadMetric}
                              />
                            }
                          />

                          <Bar
                            dataKey={weeklyWorkloadMetric}
                            fill={weeklyBarColor}
                            name={weeklyMetricLabel(
                              weeklyWorkloadMetric,
                            )}
                            radius={[6, 6, 0, 0]}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <ChartInsight
                    question="Am I training this exercise consistently enough to support progress?"
                    explanation="Each bar represents one calendar week. Change the metric to compare working sets, repetitions, or total weight moved."
                  >
                    <div className="chart-insight-details">
                      <span>
                        Sets are usually the clearest default
                        measure of weekly training exposure.
                      </span>

                      <span>
                        Repetitions reveal changes in rep
                        emphasis, but can rise when lighter
                        training is used.
                      </span>

                      <span>
                        Volume combines weight and repetitions,
                        but can change substantially when the
                        exercise or rep range changes.
                      </span>

                      <span>
                        A zero week means the selected exercise
                        was not performed. It is not missing
                        data.
                      </span>

                      <span>
                        Compare this chart with the strength
                        trend above. Rising strength with stable
                        workload is generally a stronger signal
                        than volume rising by itself.
                      </span>
                    </div>

                    <p className="chart-insight-footnote">
                      Weekly workload describes training
                      exposure, not recovery or muscle growth.
                      Compare trends primarily within the same
                      exercise and technique.
                    </p>
                  </ChartInsight>
                </>
              ) : (
                <div className="empty">
                  No weekly workload history for this exercise.
                </div>
              )}
            </ChartCard>

            <ChartCard
              wide
              actions={
                comparisonExercises.length > 0 ? (
                  <div className="chart-filter-row">
                    <label className="chart-exercise-select">
                      <span>Exercise</span>

                      <select
                        onChange={(event) =>
                          setSelectedComparisonExerciseId(
                            Number(event.target.value),
                          )
                        }
                        value={
                          selectedComparisonExerciseId ??
                          comparisonExercises[0]
                            .exercise_id
                        }
                      >
                        {comparisonExercises.map(
                          (exercise) => (
                            <option
                              key={exercise.exercise_id}
                              value={exercise.exercise_id}
                            >
                              {exercise.name}
                            </option>
                          ),
                        )}
                      </select>
                    </label>

                    <div className="weekly-metric-select">
                      <span>Workload</span>

                      <div
                        aria-label="Comparison workload metric"
                        className="weekly-metric-buttons"
                        role="group"
                      >
                        {(
                          [
                            ["sets", "Sets"],
                            ["reps", "Reps"],
                            ["volume", "Volume"],
                          ] as Array<
                            [WeeklyWorkloadMetric, string]
                          >
                        ).map(([metric, label]) => (
                          <button
                            aria-pressed={
                              comparisonWorkloadMetric ===
                              metric
                            }
                            className={
                              comparisonWorkloadMetric ===
                              metric
                                ? "weekly-metric-button weekly-metric-button-active"
                                : "weekly-metric-button"
                            }
                            key={metric}
                            onClick={() =>
                              setComparisonWorkloadMetric(
                                metric,
                              )
                            }
                            type="button"
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null
              }
              subtitle="Weekly strength performance aligned with weekly training exposure"
              title="Strength versus workload"
            >
              {selectedComparisonStrength &&
              selectedComparisonWorkload &&
              strengthWorkloadData.length > 0 ? (
                <>
                  <div className="strength-progress-summary">
                    <div>
                      <strong>
                        {latestComparisonBest === null
                          ? "—"
                          : `${formatNumber(
                              latestComparisonBest,
                              1,
                            )} kg`}
                      </strong>
                      <span>current rolling e1RM best</span>
                    </div>

                    <div>
                      <strong>
                        {comparisonStrengthGain === null
                          ? "—"
                          : `${
                              comparisonStrengthGain >= 0
                                ? "+"
                                : ""
                            }${formatNumber(
                              comparisonStrengthGain,
                              1,
                            )} kg`}
                      </strong>
                      <span>rolling-best gain in range</span>
                    </div>

                    <div>
                      <strong>
                        {formatWeeklyMetric(
                          averageComparisonWorkload,
                          comparisonWorkloadMetric,
                        )}
                      </strong>
                      <span>average active-week workload</span>
                    </div>
                  </div>

                  <div className="strength-workload-scroll">
                    <div
                      className="strength-workload-inner"
                      style={{
                        width: strengthWorkloadChartWidth,
                      }}
                    >
                      <section className="strength-workload-panel">
                        <div className="strength-workload-panel-heading">
                          <strong>Strength</strong>
                          <span>
                            Weekly best e1RM and historical best
                          </span>
                        </div>

                        <ResponsiveContainer
                          height={240}
                          width="100%"
                        >
                          <LineChart
                            className="clickable-chart"
                            data={strengthWorkloadData}
                            margin={{
                              top: 16,
                              right: 18,
                              left: 0,
                              bottom: 0,
                            }}
                            onClick={openWorkoutFromChart}
                            syncId="strength-workload-comparison"
                          >
                            <CartesianGrid
                              stroke={chartColors.grid}
                              strokeDasharray="3 3"
                            />

                            <XAxis
                              dataKey="week_start"
                              hide
                            />

                            <YAxis
                              domain={strengthWorkloadDomain}
                              stroke={chartColors.muted}
                              tick={{ fontSize: 12 }}
                              tickFormatter={(value) =>
                                formatNumber(
                                  Number(value),
                                  1,
                                )
                              }
                              width={52}
                            />

                            <Tooltip
                              content={
                                <StrengthWorkloadTooltip
                                  metric={
                                    comparisonWorkloadMetric
                                  }
                                  mode="strength"
                                />
                              }
                            />

                            <Legend
                              wrapperStyle={{
                                color: chartColors.muted,
                              }}
                            />

                            <Line
                              activeDot={{ r: 5 }}
                              connectNulls
                              dataKey="weeklyE1rm"
                              dot={{ r: 3 }}
                              name="Weekly best e1RM"
                              stroke={chartColors.blue}
                              strokeWidth={2}
                              type="monotone"
                            />

                            <Line
                              activeDot={false}
                              dataKey="rollingBest"
                              dot={false}
                              name="Historical best"
                              stroke={chartColors.green}
                              strokeWidth={3}
                              type="stepAfter"
                            />

                            {strengthWorkloadData
                              .filter(
                                (point) =>
                                  point.hasPr &&
                                  point.weeklyE1rm !== null,
                              )
                              .map((point) => (
                                <ReferenceDot
                                  fill={chartColors.orange}
                                  key={`comparison-pr-${point.week_start}`}
                                  r={6}
                                  stroke={chartColors.card}
                                  strokeWidth={2}
                                  x={point.week_start}
                                  y={point.weeklyE1rm!}
                                />
                              ))}
                          </LineChart>
                        </ResponsiveContainer>
                      </section>

                      <section className="strength-workload-panel">
                        <div className="strength-workload-panel-heading">
                          <strong>Workload</strong>
                          <span>
                            {weeklyMetricLabel(
                              comparisonWorkloadMetric,
                            )}{" "}
                            per calendar week
                          </span>
                        </div>

                        <ResponsiveContainer
                          height={230}
                          width="100%"
                        >
                          <BarChart
                            data={strengthWorkloadData}
                            margin={{
                              top: 16,
                              right: 18,
                              left: 0,
                              bottom: 0,
                            }}
                            syncId="strength-workload-comparison"
                          >
                            <CartesianGrid
                              stroke={chartColors.grid}
                              strokeDasharray="3 3"
                            />

                            <XAxis
                              dataKey="week_start"
                              stroke={chartColors.muted}
                              tick={{ fontSize: 12 }}
                              tickFormatter={(value) =>
                                formatWeekLabel(
                                  String(value),
                                )
                              }
                            />

                            <YAxis
                              allowDecimals={
                                comparisonWorkloadMetric ===
                                "volume"
                              }
                              domain={[0, "auto"]}
                              stroke={chartColors.muted}
                              tick={{ fontSize: 12 }}
                              width={52}
                            />

                            <Tooltip
                              content={
                                <StrengthWorkloadTooltip
                                  metric={
                                    comparisonWorkloadMetric
                                  }
                                  mode="workload"
                                />
                              }
                            />

                            <Bar
                              dataKey="workload"
                              fill={comparisonBarColor}
                              name={weeklyMetricLabel(
                                comparisonWorkloadMetric,
                              )}
                              radius={[6, 6, 0, 0]}
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </section>
                    </div>
                  </div>

                  <ChartInsight
                    question="Is additional workload producing measurable strength progress?"
                    explanation="The charts use the same weekly timeline so changes in strength can be compared directly with training exposure."
                  >
                    <div className="chart-insight-details">
                      <span>
                        A rising green strength line while
                        workload remains relatively stable is
                        a strong indication of improved
                        performance.
                      </span>

                      <span>
                        Rising workload followed by a later
                        strength increase may indicate useful
                        training accumulation.
                      </span>

                      <span>
                        Workload rising for several weeks
                        without any strength improvement may
                        reflect fatigue, excessive volume,
                        exercise inconsistency, or insufficient
                        recovery.
                      </span>

                      <span>
                        A short-term e1RM decline does not
                        automatically indicate lost strength.
                        Rep targets, fatigue, technique, and
                        programming can affect an individual
                        session.
                      </span>

                      <span>
                        Weeks without a valid 3–12-rep weighted
                        set have no blue strength point. They
                        are not estimated or filled in.
                      </span>
                    </div>

                    <p className="chart-insight-footnote">
                      This comparison shows association, not
                      causation. Training adaptations can lag
                      behind workload by several weeks, and the
                      chart does not account for sleep,
                      nutrition, illness, or other recovery
                      factors.
                    </p>
                  </ChartInsight>
                </>
              ) : (
                <div className="empty">
                  No matching strength and workload history.
                </div>
              )}
            </ChartCard>

            <ChartCard
              wide
              subtitle="Compare relative e1RM development across exercises with different absolute weights"
              title="Normalized benchmark progress"
            >
              {benchmarkCandidates.length > 0 ? (
                <>
                  <section className="benchmark-picker">
                    <div className="benchmark-picker-heading">
                      <div>
                        <strong>Benchmark lifts</strong>
                        <span>
                          Select up to five exercises
                        </span>
                      </div>

                      <span>
                        {
                          selectedBenchmarkExerciseIds
                            .length
                        }
                        /5 selected
                      </span>
                    </div>

                    <div className="benchmark-picker-options">
                      {benchmarkCandidates.map(
                        (exercise) => {
                          const isSelected =
                            selectedBenchmarkExerciseIds.includes(
                              exercise.exercise_id,
                            );

                          const maximumReached =
                            selectedBenchmarkExerciseIds
                              .length >= 5;

                          const isOnlySelection =
                            isSelected &&
                            selectedBenchmarkExerciseIds
                              .length === 1;

                          return (
                            <button
                              aria-pressed={isSelected}
                              className={
                                isSelected
                                  ? "benchmark-picker-button benchmark-picker-button-active"
                                  : "benchmark-picker-button"
                              }
                              disabled={
                                isOnlySelection ||
                                (!isSelected &&
                                  maximumReached)
                              }
                              key={
                                exercise.exercise_id
                              }
                              onClick={() =>
                                toggleBenchmarkExercise(
                                  exercise.exercise_id,
                                )
                              }
                              type="button"
                            >
                              {exercise.name}
                            </button>
                          );
                        },
                      )}
                    </div>
                  </section>

                  {benchmarkSeries.length > 0 &&
                  benchmarkChartData.length > 0 ? (
                    <>
                      <div className="strength-progress-summary">
                        <div>
                          <strong>
                            {benchmarkSeries.length}
                          </strong>
                          <span>benchmark lifts</span>
                        </div>

                        <div>
                          <strong>
                            {averageBenchmarkIndex ===
                            null
                              ? "—"
                              : `${formatNumber(
                                  averageBenchmarkIndex,
                                  1,
                                )}%`}
                          </strong>
                          <span>
                            average latest index
                          </span>
                        </div>

                        <div>
                          <strong>
                            {strongestBenchmark
                              ? `${
                                  strongestBenchmark
                                    .gain >= 0
                                    ? "+"
                                    : ""
                                }${formatNumber(
                                  strongestBenchmark.gain,
                                  1,
                                )}%`
                              : "—"}
                          </strong>

                          <span>
                            {strongestBenchmark
                              ? `strongest relative gain · ${strongestBenchmark.name}`
                              : "strongest relative gain"}
                          </span>
                        </div>
                      </div>

                      <div className="benchmark-chart-scroll">
                        <div
                          className="benchmark-chart-inner"
                          style={{
                            minWidth: benchmarkChartMinWidth,
                          }}
                        >
                          <ResponsiveContainer
                            height={340}
                            width="100%"
                          >
                            <LineChart
                              data={
                                benchmarkChartData
                              }
                              margin={{
                                top: 22,
                                right: 22,
                                left: 0,
                                bottom: 0,
                              }}
                            >
                              <CartesianGrid
                                stroke={
                                  chartColors.grid
                                }
                                strokeDasharray="3 3"
                              />

                              <XAxis
                                dataKey="chartKey"
                                minTickGap={24}
                                interval="preserveStartEnd"
                                stroke={chartColors.muted}
                                tick={{ fontSize: 12 }}
                              />

                              <YAxis
                                domain={
                                  benchmarkProgressDomain
                                }
                                stroke={
                                  chartColors.muted
                                }
                                tick={{
                                  fontSize: 12,
                                }}
                                tickFormatter={(
                                  value,
                                ) =>
                                  `${formatNumber(
                                    Number(value),
                                    0,
                                  )}%`
                                }
                                width={52}
                              />

                              <ReferenceLine
                                label={{
                                  value:
                                    "100% baseline",
                                  fill:
                                    chartColors.muted,
                                  fontSize: 11,
                                  position:
                                    "insideTopLeft",
                                }}
                                stroke={
                                  chartColors.muted
                                }
                                strokeDasharray="5 5"
                                y={100}
                              />

                              <Tooltip
                                content={
                                  <BenchmarkProgressTooltip
                                    series={
                                      benchmarkSeries
                                    }
                                  />
                                }
                              />

                              <Legend
                                wrapperStyle={{
                                  color:
                                    chartColors.muted,
                                }}
                              />

                              {benchmarkSeries.map(
                                (series) => (
                                  <Line
                                    activeDot={{
                                      r: 5,
                                    }}
                                    connectNulls
                                    dataKey={
                                      series.valueKey
                                    }
                                    dot={{ r: 3 }}
                                    key={
                                      series.exerciseId
                                    }
                                    name={series.name}
                                    stroke={
                                      series.color
                                    }
                                    strokeWidth={2.5}
                                    type="monotone"
                                  />
                                ),
                              )}
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </div>

                      <div className="benchmark-results-grid">
                        {benchmarkSeries.map(
                          (series) => (
                            <div
                              className="benchmark-result"
                              key={
                                series.exerciseId
                              }
                            >
                              <div>
                                <span
                                  aria-hidden="true"
                                  className="benchmark-result-dot"
                                  style={{
                                    background:
                                      series.color,
                                  }}
                                />

                                <strong>
                                  {series.name}
                                </strong>
                              </div>

                              <b>
                                {formatNumber(
                                  series.latestIndex,
                                  1,
                                )}
                                %
                              </b>

                              <span>
                                {series.gain >= 0
                                  ? "+"
                                  : ""}
                                {formatNumber(
                                  series.gain,
                                  1,
                                )}
                                %
                                {" · baseline "}
                                {formatNumber(
                                  series.baselineE1rm,
                                  1,
                                )}{" "}
                                kg
                              </span>
                            </div>
                          ),
                        )}
                      </div>

                      <ChartInsight
                        question="Which benchmark lifts are progressing fastest relative to their own starting points?"
                        explanation="Every exercise begins at 100%, allowing relative progress to be compared despite large differences in absolute lifting weight."
                      >
                        <div className="chart-insight-details">
                          <span>
                            A value of 110% means the
                            session e1RM is 10% above
                            that exercise&apos;s first
                            valid result in the selected
                            range.
                          </span>

                          <span>
                            Compare the slope and total
                            percentage change, not the
                            absolute height of the
                            original e1RM.
                          </span>

                          <span>
                            Missing exercise dates are
                            skipped. The chart does not
                            generate artificial strength
                            results for workouts where
                            the exercise was absent.
                          </span>

                          <span>
                            Short-term declines can reflect
                            fatigue, lighter programming,
                            or different repetition
                            targets rather than actual
                            strength loss.
                          </span>

                          <span>
                            Exercises with fewer than two
                            eligible e1RM results are not
                            offered as benchmark lifts.
                          </span>
                        </div>

                        <p className="chart-insight-footnote">
                          The 100% baseline is recalculated
                          from the first valid e1RM inside
                          the currently selected 10, 30,
                          90, or All-workout range.
                          Changing the range may therefore
                          change both the baseline and the
                          displayed percentage gain.
                        </p>
                      </ChartInsight>
                    </>
                  ) : (
                    <div className="empty">
                      Select at least one benchmark lift.
                    </div>
                  )}
                </>
              ) : (
                <div className="empty">
                  At least two eligible strength results
                  are required for a benchmark exercise.
                </div>
              )}
            </ChartCard>

          </div>
        </>
      )}
    </section>
  );
}
