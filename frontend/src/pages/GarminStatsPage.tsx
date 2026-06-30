import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import {
  getGarminStats,
  getGarminStatus,
  syncGarmin,
} from "../api/garmin";

import type {
  GarminStatsPoint,
  GarminStatsRange,
  GarminStatsResponse,
  GarminStatsSignal,
  GarminStatus,
} from "../api/types";

const chartColors = {
  blue: "#0a84ff",
  green: "#30d158",
  orange: "#ff9f0a",
  red: "#ff453a",
  purple: "#af52de",
  yellow: "#ffd60a",
  muted: "#999999",
  grid: "#2e2e2e",
  card: "#171717",
  text: "#f2f2f2",
};

const rangeOptions: Array<{ value: GarminStatsRange; label: string }> = [
  { value: "35", label: "35" },
  { value: "90", label: "90" },
  { value: "180", label: "180" },
  { value: "365", label: "365" },
  { value: "all", label: "All" },
];

type GarminChartPoint = GarminStatsPoint & {
  label: string;
  hrv_ms_rolling_7d: number | null;
  resting_heart_rate_rolling_7d: number | null;
  body_battery_start_rolling_7d: number | null;
  stress_avg_rolling_7d: number | null;
  steps_rolling_7d: number | null;
};

type ChartCardProps = {
  children: ReactNode;
  insight?: ReactNode;
  subtitle?: string;
  title: string;
};

type MetricDomain = [number, number];

type NumericStatsKey = {
  [K in keyof GarminStatsPoint]: GarminStatsPoint[K] extends number | null
    ? K
    : never;
}[keyof GarminStatsPoint];

function parseRange(value: string | null): GarminStatsRange {
  if (
    value === "35" ||
    value === "90" ||
    value === "180" ||
    value === "365" ||
    value === "all"
  ) {
    return value;
  }

  return "90";
}

function formatDate(value: string | null | undefined) {
  if (!value) {
    return "n/a";
  }

  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(new Date(year, month - 1, day));
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "n/a";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatNumber(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }

  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

function formatWithUnit(
  value: number | null | undefined,
  unit: string,
  digits = 0,
) {
  const formatted = formatNumber(value, digits);
  return formatted === "n/a" ? formatted : `${formatted}${unit}`;
}

function latestPoint(stats: GarminStatsResponse | null) {
  if (!stats || stats.series.length === 0) {
    return null;
  }

  return stats.series[stats.series.length - 1];
}

function bodyBatteryValue(point: GarminStatsPoint | null) {
  if (!point) {
    return "n/a";
  }

  const start = formatNumber(point.body_battery_start);
  const end = formatNumber(point.body_battery_end);

  if (start === "n/a" && end === "n/a") {
    return "n/a";
  }

  return `${start} / ${end}`;
}

function statusLabel(status: string | null | undefined) {
  const labels: Record<string, string> = {
    display_only: "Display only",
    fresh: "Today synced",
    good: "Good",
    high: "High",
    historical_only: "Historical only",
    informational: "Informational",
    insufficient_baseline: "Not enough baseline",
    low: "Low",
    missing: "Missing",
    no_data: "No data",
    normal: "Normal",
    not_connected: "Not connected",
    not_enough_data: "Not enough data",
    poor: "Poor",
    very_low: "Very low",
    watch: "Watch",
  };

  return labels[status ?? ""] ?? status ?? "n/a";
}

function metricClassForStatus(status: string | null | undefined) {
  if (status === "good" || status === "normal" || status === "fresh") {
    return "metric-green";
  }
  if (status === "watch" || status === "low" || status === "display_only" || status === "not_enough_data") {
    return "metric-yellow";
  }
  if (status === "historical_only" || status === "insufficient_baseline" || status === "very_low" || status === "high" || status === "not_connected") {
    return "metric-orange";
  }
  if (status === "poor" || status === "missing" || status === "no_data") {
    return "metric-red";
  }

  return "";
}

function metricClassForScore(score: number) {
  if (score > 0) {
    return "metric-green";
  }
  if (score <= -10) {
    return "metric-red";
  }
  if (score < 0) {
    return "metric-orange";
  }

  return "metric-yellow";
}

function statusBadge(status: string | null | undefined) {
  return (
    <span className={`status-badge ${metricClassForStatus(status)}`}>
      {statusLabel(status)}
    </span>
  );
}

function formatScoreDelta(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "n/a";
  }

  return value > 0 ? `+${value}` : String(value);
}

function signalByMetric(stats: GarminStatsResponse, metric: string) {
  return stats.insights.signals.find((signal) => signal.metric === metric) ?? null;
}

function signalDigits(signal: GarminStatsSignal) {
  if (signal.metric === "hrv_ms") {
    return 1;
  }
  if (signal.metric === "delta_percent") {
    return 1;
  }

  return 0;
}

