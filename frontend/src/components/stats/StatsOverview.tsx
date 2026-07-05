import type { ReactNode } from "react";

import type { StatsSparkbars, StatsSummary } from "../../api/types";
import MetricCard from "./MetricCard";
import MetricInfo from "./MetricInfo";
import MetricProgressBar from "./MetricProgressBar";
import MetricRangeBar from "./MetricRangeBar";
import MetricRow from "./MetricRow";
import MetricSparkline from "./MetricSparkline";
import type { MetricSparklinePoint } from "./MetricSparkline";
import type { MetricStatus } from "./MetricStatusBadge";

type StatsLimit = 10 | 30 | 90 | "all";

type MetricTone = "green" | "yellow" | "orange" | "red";

type StatsLimitOption = {
  value: StatsLimit;
  label: string;
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

const recoveryZones = [
  { from: 0, to: 40, status: "bad" as const, label: "High stress" },
  { from: 40, to: 70, status: "watch" as const, label: "Moderate" },
  { from: 70, to: 100, status: "good" as const, label: "Good" },
];

const backPainZones = [
  { from: 0, to: 2, status: "good" as const, label: "Low" },
  { from: 2, to: 4, status: "watch" as const, label: "Moderate" },
  { from: 4, to: 7, status: "bad" as const, label: "High" },
  { from: 7, to: 10, status: "bad" as const, label: "Risky" },
];

const tsbZones = [
  { from: -40, to: -25, status: "bad" as const, label: "Very fatigued" },
  { from: -25, to: -10, status: "watch" as const, label: "Fatigued" },
  { from: -10, to: 10, status: "good" as const, label: "Balanced" },
  { from: 10, to: 40, status: "info" as const, label: "Fresh" },
];

const ratioZones = [
  { from: 0, to: 0.8, status: "watch" as const, label: "Low" },
  { from: 0.8, to: 1.3, status: "good" as const, label: "Good" },
  { from: 1.3, to: 1.5, status: "watch" as const, label: "High" },
  { from: 1.5, to: 2, status: "bad" as const, label: "Risky" },
];

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

function backPainStatus(value: number | null | undefined): {
  label: string;
  status: MetricStatus;
} {
  if (value === null || value === undefined) {
    return { label: "No data", status: "neutral" };
  }
  if (value <= 2) {
    return { label: "Low", status: "good" };
  }
  if (value <= 4) {
    return { label: "Watch", status: "watch" };
  }
  return { label: "High", status: "bad" };
}

function recoveryScore(summary: StatsSummary) {
  const rpePenalty = summary.avg_rpe === null ? 20 : summary.avg_rpe * 5;
  const backPenalty =
    summary.avg_back_pain === null ? 20 : summary.avg_back_pain * 7;
  return Math.max(0, Math.min(100, 100 - rpePenalty - backPenalty));
}

function sparkbarToPoints(value: string | undefined): MetricSparklinePoint[] {
  if (!value) {
    return [];
  }

  return Array.from(value).map((char, index) => ({
    date: String(index),
    value: "▁▂▃▄▅▆▇█".indexOf(char) + 1 || 1,
  }));
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
  const recovery = recoveryScore(summary);
  const consistency =
    workoutCount === 0
      ? null
      : ((rpeLoggedCount + backPainLoggedCount) / (workoutCount * 2)) * 100;
  const backPain = summary.avg_back_pain;
  const recoveryStatus =
    recovery >= 70
      ? { label: "Good", status: "good" as const }
      : recovery >= 40
        ? { label: "Watch", status: "watch" as const }
        : { label: "High stress", status: "bad" as const };

  return (
    <>
      <section className="metric-card-grid">
        <MetricCard
          description="Blends average RPE and back pain into a simple recovery view."
          status={recoveryStatus}
          subtitle="RPE and back pain"
          title="Recovery"
          value={`${formatNumber(recovery, 0)}%`}
          visual={
            <MetricProgressBar
              markerLabel={`${formatNumber(recovery, 0)}%`}
              value={recovery}
              zones={recoveryZones}
            />
          }
        />
        <MetricCard
          description="Total app load points in the selected range."
          status={{ label: "Load", status: "info" }}
          subtitle={`${formatNumber(summary.avg_load_score, 1)} average`}
          title="Weekly Load"
          value={formatNumber(summary.total_load_score, 1)}
          visual={<MetricSparkline data={sparkbarToPoints(sparkbars?.load)} />}
        />
        <MetricCard
          description="Average relative strength intensity across eligible sets."
          status={{ label: "Trend", status: "info" }}
          subtitle="Relative intensity"
          title="Strength Progress"
          value={
            summary.avg_relative_intensity === null
              ? "No data"
              : `${formatNumber(summary.avg_relative_intensity, 0)}%`
          }
          visual={<MetricSparkline data={sparkbarToPoints(sparkbars?.intensity)} />}
        />
        <MetricCard
          description={`${backPainLoggedCount}/${workoutCount} workouts include back pain feedback.`}
          status={backPainStatus(backPain)}
          subtitle="Average back pain"
          title="Back Pain Risk"
          value={backPain === null ? "No data" : `${formatNumber(backPain, 1)}/10`}
          visual={
            <MetricRangeBar
              max={10}
              min={0}
              value={backPain}
              valueLabel={backPain === null ? "No data" : `${formatNumber(backPain, 1)}/10`}
              zones={backPainZones}
            />
          }
        />
        <MetricCard
          description="Share of workouts with both RPE and back-pain context available."
          status={{
            label: consistency !== null && consistency >= 80 ? "On Track" : "Watch",
            status: consistency !== null && consistency >= 80 ? "good" : "watch",
          }}
          subtitle="Feedback coverage"
          title="Consistency"
          value={consistency === null ? "No data" : `${formatNumber(consistency, 0)}%`}
          visual={
            <MetricProgressBar
              markerLabel={
                consistency === null ? "No data" : `${formatNumber(consistency, 0)}%`
              }
              value={consistency}
              zones={recoveryZones}
            />
          }
        />
      </section>

      <section className="panel training-load-status-card">
        <div className="panel-header">
          <div>
            <h2>Training load status</h2>
            <p className="muted">
              ATL builds fatigue. CTL reflects fitness. TSB shows how fresh (+)
              or fatigued (-) you are.
            </p>
          </div>
          <MetricInfo>Real ATL, CTL, and TSB values are added in the training load phase.</MetricInfo>
        </div>
        <div className="training-load-placeholder">
          <MetricRow
            description="Short-term fatigue"
            label="ATL"
            status="neutral"
            value="No data"
            visual={<MetricProgressBar value={null} zones={recoveryZones} />}
          />
          <MetricRow
            description="Longer-term base"
            label="CTL"
            status="neutral"
            value="No data"
            visual={<MetricProgressBar value={null} zones={recoveryZones} />}
          />
          <MetricRow
            description="Freshness balance"
            label="TSB"
            status="neutral"
            value="No data"
            visual={<MetricRangeBar max={40} min={-40} value={null} zones={tsbZones} />}
          />
        </div>
      </section>

      <details className="panel metric-calculations-panel">
        <summary>
          <span>Calculations</span>
          <span className="metric-calculation-legend">
            <b className="metric-dot metric-dot-good" /> Good
            <b className="metric-dot metric-dot-watch" /> Moderate
            <b className="metric-dot metric-dot-bad" /> Risk
          </span>
        </summary>
        <MetricRow
          description="Fatigue from recent load"
          label="Fatigue (ATL)"
          status="neutral"
          value="No data"
          visual={<MetricProgressBar value={null} zones={recoveryZones} />}
        />
        <MetricRow
          description="Fitness/base from longer load"
          label="Fitness (CTL)"
          status="neutral"
          value="No data"
          visual={<MetricProgressBar value={null} zones={recoveryZones} />}
        />
        <MetricRow
          description="Freshness minus fatigue"
          label="Stress Balance (TSB)"
          status="neutral"
          value="No data"
          visual={<MetricRangeBar max={40} min={-40} value={null} zones={tsbZones} />}
        />
        <MetricRow
          description="Acute load divided by chronic load"
          label="Workload Ratio (AC)"
          status="neutral"
          value="No data"
          visual={<MetricRangeBar max={2} min={0} value={null} zones={ratioZones} />}
        />
        <MetricRow
          description="How repetitive the last week was"
          label="Monotony"
          status="neutral"
          value="No data"
          visual={<MetricRangeBar max={3} min={0} value={null} zones={ratioZones} />}
        />
        <MetricRow
          description="Weekly load multiplied by monotony"
          label="Training strain"
          status="neutral"
          value="No data"
          visual={<MetricProgressBar value={null} zones={recoveryZones} />}
        />
      </details>

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
