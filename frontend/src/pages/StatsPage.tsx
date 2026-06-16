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

const sparkChars = " ▁▂▃▄▅▆▇█";

type ChartPoint = {
  id: number;
  date: string;
  volume: number;
  load: number;
  compound: number;
  backStress: number;
  intensity: number | null;
  rpe: number | null;
  backPain: number | null;
};

function formatNumber(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return Number(value).toFixed(digits);
}

function formatKg(value: number | null | undefined) {
  return `${formatNumber(value)} kg`;
}

function buildSpark(values: Array<number | null | undefined>, width = 14) {
  const validValues = values
    .filter((value): value is number => value !== null && value !== undefined)
    .map(Number);

  if (validValues.length === 0) {
    return "—";
  }

  const sampledValues = values.length > width
    ? Array.from({ length: width }, (_, index) => {
        const start = Math.floor((index * values.length) / width);
        const end = Math.floor(((index + 1) * values.length) / width);
        const bucket = values
          .slice(start, end)
          .filter((value): value is number => value !== null && value !== undefined);

        return bucket.length
          ? bucket.reduce((total, value) => total + Number(value), 0) / bucket.length
          : null;
      })
    : values;

  const maxValue = Math.max(...validValues, 1);
  const maxIndex = sparkChars.length - 1;

  return sampledValues
    .map((value) => {
      if (value === null || value === undefined) {
        return "·";
      }

      const ratio = Math.max(0, Math.min(1, Number(value) / maxValue));
      return sparkChars[Math.round(ratio * maxIndex)];
    })
    .join("");
}

function buildWorkoutData(workouts: StatsWorkout[]): ChartPoint[] {
  return workouts.map((workout) => ({
    id: workout.id,
    date: workout.date,
    volume: workout.total_volume,
    load: workout.load_score,
    compound: workout.compound_score,
    backStress: workout.back_stress_score,
    intensity: workout.intensity_score,
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

type ChartCardProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
};

function ChartCard({ children, subtitle, title }: ChartCardProps) {
  return (
    <section className="chart-card">
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

export default function StatsPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Failed to load.");
      });
  }, []);

  const workoutData = useMemo(
    () => buildWorkoutData(stats?.stats.workouts ?? []),
    [stats],
  );
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

  return (
    <section className="page-stack">
      {error && <div className="error-banner">{error}</div>}
      {!stats && !error && <section className="panel">Loading</section>}
      {stats && workoutData.length === 0 && <EmptyStats />}

      {stats && summary && workoutData.length > 0 && (
        <>
          <section className="dashboard-grid">
            <DashboardCard
              color="blue"
              label="Workouts"
              spark={buildSpark(workoutData.map((item) => item.load))}
              subvalue={`${formatNumber(summary.total_sets)} sets · ${formatNumber(
                summary.total_reps,
              )} reps`}
              value={formatNumber(summary.workout_count)}
            />
            <DashboardCard
              color="green"
              label="Volume"
              spark={buildSpark(workoutData.map((item) => item.volume))}
              subvalue={`${formatKg(summary.avg_intensity)} avg intensity`}
              value={formatKg(summary.total_volume)}
            />
            <DashboardCard
              color="orange"
              label="Load"
              spark={buildSpark(workoutData.map((item) => item.load))}
              subvalue={`${formatNumber(summary.avg_load_score, 1)} avg load`}
              value={formatNumber(summary.total_load_score, 1)}
            />
            <DashboardCard
              color="red"
              label="Back stress"
              spark={buildSpark(workoutData.map((item) => item.backStress))}
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

          <div className="stats-chart-grid">
            <ChartCard
              subtitle="Total training volume by workout"
              title="Volume trend"
            >
              <ResponsiveContainer height={240} width="100%">
                <AreaChart data={workoutData}>
                  <defs>
                    <linearGradient id="volumeGradient" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="5%" stopColor={chartColors.blue} stopOpacity={0.55} />
                      <stop offset="95%" stopColor={chartColors.blue} stopOpacity={0.04} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="date" stroke={chartColors.muted} tick={{ fontSize: 12 }} />
                  <YAxis stroke={chartColors.muted} tick={{ fontSize: 12 }} />
                  <Tooltip {...commonTooltipProps()} />
                  <Area
                    dataKey="volume"
                    fill="url(#volumeGradient)"
                    stroke={chartColors.blue}
                    strokeWidth={2}
                    type="monotone"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard
              subtitle="Load, compound contribution, and back stress"
              title="Session load"
            >
              <ResponsiveContainer height={240} width="100%">
                <LineChart data={workoutData}>
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
                <LineChart data={workoutData}>
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
                <BarChart data={topExercises} layout="vertical" margin={{ left: 18 }}>
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
                  <Bar dataKey="total_volume" fill={chartColors.blue} radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard
              subtitle="Best estimated 1RM per exercise"
              title="Strength leaders"
            >
              <ResponsiveContainer height={260} width="100%">
                <BarChart data={bestStrength} layout="vertical" margin={{ left: 18 }}>
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
                  <Bar dataKey="best_e1rm" fill={chartColors.green} radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
        </>
      )}
    </section>
  );
}