function formatSignalValue(
  value: number | null | undefined,
  signal: Pick<GarminStatsSignal, "metric" | "unit">,
  digits = signal.metric === "hrv_ms" ? 1 : 0,
) {
  if (value === null || value === undefined) {
    return "n/a";
  }

  const unit = signal.unit ? ` ${signal.unit}` : "";
  return `${formatNumber(value, digits)}${unit}`;
}

function formatSignalDelta(signal: GarminStatsSignal) {
  if (signal.status === "display_only") {
    return "Display-only partial day";
  }
  if (signal.status === "missing") {
    return "No current value for the scoring date";
  }
  if (signal.status === "insufficient_baseline") {
    return `Needs ${signal.baseline_sample_count}/${7} baseline samples`;
  }
  if (signal.delta === null || signal.baseline_median === null) {
    return signal.message;
  }

  const baseline = formatSignalValue(signal.baseline_median, signal, signalDigits(signal));
  const delta = signal.delta > 0
    ? `+${formatSignalValue(signal.delta, signal, signalDigits(signal))}`
    : formatSignalValue(signal.delta, signal, signalDigits(signal));

  if (signal.delta_percent !== null && signal.metric !== "resting_heart_rate") {
    const percent = signal.delta_percent > 0
      ? `+${formatNumber(signal.delta_percent, 1)}%`
      : `${formatNumber(signal.delta_percent, 1)}%`;
    return `${percent} vs ${baseline} median`;
  }

  return `${delta} vs ${baseline} median`;
}

function baselineSampleLabel(signal: GarminStatsSignal) {
  return `${signal.baseline_sample_count} baseline samples`;
}

function tooltipFormatter(value: unknown, name: unknown): [ReactNode, string] {
  const labels: Record<string, string> = {
    hrv_ms: "HRV",
    hrv_ms_rolling_7d: "HRV 7d median",
    resting_heart_rate: "Resting HR",
    resting_heart_rate_rolling_7d: "Resting HR 7d avg",
    body_battery_start: "Body Battery start",
    body_battery_start_rolling_7d: "Body Battery 7d avg",
    body_battery_end: "Body Battery end",
    stress_avg: "Stress avg",
    stress_avg_rolling_7d: "Stress 7d avg",
    steps: "Steps",
    steps_rolling_7d: "Steps 7d avg",
  };
  const units: Record<string, string> = {
    hrv_ms: " ms",
    hrv_ms_rolling_7d: " ms",
    resting_heart_rate: " bpm",
    resting_heart_rate_rolling_7d: " bpm",
    body_battery_start: "",
    body_battery_start_rolling_7d: "",
    body_battery_end: "",
    stress_avg: "",
    stress_avg_rolling_7d: "",
    steps: "",
    steps_rolling_7d: "",
  };
  const key = String(name);
  const numericValue = typeof value === "number" ? value : null;
  const digits = key.startsWith("hrv_ms") ? 1 : 0;

  return [formatWithUnit(numericValue, units[key] ?? "", digits), labels[key] ?? key];
}

function ChartCard({ children, insight, subtitle, title }: ChartCardProps) {
  return (
    <section className="chart-card">
      <div className="chart-heading">
        <h2>{title}</h2>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      <div className="chart-frame">{children}</div>
      {insight && <div className="chart-insight">{insight}</div>}
    </section>
  );
}

function commonAxisProps() {
  return {
    stroke: chartColors.muted,
    tick: { fill: chartColors.muted, fontSize: 12 },
  };
}

function numericChartValues(
  data: GarminChartPoint[],
  key: keyof GarminChartPoint,
) {
  return data.reduce<number[]>((values, point) => {
    const value = point[key];
    if (typeof value === "number") {
      values.push(value);
    }
    return values;
  }, []);
}

function paddedDomain(
  values: number[],
  fallback: MetricDomain,
  minPadding: number,
): MetricDomain {
  if (values.length === 0) {
    return fallback;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(max - min, minPadding);
  const padding = Math.max(spread * 0.28, minPadding);

  return [Math.max(0, Math.floor(min - padding)), Math.ceil(max + padding)];
}

function median(values: number[]) {
  if (values.length === 0) {
    return null;
  }

  const sorted = [...values].sort((first, second) => first - second);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) {
    return (sorted[middle - 1] + sorted[middle]) / 2;
  }

  return sorted[middle];
}

