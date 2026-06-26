import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  getGarminStats,
  getGarminStatus,
  syncGarmin,
} from "../api/garmin";

import type {
  GarminStatsPoint,
  GarminStatsRange,
  GarminStatsResponse,
  GarminStatus,
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

const rangeOptions: Array<{ value: GarminStatsRange; label: string }> = [
  { value: "35", label: "35" },
  { value: "90", label: "90" },
  { value: "180", label: "180" },
  { value: "365", label: "365" },
  { value: "all", label: "All" },
];

type GarminChartPoint = GarminStatsPoint & {
  label: string;
};

type ChartCardProps = {
  children: ReactNode;
  subtitle?: string;
  title: string;
  wide?: boolean;
};

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

function readRangeFromUrl() {
  return parseRange(new URLSearchParams(window.location.search).get("range"));
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

  return Number(value).toFixed(digits);
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

function coverageSubvalue(stats: GarminStatsResponse | null) {
  if (!stats) {
    return "loading";
  }

  if (stats.coverage.expected_days === null) {
    return "all local days";
  }

  return `of ${stats.coverage.expected_days} days`;
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

function tooltipFormatter(value: unknown, name: unknown): [ReactNode, string] {
  const labels: Record<string, string> = {
    hrv_ms: "HRV",
    resting_heart_rate: "Resting HR",
    body_battery_start: "Body Battery start",
    body_battery_end: "Body Battery end",
    stress_avg: "Stress avg",
    steps: "Steps",
  };
  const units: Record<string, string> = {
    hrv_ms: " ms",
    resting_heart_rate: " bpm",
    body_battery_start: "",
    body_battery_end: "",
    stress_avg: "",
    steps: "",
  };
  const key = String(name);
  const numericValue = typeof value === "number" ? value : null;

  return [
    formatWithUnit(numericValue, units[key] ?? "", key === "hrv_ms" ? 1 : 0),
    labels[key] ?? key,
  ];
}

function ChartCard({ children, subtitle, title, wide = false }: ChartCardProps) {
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

function commonAxisProps() {
  return {
    stroke: chartColors.muted,
    tick: { fill: chartColors.muted, fontSize: 12 },
  };
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

export default function GarminStatsPage() {
  const [range, setRange] = useState<GarminStatsRange>(() => readRangeFromUrl());
  const [stats, setStats] = useState<GarminStatsResponse | null>(null);
  const [status, setStatus] = useState<GarminStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chartData = useMemo<GarminChartPoint[]>(
    () =>
      (stats?.series ?? []).map((point) => ({
        ...point,
        label: formatDate(point.date),
      })),
    [stats],
  );

  const currentPoint = latestPoint(stats);
  const hasLowData = Boolean(stats && stats.metric_count > 0 && stats.metric_count < 7);
  const hasNoData = Boolean(stats && stats.metric_count === 0);

  async function load(nextRange: GarminStatsRange, options = { showLoading: true }) {
    if (options.showLoading) {
      setIsLoading(true);
    }
    setError(null);

    try {
      const [nextStats, nextStatus] = await Promise.all([
        getGarminStats(nextRange),
        getGarminStatus(),
      ]);
      setStats(nextStats);
      setStatus(nextStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load Garmin stats.");
    } finally {
      if (options.showLoading) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    Promise.all([getGarminStats(range), getGarminStatus()])
      .then(([nextStats, nextStatus]) => {
        if (!cancelled) {
          setStats(nextStats);
          setStatus(nextStatus);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to load Garmin stats.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [range]);

  useEffect(() => {
    function syncRangeFromUrl() {
      setRange(readRangeFromUrl());
    }

    window.addEventListener("popstate", syncRangeFromUrl);
    return () => window.removeEventListener("popstate", syncRangeFromUrl);
  }, []);

  function changeRange(nextRange: GarminStatsRange) {
    setRange(nextRange);
    const path = nextRange === "90" ? "/garmin" : `/garmin?range=${nextRange}`;
    window.history.pushState(null, "", path);
  }

  async function handleSync() {
    setIsSyncing(true);
    setError(null);

    try {
      await syncGarmin(35);
      await load(range, { showLoading: false });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sync Garmin data.");
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

          <a className="card-link" href="/settings">Settings</a>
        </div>
      </div>

      {error && <section className="panel danger-text">{error}</section>}
      {isLoading && <section className="panel">Loading Garmin stats</section>}

      {!isLoading && stats && (
        <>
          <div className="dashboard-grid garmin-summary-grid">
            <div className="dashboard-card">
              <div className="dashboard-label">Latest date</div>
              <div className="dashboard-value">{formatDate(stats.latest_metric?.date)}</div>
              <div className="dashboard-subvalue">{stats.range} range</div>
            </div>
            <div className="dashboard-card">
              <div className="dashboard-label">Last sync</div>
              <div className="dashboard-value">
                {formatDateTime(status?.last_synced_at ?? stats.latest_metric?.synced_at)}
              </div>
              <div className="dashboard-subvalue">
                {status?.connected ? "connected" : "local history"}
              </div>
            </div>
            <div className="dashboard-card">
              <div className="dashboard-label">Available days</div>
              <div className="dashboard-value">{stats.coverage.available_days}</div>
              <div className="dashboard-subvalue">{coverageSubvalue(stats)}</div>
            </div>
            <div className="dashboard-card">
              <div className="dashboard-label">Missing days</div>
              <div className="dashboard-value">
                {stats.coverage.missing_days === null ? "n/a" : stats.coverage.missing_days}
              </div>
              <div className="dashboard-subvalue">not synced in range</div>
            </div>
            <div className="dashboard-card">
              <div className="dashboard-label">Current HRV</div>
              <div className="dashboard-value">{formatWithUnit(currentPoint?.hrv_ms, " ms", 1)}</div>
              <div className="dashboard-subvalue">latest local metric</div>
            </div>
            <div className="dashboard-card">
              <div className="dashboard-label">Current resting HR</div>
              <div className="dashboard-value">{formatWithUnit(currentPoint?.resting_heart_rate, " bpm")}</div>
              <div className="dashboard-subvalue">latest local metric</div>
            </div>
            <div className="dashboard-card">
              <div className="dashboard-label">Current Body Battery</div>
              <div className="dashboard-value">{bodyBatteryValue(currentPoint)}</div>
              <div className="dashboard-subvalue">start / end</div>
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
            <div className="stats-chart-grid">
              <ChartCard
                subtitle="Nightly HRV with 28-day median baseline when enough samples exist."
                title="HRV"
                wide
              >
                <ResponsiveContainer height={260} width="100%">
                  <LineChart data={chartData} margin={{ bottom: 8, left: 0, right: 12, top: 12 }}>
                    <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={18} {...commonAxisProps()} />
                    <YAxis {...commonAxisProps()} />
                    <Tooltip {...tooltipProps()} />
                    {baselineLine(stats.baselines.hrv_ms, "28d median")}
                    <Line
                      connectNulls={false}
                      dataKey="hrv_ms"
                      dot={false}
                      name="HRV"
                      stroke={chartColors.blue}
                      strokeWidth={2}
                      type="monotone"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>

              <ChartCard
                subtitle="Resting heart rate with 28-day median baseline when enough samples exist."
                title="Resting heart rate"
              >
                <ResponsiveContainer height={260} width="100%">
                  <LineChart data={chartData} margin={{ bottom: 8, left: 0, right: 12, top: 12 }}>
                    <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={18} {...commonAxisProps()} />
                    <YAxis {...commonAxisProps()} />
                    <Tooltip {...tooltipProps()} />
                    {baselineLine(stats.baselines.resting_heart_rate, "28d median")}
                    <Line
                      connectNulls={false}
                      dataKey="resting_heart_rate"
                      dot={false}
                      name="Resting HR"
                      stroke={chartColors.red}
                      strokeWidth={2}
                      type="monotone"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>

              <ChartCard subtitle="Daily start and end values." title="Body Battery">
                <ResponsiveContainer height={260} width="100%">
                  <LineChart data={chartData} margin={{ bottom: 8, left: 0, right: 12, top: 12 }}>
                    <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={18} {...commonAxisProps()} />
                    <YAxis domain={[0, 100]} {...commonAxisProps()} />
                    <Tooltip {...tooltipProps()} />
                    <Legend />
                    <Line
                      connectNulls={false}
                      dataKey="body_battery_start"
                      dot={false}
                      name="Body Battery start"
                      stroke={chartColors.green}
                      strokeWidth={2}
                      type="monotone"
                    />
                    <Line
                      connectNulls={false}
                      dataKey="body_battery_end"
                      dot={false}
                      name="Body Battery end"
                      stroke={chartColors.orange}
                      strokeWidth={2}
                      type="monotone"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>

              <ChartCard
                subtitle="Average daily stress with 28-day median baseline when enough samples exist."
                title="Stress average"
              >
                <ResponsiveContainer height={260} width="100%">
                  <LineChart data={chartData} margin={{ bottom: 8, left: 0, right: 12, top: 12 }}>
                    <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={18} {...commonAxisProps()} />
                    <YAxis {...commonAxisProps()} />
                    <Tooltip {...tooltipProps()} />
                    {baselineLine(stats.baselines.stress_avg, "28d median")}
                    <Line
                      connectNulls={false}
                      dataKey="stress_avg"
                      dot={false}
                      name="Stress avg"
                      stroke={chartColors.purple}
                      strokeWidth={2}
                      type="monotone"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>

              <ChartCard
                subtitle="Step count with 28-day median baseline when enough samples exist."
                title="Steps"
                wide
              >
                <ResponsiveContainer height={260} width="100%">
                  <BarChart data={chartData} margin={{ bottom: 8, left: 0, right: 12, top: 12 }}>
                    <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" minTickGap={18} {...commonAxisProps()} />
                    <YAxis {...commonAxisProps()} />
                    <Tooltip {...tooltipProps()} />
                    {baselineLine(stats.baselines.steps, "28d median")}
                    <Bar dataKey="steps" fill={chartColors.green} name="Steps" radius={[4, 4, 0, 0]} />
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
