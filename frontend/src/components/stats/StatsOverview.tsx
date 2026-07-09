import type { ReactNode } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  MetricZone,
  StatsSparkbars,
  StatsSummary,
  TrainingLoadMetric,
  TrainingLoadSummary,
} from "../../api/types";
import {
  formatChartDateTick,
  formatChartDateTooltip,
} from "../../utils/chartDateFormat";
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
  trainingLoad?: TrainingLoadSummary;
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

const consistencyZones = [
  { from: 0, to: 50, status: "bad" as const, label: "Low" },
  { from: 50, to: 80, status: "watch" as const, label: "Partial" },
  { from: 80, to: 100, status: "good" as const, label: "Good" },
];

function StatsIcon({
  type,
}: {
  type: "recovery" | "load" | "strength" | "pain" | "consistency";
}) {
  if (type === "recovery") {
    return (
      <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
        <path d="M4 12h4l2-5 4 10 2-5h4" />
      </svg>
    );
  }

  if (type === "load") {
    return (
      <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
        <path d="M4 9v6M8 7v10M8 12h8M16 7v10M20 9v6" />
      </svg>
    );
  }

  if (type === "strength") {
    return (
      <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
        <path d="M4 17l5-5 4 4 7-9" />
        <path d="M15 7h5v5" />
      </svg>
    );
  }

  if (type === "pain") {
    return (
      <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
        <path d="M12 4l9 16H3L12 4z" />
        <path d="M12 9v5M12 17h.01" />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
      <path d="M7 3v4M17 3v4M4 9h16" />
      <path d="M5 5h14v15H5z" />
      <path d="M8 14l2 2 5-5" />
    </svg>
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

const SPARK_CHARS_INC = " ⢀⣀⣠⣤⣴⣶⣾⣿";
const SPARK_CHARS_DEC = "⣿⣷⣶⣦⣤⣄⣀⡀ ";

function sparkbarToPoints(value: string | undefined): MetricSparklinePoint[] {
  if (!value || value === "—") {
    return [];
  }

  return Array.from(value).map((char, index) => {
    const incIndex = SPARK_CHARS_INC.indexOf(char);

    if (incIndex >= 0) {
      return {
        date: String(index),
        value: incIndex + 1,
      };
    }

    const decIndex = SPARK_CHARS_DEC.indexOf(char);

    if (decIndex >= 0) {
      return {
        date: String(index),
        value: SPARK_CHARS_DEC.length - decIndex,
      };
    }

    if (char === "·") {
      return {
        date: String(index),
        value: 0,
      };
    }

    return {
      date: String(index),
      value: 1,
    };
  });
}

function statusLabel(status: MetricStatus) {
  if (status === "neutral") {
    return "No data";
  }

  if (status === "good") {
    return "Good";
  }

  if (status === "watch") {
    return "Watch";
  }

  if (status === "bad") {
    return "Risk";
  }

  return "Info";
}

function toMetricZones(zones: MetricZone[]) {
  return zones.map((zone) => ({
    from: zone.from_value,
    to: zone.to_value,
    status: zone.status,
    label: zone.label,
  }));
}

function metricVisual(metric: TrainingLoadMetric | undefined) {
  if (!metric) {
    return (
      <MetricProgressBar
        showValueLabel={false}
        size="sm"
        value={null}
        zones={recoveryZones}
      />
    );
  }

  const zones = toMetricZones(metric.zones);
  const value = metric.percent ?? metric.value;

  if (
    metric.key === "tsb" ||
    metric.key === "ac_ratio" ||
    metric.key === "monotony"
  ) {
    return (
      <MetricRangeBar
        max={metric.max}
        min={metric.min}
        showValueLabel={false}
        size="sm"
        value={metric.value}
        zones={zones.length > 0 ? zones : ratioZones}
      />
    );
  }

  return (
    <MetricProgressBar
      showValueLabel={false}
      size="sm"
      value={value}
      zones={zones.length > 0 ? zones : recoveryZones}
    />
  );
}

function TrainingLoadMetricRow({
  fallbackDescription,
  fallbackLabel,
  label,
  metric,
}: {
  fallbackDescription: string;
  fallbackLabel: string;
  label?: string;
  metric?: TrainingLoadMetric;
}) {
  const description =
    metric?.key === "ac_ratio" &&
    metric.value !== null &&
    metric.value !== undefined &&
    metric.value < 0.8
      ? "Recent load is low versus your longer-term base."
      : metric?.description ?? fallbackDescription;

  return (
    <MetricRow
      description={description}
      label={label ?? metric?.label ?? fallbackLabel}
      status={metric?.status ?? "neutral"}
      value={metric?.formatted ?? "No data"}
      visual={metricVisual(metric)}
    />
  );
}

function TrainingLoadChip({
  label,
  metric,
  tone,
}: {
  label: string;
  metric?: TrainingLoadMetric;
  tone: "atl" | "ctl" | "tsb";
}) {
  return (
    <div className={`training-load-chip training-load-chip-${tone}`}>
      <span>{label}</span>
      <strong>{metric?.formatted ?? "No data"}</strong>
      <small>{statusLabel(metric?.status ?? "neutral")}</small>
    </div>
  );
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
  trainingLoad,
  uniqueExerciseCount,
  workoutCount,
}: StatsOverviewProps) {
  const metricByKey = new Map(
    (trainingLoad?.metrics ?? []).map((metric) => [metric.key, metric]),
  );
  const atlMetric = metricByKey.get("atl");
  const ctlMetric = metricByKey.get("ctl");
  const tsbMetric = metricByKey.get("tsb");
  const acMetric = metricByKey.get("ac_ratio");
  const monotonyMetric = metricByKey.get("monotony");
  const strainMetric = metricByKey.get("training_strain");
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
  const weeklyLoadValue =
    trainingLoad?.weekly_load === null ||
    trainingLoad?.weekly_load === undefined ||
    trainingLoad.weekly_load <= 0
      ? "No recent load"
      : formatNumber(trainingLoad.weekly_load, 1);

  return (
    <>
      <section className="metric-card-grid">
        <MetricCard
          description="Combined session feedback from RPE and back pain."
          icon={<StatsIcon type="recovery" />}
          status={recoveryStatus}
          subtitle="RPE + back pain"
          tone="recovery"
          title="Recovery"
          value={`${formatNumber(recovery, 0)}%`}
          visual={
            <MetricProgressBar
              edgeLabels={{ left: "0%", center: "50%", right: "100%" }}
              markerLabel={`${formatNumber(recovery, 0)}%`}
              showEdgeLabels
              tone="recovery"
              value={recovery}
              zones={recoveryZones}
            />
          }
        />
        <MetricCard
          description="Load from the last 7 local days."
          icon={<StatsIcon type="load" />}
          status={{
            label: statusLabel(atlMetric?.status ?? "neutral"),
            status: atlMetric?.status ?? "neutral",
          }}
          subtitle="Including rest days"
          tone="load"
          title="7-day Load"
          value={weeklyLoadValue}
          visual={
            <MetricSparkline
              data={sparkbarToPoints(sparkbars?.load)}
              label="Load trend"
              tone="load"
            />
          }
        />
        <MetricCard
          description="Average relative strength intensity across eligible sets."
          icon={<StatsIcon type="strength" />}
          status={{ label: "Info", status: "info" }}
          subtitle="Average e1RM context"
          tone="strength"
          title="Strength Intensity"
          value={
            summary.avg_relative_intensity === null
              ? "No data"
              : `${formatNumber(summary.avg_relative_intensity, 0)}%`
          }
          visual={
            <MetricSparkline
              data={sparkbarToPoints(sparkbars?.intensity)}
              label="Strength intensity trend"
              tone="strength"
            />
          }
        />
        <MetricCard
          description="Average reported back pain across logged workouts."
          icon={<StatsIcon type="pain" />}
          status={backPainStatus(backPain)}
          subtitle="Average back pain"
          tone="pain"
          title="Back Pain Risk"
          value={backPain === null ? "No data" : `${formatNumber(backPain, 1)}/10`}
          visual={
            <MetricRangeBar
              edgeLabels={{ left: "Low", center: "Moderate", right: "High" }}
              max={10}
              min={0}
              showEdgeLabels
              tone="pain"
              value={backPain}
              valueLabel={backPain === null ? "No data" : `${formatNumber(backPain, 1)}/10`}
              zones={backPainZones}
            />
          }
        />
        <MetricCard
          description="Workouts with both RPE and back-pain feedback."
          icon={<StatsIcon type="consistency" />}
          status={{
            label:
              consistency === null
                ? "No data"
                : consistency >= 80
                  ? "Good"
                  : consistency >= 50
                    ? "Watch"
                    : "Risk",
            status:
              consistency === null
                ? "neutral"
                : consistency >= 80
                  ? "good"
                  : consistency >= 50
                    ? "watch"
                    : "bad",
          }}
          subtitle="Feedback coverage"
          tone="consistency"
          title="Consistency"
          value={consistency === null ? "No data" : `${formatNumber(consistency, 0)}%`}
          visual={
            <MetricProgressBar
              edgeLabels={{ left: "Low", center: "Partial", right: "Good" }}
              markerLabel={
                consistency === null ? "No data" : `${formatNumber(consistency, 0)}%`
              }
              showEdgeLabels
              tone="strength"
              value={consistency}
              zones={consistencyZones}
            />
          }
        />
      </section>

      <section className="stats-main-grid">
        <section className="panel training-load-status-card">
          <div className="panel-header training-load-header">
            <div>
              <h2>Training load status</h2>
              <p className="muted">
                Short-term load reacts quickly. Long-term load shows the base.
                Freshness compares the two.
              </p>
            </div>
            <MetricInfo>Daily load includes rest days through today.</MetricInfo>
          </div>
          <div className="training-load-legend" aria-label="Training load legend">
            <span className="legend-atl">Short-term load (ATL)</span>
            <span className="legend-ctl">Long-term load (CTL)</span>
            <span className="legend-tsb">Freshness (TSB)</span>
          </div>
          {trainingLoad && trainingLoad.series.length > 0 ? (
            <div className="training-load-chart">
              <ResponsiveContainer height={240} width="100%">
                <LineChart
                  data={trainingLoad.series}
                  margin={{ top: 12, right: 12, bottom: 0, left: 0 }}
                >
                  <CartesianGrid stroke="#2e2e2e" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    minTickGap={24}
                    tickFormatter={(value) => formatChartDateTick(String(value))}
                  />
                  <YAxis width={42} />
                  <Tooltip
                    formatter={(value, name) => [
                      typeof value === "number"
                        ? formatNumber(value, 1)
                        : String(value),
                      String(name),
                    ]}
                    labelFormatter={(value) =>
                      formatChartDateTooltip(String(value))
                    }
                  />
                  <Line
                    dataKey="atl"
                    dot={false}
                    name="Short-term load (ATL)"
                    stroke="var(--stats-atl)"
                    strokeWidth={2.5}
                    type="monotone"
                  />
                  <Line
                    dataKey="ctl"
                    dot={false}
                    name="Long-term load (CTL)"
                    stroke="var(--stats-ctl)"
                    strokeWidth={2.5}
                    type="monotone"
                  />
                  <Line
                    dataKey="tsb"
                    dot={false}
                    name="Freshness (TSB)"
                    stroke="var(--stats-tsb)"
                    strokeWidth={2.5}
                    type="monotone"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="training-load-empty">No load data yet</div>
          )}
          <div className="training-load-chip-grid">
            <TrainingLoadChip label="Short-term" metric={atlMetric} tone="atl" />
            <TrainingLoadChip label="Long-term" metric={ctlMetric} tone="ctl" />
            <TrainingLoadChip label="Freshness" metric={tsbMetric} tone="tsb" />
          </div>
        </section>

        <details className="panel metric-calculations-panel" open>
          <summary>
            <span>Calculations</span>
            <span className="metric-calculation-legend">
              <b className="metric-dot metric-dot-good" /> Good
              <b className="metric-dot metric-dot-watch" /> Watch
              <b className="metric-dot metric-dot-bad" /> Risk
            </span>
          </summary>
          <div className="metric-row-list">
            <TrainingLoadMetricRow
              fallbackDescription="Fatigue from recent load"
              fallbackLabel="Short-term load"
              label="Short-term load"
              metric={atlMetric}
            />
            <TrainingLoadMetricRow
              fallbackDescription="Fitness/base from longer load"
              fallbackLabel="Long-term load"
              label="Long-term load"
              metric={ctlMetric}
            />
            <TrainingLoadMetricRow
              fallbackDescription="Freshness minus fatigue"
              fallbackLabel="Freshness"
              label="Freshness"
              metric={tsbMetric}
            />
            <TrainingLoadMetricRow
              fallbackDescription="Acute load divided by chronic load"
              fallbackLabel="AC ratio"
              label="AC ratio"
              metric={acMetric}
            />
            <TrainingLoadMetricRow
              fallbackDescription="How repetitive the last week was"
              fallbackLabel="Monotony"
              label="Monotony"
              metric={monotonyMetric}
            />
            <TrainingLoadMetricRow
              fallbackDescription="Weekly load multiplied by monotony"
              fallbackLabel="Training strain"
              label="Training strain"
              metric={strainMetric}
            />
          </div>
        </details>
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
            label="kg volume"
            value={formatKg(summary.total_volume_kg)}
          />

          <SummaryMetric
            label="bodyweight reps"
            value={formatNumber(summary.bodyweight_reps)}
          />

          <SummaryMetric
            label="kg / weighted rep"
            value={formatNumber(summary.avg_kg_per_rep, 1)}
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