function average(values: number[]) {
  if (values.length === 0) {
    return null;
  }

  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function rollingMetric(
  points: GarminStatsPoint[],
  key: NumericStatsKey,
  mode: "average" | "median",
  digits = 0,
) {
  return points.map((_point, index) => {
    const windowPoints = points.slice(Math.max(0, index - 6), index + 1);
    const values = windowPoints.reduce<number[]>((acc, point) => {
      const value = point[key];
      if (typeof value === "number") {
        acc.push(value);
      }
      return acc;
    }, []);

    const rawValue = mode === "median" ? median(values) : average(values);
    if (rawValue === null) {
      return null;
    }

    return Number(rawValue.toFixed(digits));
  });
}

function hrvZones(baseline: number | null) {
  if (baseline === null || baseline <= 0) {
    return null;
  }

  return {
    poorMax: baseline * 0.85,
    watchMax: baseline * 0.95,
    normalMax: baseline * 1.05,
  };
}

function hrvDomain(data: GarminChartPoint[], baseline: number | null): MetricDomain {
  const values = [
    ...numericChartValues(data, "hrv_ms"),
    ...numericChartValues(data, "hrv_ms_rolling_7d"),
  ];
  const zones = hrvZones(baseline);
  const domainValues = zones && baseline !== null
    ? [...values, baseline * 0.75, baseline * 1.15]
    : values;
  return paddedDomain(domainValues, [20, 100], 6);
}

function rhrRanges(baseline: number | null) {
  if (baseline === null || baseline <= 0) {
    return null;
  }

  return {
    normalMax: baseline + 3,
    watchMax: baseline + 7,
  };
}

function restingHeartRateDomain(
  data: GarminChartPoint[],
  baseline: number | null,
): MetricDomain {
  const values = [
    ...numericChartValues(data, "resting_heart_rate"),
    ...numericChartValues(data, "resting_heart_rate_rolling_7d"),
  ];
  const ranges = rhrRanges(baseline);
  const domainValues = ranges && baseline !== null
    ? [...values, baseline - 10, ranges.normalMax, ranges.watchMax, baseline + 14]
    : values;
  return paddedDomain(domainValues, [45, 85], 4);
}

function stressColor(value: number | null | undefined) {
  if (typeof value !== "number") {
    return chartColors.muted;
  }
  if (value <= 25) {
    return chartColors.blue;
  }
  if (value <= 50) {
    return chartColors.green;
  }
  if (value <= 75) {
    return chartColors.orange;
  }
  return chartColors.red;
}

function baselineLine(value: number | null, label: string) {
  if (value === null) {
    return null;
  }

  return (
    <ReferenceLine
      label={{
        value: label,
        position: "insideTopRight",
        fill: chartColors.orange,
        fontSize: 12,
      }}
      stroke={chartColors.orange}
      strokeDasharray="5 5"
      y={value}
    />
  );
}

function dateMarker(date: string | null | undefined, label: string) {
  if (!date) {
    return null;
  }

  return (
    <ReferenceLine
      label={{
        value: label,
        position: "insideTopLeft",
        fill: chartColors.yellow,
        fontSize: 12,
      }}
      stroke={chartColors.yellow}
      strokeDasharray="3 5"
      x={formatDate(date)}
    />
  );
}

function hrvRangeAreas(domain: MetricDomain, baseline: number | null) {
  const zones = hrvZones(baseline);
  if (!zones) {
    return null;
  }

  return (
    <>
      <ReferenceArea fill="rgba(255, 69, 58, 0.13)" y1={domain[0]} y2={zones.poorMax} />
      <ReferenceArea fill="rgba(255, 159, 10, 0.12)" y1={zones.poorMax} y2={zones.watchMax} />
      <ReferenceArea fill="rgba(48, 209, 88, 0.11)" y1={zones.watchMax} y2={zones.normalMax} />
      <ReferenceArea fill="rgba(10, 132, 255, 0.08)" y1={zones.normalMax} y2={domain[1]} />
      <ReferenceLine
        label={{
          value: "0.85x",
          position: "insideBottomRight",
          fill: chartColors.red,
          fontSize: 12,
        }}
        stroke={chartColors.red}
        strokeDasharray="4 4"
        y={zones.poorMax}
      />
      <ReferenceLine stroke={chartColors.orange} strokeDasharray="4 4" y={zones.watchMax} />
      <ReferenceLine stroke={chartColors.green} strokeDasharray="4 4" y={zones.normalMax} />
    </>
  );
}

function restingHeartRateAreas(domain: MetricDomain, baseline: number | null) {
  const ranges = rhrRanges(baseline);
  if (!ranges) {
    return null;
  }

  return (
    <>
      <ReferenceArea fill="rgba(48, 209, 88, 0.12)" y1={domain[0]} y2={ranges.normalMax} />
      <ReferenceArea fill="rgba(255, 214, 10, 0.12)" y1={ranges.normalMax} y2={ranges.watchMax} />
      <ReferenceArea fill="rgba(255, 69, 58, 0.13)" y1={ranges.watchMax} y2={domain[1]} />
      <ReferenceLine
        label={{
          value: "baseline",
          position: "insideTopRight",
          fill: chartColors.orange,
          fontSize: 12,
        }}
        stroke={chartColors.orange}
        strokeDasharray="5 5"
        y={baseline ?? undefined}
      />
    </>
  );
}

function bodyBatteryRangeAreas() {
  return (
    <>
      <ReferenceArea fill="rgba(255, 69, 58, 0.12)" y1={0} y2={25} />
      <ReferenceArea fill="rgba(255, 159, 10, 0.11)" y1={25} y2={50} />
      <ReferenceArea fill="rgba(255, 214, 10, 0.09)" y1={50} y2={75} />
      <ReferenceArea fill="rgba(48, 209, 88, 0.1)" y1={75} y2={100} />
    </>
  );
}

function stressRangeAreas() {
  return (
    <>
      <ReferenceArea fill="rgba(10, 132, 255, 0.1)" y1={0} y2={25} />
      <ReferenceArea fill="rgba(48, 209, 88, 0.1)" y1={25} y2={50} />
      <ReferenceArea fill="rgba(255, 159, 10, 0.1)" y1={50} y2={75} />
      <ReferenceArea fill="rgba(255, 69, 58, 0.12)" y1={75} y2={100} />
    </>
  );
}

function tooltipProps() {
  return {
    contentStyle: {
      background: chartColors.card,
      border: `1px solid ${chartColors.grid}`,
      borderRadius: 8,
      color: chartColors.text,
    },
    formatter: tooltipFormatter,
  };
}

function InsightHeading({ signal }: { signal: GarminStatsSignal | null }) {
  if (!signal) {
    return null;
  }

  return (
    <div className="chart-insight-heading">
      <strong>{signal.label}: {statusLabel(signal.status)}</strong>
      <span>{signal.message}</span>
    </div>
  );
}

function SignalCard({ signal }: { signal: GarminStatsSignal }) {
  const readinessText = signal.used_for_readiness
    ? `Used: ${formatScoreDelta(signal.score_delta)}`
    : signal.status === "display_only"
      ? "Display only"
      : "Informational";

  return (
    <article className={`garmin-signal-card ${metricClassForStatus(signal.status)}`}>
      <div className="garmin-signal-header">
        <strong>{signal.label}</strong>
        {statusBadge(signal.status)}
      </div>
      <div className="garmin-signal-value">
        {formatSignalValue(signal.current, signal, signalDigits(signal))}
      </div>
      <div className="garmin-signal-detail">{formatSignalDelta(signal)}</div>
      <div className="garmin-signal-meta">
        <span>{formatDate(signal.source_date)}</span>
        <span>{baselineSampleLabel(signal)}</span>
        <span>{readinessText}</span>
      </div>
      <p>{signal.message}</p>
    </article>
  );
}

function GarminOverview({ stats, status }: { stats: GarminStatsResponse; status: GarminStatus | undefined }) {
  const readiness = stats.insights.readiness_impact;
  const usedSignals = stats.insights.signals.filter((signal) => signal.used_for_readiness);
  const baselineSamples = usedSignals.length > 0
    ? Math.min(...usedSignals.map((signal) => signal.baseline_sample_count))
    : 0;
  const coverage = stats.coverage.expected_days === null
    ? `${stats.coverage.available_days}`
    : `${stats.coverage.available_days}/${stats.coverage.expected_days}`;

  return (
    <section className="stats-summary-panel garmin-overview-panel">
      <div className="panel-header">
        <div>
          <h2>Garmin overview</h2>
          <p className="muted">{stats.insights.overall_message}</p>
        </div>
        {statusBadge(stats.insights.overall_status)}
      </div>

      <div className="stats-summary-grid garmin-overview-grid">
        <div className={`stats-summary-metric ${metricClassForStatus(stats.insights.overall_status)}`}>
          <strong>{statusLabel(stats.insights.overall_status)}</strong>
          <span>overall</span>
          <small>{formatDate(stats.insights.current_date)}</small>
        </div>
        <div className={`stats-summary-metric ${metricClassForScore(readiness.score_delta)}`}>
          <strong>{formatScoreDelta(readiness.score_delta)}</strong>
          <span>readiness impact</span>
          <small>raw {formatScoreDelta(readiness.raw_score_delta)}</small>
        </div>
        <div className={`stats-summary-metric ${metricClassForStatus(stats.insights.freshness.status)}`}>
          <strong>{statusLabel(stats.insights.freshness.status)}</strong>
          <span>freshness</span>
          <small>{stats.insights.freshness.message}</small>
        </div>
        <div className="stats-summary-metric">
          <strong>{coverage}</strong>
          <span>coverage</span>
          <small>{stats.coverage.missing_days === null ? "all range" : `${stats.coverage.missing_days} missing`}</small>
        </div>
        <div className="stats-summary-metric">
          <strong>{baselineSamples || "n/a"}</strong>
          <span>baseline samples</span>
          <small>{stats.insights.baseline_days}d median</small>
        </div>
        <div className="stats-summary-metric">
          <strong>{readiness.used_metric_count}</strong>
          <span>scored signals</span>
          <small>{readiness.display_only_metric_count} display-only</small>
        </div>
        <div className="stats-summary-metric">
          <strong>{formatDate(stats.latest_metric?.date)}</strong>
          <span>latest row</span>
          <small>{stats.insights.freshness.days_since_latest_metric ?? "n/a"} days old</small>
        </div>
        <div className="stats-summary-metric">
          <strong>{formatDateTime(status?.last_synced_at ?? stats.latest_metric?.synced_at)}</strong>
          <span>last sync</span>
          <small>{status?.connected ? "connected" : "not connected"}</small>
        </div>
      </div>
    </section>
  );
}

function ReadinessImpactPanel({ stats }: { stats: GarminStatsResponse }) {
  const readiness = stats.insights.readiness_impact;
  const usedSignals = stats.insights.signals.filter((signal) => signal.used_for_readiness);
  const displaySignals = stats.insights.signals.filter((signal) => !signal.used_for_readiness);

  return (
    <details className="garmin-impact-panel" open>
      <summary>
        <span>Readiness impact</span>
        <span className={`status-badge ${metricClassForScore(readiness.score_delta)}`}>
          {formatScoreDelta(readiness.score_delta)}
        </span>
      </summary>
      <div className="garmin-impact-content">
        <p>{stats.insights.freshness.message}</p>
        <div className="garmin-impact-columns">
          <div>
            <strong>Used for readiness</strong>
            {usedSignals.length > 0 ? (
              <ul>
                {usedSignals.map((signal) => (
                  <li key={signal.metric}>
                    <span>{signal.label}</span>
                    <b>{formatScoreDelta(signal.score_delta)}</b>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No current Garmin row was scored.</p>
            )}
          </div>
          <div>
            <strong>Display only</strong>
            {displaySignals.length > 0 ? (
              <ul>
                {displaySignals.map((signal) => (
                  <li key={signal.metric}>
                    <span>{signal.label}</span>
                    <b>{statusLabel(signal.status)}</b>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No display-only signals.</p>
            )}
          </div>
          <div>
            <strong>Result</strong>
            <ul>
              <li><span>Raw Garmin delta</span><b>{formatScoreDelta(readiness.raw_score_delta)}</b></li>
              <li><span>Applied Garmin delta</span><b>{formatScoreDelta(readiness.score_delta)}</b></li>
              <li><span>Clamp</span><b>{readiness.min_score_delta}..+{readiness.max_score_delta}</b></li>
            </ul>
          </div>
        </div>
      </div>
    </details>
  );
}

export default function GarminStatsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const range = parseRange(searchParams.get("range"));
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const {
    data: stats,
    error: statsQueryError,
    isLoading: isStatsLoading,
  } = useQuery<GarminStatsResponse>({
    queryKey: ["garmin-stats", range],
    queryFn: () => getGarminStats(range),
  });
  const {
    data: status,
    error: statusQueryError,
    isLoading: isStatusLoading,
  } = useQuery<GarminStatus>({
    queryKey: ["garmin-status"],
    queryFn: getGarminStatus,
  });
  const queryError = statsQueryError ?? statusQueryError;
  const error = syncError ?? (queryError instanceof Error
    ? queryError.message
    : queryError
      ? "Unable to load Garmin stats."
      : null);
  const isLoading = isStatsLoading || isStatusLoading;

  const chartData = useMemo<GarminChartPoint[]>(() => {
    const series = stats?.series ?? [];
    const hrvRolling = rollingMetric(series, "hrv_ms", "median", 1);
    const rhrRolling = rollingMetric(series, "resting_heart_rate", "average", 0);
    const bodyBatteryRolling = rollingMetric(series, "body_battery_start", "average", 0);
    const stressRolling = rollingMetric(series, "stress_avg", "average", 0);
    const stepsRolling = rollingMetric(series, "steps", "average", 0);

    return series.map((point, index) => ({
      ...point,
      body_battery_start_rolling_7d: bodyBatteryRolling[index],
      hrv_ms_rolling_7d: hrvRolling[index],
      label: formatDate(point.date),
      resting_heart_rate_rolling_7d: rhrRolling[index],
      steps_rolling_7d: stepsRolling[index],
      stress_avg_rolling_7d: stressRolling[index],
    }));
  }, [stats]);

  const currentPoint = latestPoint(stats ?? null);
  const hasLowData = Boolean(stats && stats.metric_count > 0 && stats.metric_count < 7);
  const hasNoData = Boolean(stats && stats.metric_count === 0);
  const hrvChartDomain = hrvDomain(chartData, stats?.baselines.hrv_ms ?? null);
  const rhrChartDomain = restingHeartRateDomain(
    chartData,
    stats?.baselines.resting_heart_rate ?? null,
  );
  const hasBodyBatteryData = chartData.some(
    (point) =>
      point.body_battery_start !== null || point.body_battery_end !== null,
  );
  const hrvSignal = stats ? signalByMetric(stats, "hrv_ms") : null;
  const rhrSignal = stats ? signalByMetric(stats, "resting_heart_rate") : null;
  const bodyBatterySignal = stats ? signalByMetric(stats, "body_battery_start") : null;
  const rechargeSignal = stats ? signalByMetric(stats, "overnight_recharge") : null;
  const drainSignal = stats ? signalByMetric(stats, "body_battery_daily_drain") : null;
  const stressSignal = stats ? signalByMetric(stats, "stress_avg") : null;
  const currentStressSignal = stats ? signalByMetric(stats, "current_stress_avg") : null;
  const stepsSignal = stats ? signalByMetric(stats, "steps") : null;
  const stressValues = numericChartValues(chartData, "stress_avg");
  const highStressDays = stressValues.filter((value) => value >= 75).length;
  const averageStress = average(stressValues);
  const stepValues = numericChartValues(chartData, "steps");
  const stepsSevenDayTotal = chartData
    .slice(-7)
    .reduce((total, point) => total + (typeof point.steps === "number" ? point.steps : 0), 0);
  const stepsAverage = average(stepValues);
  const stepsBelowHalfBaseline = stats?.baselines.steps
    ? stepValues.filter((value) => value < (stats.baselines.steps ?? 0) * 0.5).length
    : 0;
  const orderedSignals = stats
    ? [
      "hrv_ms",
      "resting_heart_rate",
      "body_battery_start",
      "stress_avg",
      "current_stress_avg",
      "steps",
      "overnight_recharge",
      "body_battery_daily_drain",
    ]
      .map((metric) => signalByMetric(stats, metric))
      .filter((signal): signal is GarminStatsSignal => Boolean(signal))
    : [];

  function changeRange(nextRange: GarminStatsRange) {
    setSyncError(null);
    navigate(nextRange === "90" ? "/garmin" : `/garmin?range=${nextRange}`);
  }

  async function handleSync() {
    setIsSyncing(true);
    setSyncError(null);

    try {
      await syncGarmin(35);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["garmin-stats"] }),
        queryClient.invalidateQueries({ queryKey: ["garmin-status"] }),
        queryClient.invalidateQueries({ queryKey: ["garmin-daily"] }),
      ]);
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : "Unable to sync Garmin data.");
    } finally {
      setIsSyncing(false);
    }
  }

  return (
    <section className="page-stack garmin-stats-page">
      <div className="page-header garmin-stats-header">
        <div>
          <h1>Garmin stats</h1>
          <p className="muted">Local daily metrics from synced Garmin history.</p>
        </div>

        <div className="garmin-stats-actions">
          <div aria-label="Garmin stats range" className="stats-range-control garmin-range-control">
            {rangeOptions.map((option) => (
              <button
                className={
                  option.value === range
                    ? "stats-range-button stats-range-button-active"
                    : "stats-range-button"
                }
                disabled={isLoading || isSyncing}
                key={option.value}
                onClick={() => changeRange(option.value)}
                type="button"
              >
                {option.label}
              </button>
            ))}
          </div>

          <button
            className="primary-button compact-button"
            disabled={isLoading || isSyncing}
            onClick={handleSync}
            type="button"
          >
            {isSyncing ? "Syncing" : "Sync 35 days"}
          </button>

          <Link className="card-link" to="/settings">Settings</Link>
        </div>
      </div>

      {error && <section className="panel danger-text">{error}</section>}
      {isLoading && <section className="panel">Loading Garmin stats</section>}

      {!isLoading && stats && (
        <>
          <GarminOverview stats={stats} status={status} />

          <section className="panel garmin-signals-panel">
            <div className="panel-header">
              <div>
                <h2>Today readiness signals</h2>
                <p className="muted">Personal-baseline status for the scoring window.</p>
              </div>
              {statusBadge(stats.insights.freshness.status)}
            </div>
            <div className="garmin-signal-grid">
              {orderedSignals.map((signal) => (
                <SignalCard key={signal.metric} signal={signal} />
              ))}
            </div>
          </section>

          <ReadinessImpactPanel stats={stats} />

          <div className="stats-summary-grid garmin-summary-grid">
            <div className="stats-summary-metric">
              <span>latest date</span>
              <strong>{formatDate(stats.latest_metric?.date)}</strong>
            </div>
            <div className="stats-summary-metric">
              <span>last sync</span>
              <strong>{formatDateTime(status?.last_synced_at ?? stats.latest_metric?.synced_at)}</strong>
            </div>
            <div className="stats-summary-metric">
              <span>available days</span>
              <strong>{stats.coverage.available_days}</strong>
            </div>
            <div className="stats-summary-metric">
              <span>missing days</span>
              <strong>{stats.coverage.missing_days === null ? "n/a" : stats.coverage.missing_days}</strong>
            </div>
            <div className="stats-summary-metric">
              <span>current HRV</span>
              <strong>{formatWithUnit(currentPoint?.hrv_ms, " ms", 1)}</strong>
            </div>
            <div className="stats-summary-metric">
              <span>resting HR</span>
              <strong>{formatWithUnit(currentPoint?.resting_heart_rate, " bpm")}</strong>
            </div>
            <div className="stats-summary-metric">
              <span>body battery</span>
              <strong>{bodyBatteryValue(currentPoint)}</strong>
            </div>
            <div className="stats-summary-metric">
              <span>stress avg</span>
              <strong>{formatNumber(currentPoint?.stress_avg)}</strong>
            </div>
          </div>

          {hasNoData && (
            <section className="panel">
              <h2>No Garmin metrics yet</h2>
              <p>Sync Garmin from Settings or use the sync button when connected.</p>
            </section>
          )}

          {hasLowData && (
            <section className="panel garmin-low-data">
              <h2>Low Garmin sample count</h2>
              <p>Charts are visible, but baselines need at least 7 non-empty samples per metric.</p>
            </section>
          )}

          {stats.metric_count > 0 && (
            <div className="garmin-chart-grid">
              <ChartCard
                insight={(
                  <>
                    <InsightHeading signal={hrvSignal} />
                    <div className="chart-insight-scale chart-insight-scale-four">
                      <div><strong>Poor</strong><span>&lt; 0.85x baseline</span></div>
                      <div><strong>Watch</strong><span>0.85x..0.95x</span></div>
                      <div><strong>Normal</strong><span>0.95x..1.05x</span></div>
                      <div><strong>Good</strong><span>&gt; 1.05x baseline</span></div>
                    </div>
                    <div className="chart-insight-details">
                      {hrvSignal && <span>{formatSignalDelta(hrvSignal)}</span>}
                      <span>7-day median line shows the local trend.</span>
                    </div>
                  </>
                )}
                subtitle="Personal baseline zones: poor, watch, normal, and above-baseline good."
                title="HRV"
              >
                <ResponsiveContainer height={260} width="100%">
                  <LineChart data={chartData} margin={{ bottom: 8, left: 0, right: 12, top: 12 }}>
                    <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={18} {...commonAxisProps()} />
                    <YAxis domain={hrvChartDomain} {...commonAxisProps()} />
                    <Tooltip {...tooltipProps()} />
                    {hrvRangeAreas(hrvChartDomain, stats.baselines.hrv_ms)}
                    {baselineLine(stats.baselines.hrv_ms, "median")}
                    {dateMarker(stats.insights.current_date, "scoring")}
                    <Line
                      connectNulls={false}
                      dataKey="hrv_ms"
                      dot={{ r: 2 }}
                      name="HRV"
                      stroke={chartColors.blue}
                      strokeWidth={2}
                      type="monotone"
                    />
                    <Line
                      connectNulls={false}
                      dataKey="hrv_ms_rolling_7d"
                      dot={false}
                      name="HRV 7d median"
                      stroke={chartColors.green}
                      strokeDasharray="5 5"
                      strokeWidth={2}
                      type="monotone"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>

              <ChartCard
                insight={(
                  <>
                    <InsightHeading signal={rhrSignal} />
                    <div className="chart-insight-scale chart-insight-scale-four">
                      <div><strong>Good</strong><span>Below baseline</span></div>
                      <div><strong>Normal</strong><span>up to +3 bpm</span></div>
                      <div><strong>Watch</strong><span>+4..+7 bpm</span></div>
                      <div><strong>Poor</strong><span>+8 bpm or more</span></div>
                    </div>
                    <div className="chart-insight-details">
                      {rhrSignal && <span>{formatSignalDelta(rhrSignal)}</span>}
                      <span>Dynamic Y-axis expands around baseline and recent values.</span>
                    </div>
                  </>
                )}
                subtitle="Dynamic scale with normal, warning, and high bands around local baseline."
                title="Resting heart rate"
              >
                <ResponsiveContainer height={260} width="100%">
                  <LineChart data={chartData} margin={{ bottom: 8, left: 0, right: 12, top: 12 }}>
                    <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={18} {...commonAxisProps()} />
                    <YAxis domain={rhrChartDomain} {...commonAxisProps()} />
                    <Tooltip {...tooltipProps()} />
                    {restingHeartRateAreas(rhrChartDomain, stats.baselines.resting_heart_rate)}
                    {dateMarker(stats.insights.current_date, "scoring")}
                    <Line
                      connectNulls={false}
                      dataKey="resting_heart_rate"
                      dot={{ r: 2 }}
                      name="Resting HR"
                      stroke={chartColors.red}
                      strokeWidth={2}
                      type="monotone"
                    />
                    <Line
                      connectNulls={false}
                      dataKey="resting_heart_rate_rolling_7d"
                      dot={false}
                      name="Resting HR 7d avg"
                      stroke={chartColors.yellow}
                      strokeDasharray="5 5"
                      strokeWidth={2}
                      type="monotone"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>

              <ChartCard
                insight={(
                  <>
                    <InsightHeading signal={bodyBatterySignal} />
                    <div className="chart-insight-scale chart-insight-scale-four">
                      <div><strong>Low</strong><span>0..25</span></div>
                      <div><strong>Limited</strong><span>26..50</span></div>
                      <div><strong>Okay</strong><span>51..75</span></div>
                      <div><strong>High</strong><span>76..100</span></div>
                    </div>
                    <div className="chart-insight-details">
                      {bodyBatterySignal && <span>{formatSignalDelta(bodyBatterySignal)}</span>}
                      {rechargeSignal && <span>{rechargeSignal.label}: {formatSignalValue(rechargeSignal.current, rechargeSignal)}</span>}
                      {drainSignal && <span>{drainSignal.label}: {formatSignalValue(drainSignal.current, drainSignal)}</span>}
                    </div>
                  </>
                )}
                subtitle="Morning and end-of-day values with Garmin-style 0..100 bands."
                title="Body Battery"
              >
                {hasBodyBatteryData ? (
                  <ResponsiveContainer height={260} width="100%">
                    <LineChart data={chartData} margin={{ bottom: 8, left: 0, right: 12, top: 12 }}>
                      <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                      <XAxis dataKey="label" minTickGap={18} {...commonAxisProps()} />
                      <YAxis domain={[0, 100]} {...commonAxisProps()} />
                      <Tooltip {...tooltipProps()} />
                      <Legend />
                      {bodyBatteryRangeAreas()}
                      {baselineLine(stats.baselines.body_battery_start, "start median")}
                      {dateMarker(stats.insights.current_date, "scoring")}
                      <Line
                        connectNulls={false}
                        dataKey="body_battery_start"
                        dot={{ r: 2 }}
                        name="Body Battery start"
                        stroke={chartColors.green}
                        strokeWidth={2}
                        type="monotone"
                      />
                      <Line
                        connectNulls={false}
                        dataKey="body_battery_end"
                        dot={{ r: 2 }}
                        name="Body Battery end"
                        stroke={chartColors.orange}
                        strokeWidth={2}
                        type="monotone"
                      />
                      <Line
                        connectNulls={false}
                        dataKey="body_battery_start_rolling_7d"
                        dot={false}
                        name="Body Battery 7d avg"
                        stroke={chartColors.blue}
                        strokeDasharray="5 5"
                        strokeWidth={2}
                        type="monotone"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="garmin-chart-empty">No Body Battery values in synced rows.</div>
                )}
              </ChartCard>

              <ChartCard
                insight={(
                  <>
                    <InsightHeading signal={stressSignal} />
                    <div className="chart-insight-metrics">
                      <div><strong>{highStressDays}</strong><span>high-stress days in range</span></div>
                      <div><strong>{formatNumber(averageStress)}</strong><span>average stress in range</span></div>
                      <div><strong>{currentStressSignal ? statusLabel(currentStressSignal.status) : "n/a"}</strong><span>current-day stress status</span></div>
                    </div>
                    <div className="chart-insight-details">
                      {stressSignal && <span>{formatSignalDelta(stressSignal)}</span>}
                      <span>Previous-day stress is scored; current-day stress remains display-only.</span>
                    </div>
                  </>
                )}
                subtitle="Garmin-style stress bands: rest, low, medium, and high."
                title="Stress"
              >
                <ResponsiveContainer height={260} width="100%">
                  <BarChart data={chartData} margin={{ bottom: 8, left: 0, right: 12, top: 12 }}>
                    <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={18} {...commonAxisProps()} />
                    <YAxis domain={[0, 100]} {...commonAxisProps()} />
                    <Tooltip {...tooltipProps()} />
                    {stressRangeAreas()}
                    {baselineLine(stats.baselines.stress_avg, "median")}
                    {dateMarker(stats.insights.previous_date, "scored stress")}
                    <Bar dataKey="stress_avg" name="Stress avg" radius={[4, 4, 0, 0]}>
                      {chartData.map((point) => (
                        <Cell fill={stressColor(point.stress_avg)} key={point.date} />
                      ))}
                    </Bar>
                    <Line
                      connectNulls={false}
                      dataKey="stress_avg_rolling_7d"
                      dot={false}
                      name="Stress 7d avg"
                      stroke={chartColors.text}
                      strokeDasharray="5 5"
                      strokeWidth={2}
                      type="monotone"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>

              <ChartCard
                insight={(
                  <>
                    <InsightHeading signal={stepsSignal} />
                    <div className="chart-insight-metrics">
                      <div><strong>{formatNumber(stepsSevenDayTotal)}</strong><span>7-day total</span></div>
                      <div><strong>{formatNumber(stepsAverage)}</strong><span>average per synced day</span></div>
                      <div><strong>{stepsBelowHalfBaseline}</strong><span>days below 50% baseline</span></div>
                    </div>
                    <div className="chart-insight-details">
                      {stepsSignal && <span>{formatSignalDelta(stepsSignal)}</span>}
                      <span>Steps are informational and do not change readiness.</span>
                    </div>
                  </>
                )}
                subtitle="Step count with 28-day median and neutral trend context."
                title="Steps"
              >
                <ResponsiveContainer height={260} width="100%">
                  <BarChart data={chartData} margin={{ bottom: 8, left: 0, right: 12, top: 12 }}>
                    <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={18} {...commonAxisProps()} />
                    <YAxis {...commonAxisProps()} />
                    <Tooltip {...tooltipProps()} />
                    {baselineLine(stats.baselines.steps, "28d median")}
                    <Bar dataKey="steps" fill={chartColors.blue} name="Steps" radius={[4, 4, 0, 0]} />
                    <Line
                      connectNulls={false}
                      dataKey="steps_rolling_7d"
                      dot={false}
                      name="Steps 7d avg"
                      stroke={chartColors.green}
                      strokeDasharray="5 5"
                      strokeWidth={2}
                      type="monotone"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
            </div>
          )}
        </>
      )}
    </section>
  );
}
