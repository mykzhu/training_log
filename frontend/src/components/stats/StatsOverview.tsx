import type { ReactNode } from "react";

import type { StatsSparkbars, StatsSummary } from "../../api/types";

type StatsLimit = 10 | 30 | 90 | "all";

type MetricTone = "green" | "yellow" | "orange" | "red";

type StatsLimitOption = {
  value: StatsLimit;
  label: string;
};

type DashboardCardProps = {
  label: string;
  value: string;
  subvalue: string;
  spark?: string;
  color?: "blue" | "green" | "orange" | "red" | "purple";
  tone?: MetricTone;
};

type SummaryMetricProps = {
  label: string;
  value: ReactNode;
  detail?: string;
  tone?: MetricTone;
};

type StatsRangeToolbarProps = {
  options: StatsLimitOption[];
  selectedLimit: StatsLimit;
  onSelectLimit: (limit: StatsLimit) => void;
};

type StatsOverviewProps = {
  summary: StatsSummary;
  sparkbars?: StatsSparkbars;
  uniqueExerciseCount: number;
  setsPerWorkout: number | null;
  repsPerWorkout: number | null;
  rpeLoggedCount: number;
  backPainLoggedCount: number;
  workoutCount: number;
  formatNumber: (value: number | null | undefined, digits?: number) => string;
  formatKg: (value: number | null | undefined) => string;
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

export function StatsRangeToolbar({
  onSelectLimit,
  options,
  selectedLimit,
}: StatsRangeToolbarProps) {
  return (
    <section className="stats-toolbar" aria-label="Stats range">
      <span className="stats-range-label">Last</span>
      <div className="stats-range-control">
        {options.map((option) => (
          <button
            aria-pressed={selectedLimit === option.value}
            className={
              selectedLimit === option.value
                ? "stats-range-button stats-range-button-active"
                : "stats-range-button"
            }
            key={option.value}
            onClick={() => onSelectLimit(option.value)}
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
    </section>
  );
}

export default function StatsOverview({
  backPainLoggedCount,
  formatKg,
  formatNumber,
  repsPerWorkout,
  rpeLoggedCount,
  setsPerWorkout,
  sparkbars,
  summary,
  uniqueExerciseCount,
  workoutCount,
}: StatsOverviewProps) {
  return (
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
    </>
  );
}
