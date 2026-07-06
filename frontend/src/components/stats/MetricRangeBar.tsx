import type { MetricStatus } from "./MetricStatusBadge";

type MetricRangeBarProps = {
  value: number | null;
  min: number;
  max: number;
  size?: "sm" | "md";
  showValueLabel?: boolean;
  showEdgeLabels?: boolean;
  edgeLabels?: {
    left?: string;
    center?: string;
    right?: string;
  };
  tone?: "recovery" | "load" | "strength" | "pain" | "neutral";
  zones: Array<{
    from: number;
    to: number;
    status: MetricStatus;
    label: string;
  }>;
  valueLabel?: string;
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export default function MetricRangeBar({
  edgeLabels,
  max,
  min,
  showEdgeLabels = false,
  showValueLabel = true,
  size = "md",
  tone = "neutral",
  value,
  valueLabel,
  zones,
}: MetricRangeBarProps) {
  const percent =
    value === null ? null : ((clamp(value, min, max) - min) / (max - min)) * 100;
  const markerPercent =
    percent === null ? null : Math.min(98, Math.max(2, percent));

  return (
    <div className={`metric-range metric-bar-${size} metric-bar-${tone}`}>
      <div className="metric-range-track">
        {zones.map((zone) => (
          <span
            className={`metric-zone metric-zone-${zone.status}`}
            key={`${zone.from}-${zone.to}-${zone.status}`}
            style={{
              left: `${((zone.from - min) / (max - min)) * 100}%`,
              width: `${((zone.to - zone.from) / (max - min)) * 100}%`,
            }}
            title={zone.label}
          />
        ))}
        {percent !== null && (
          <span className="metric-range-marker" style={{ left: `${markerPercent}%` }} />
        )}
      </div>
      {showEdgeLabels && (
        <div className="metric-bar-labels">
          <span>{edgeLabels?.left ?? String(min)}</span>
          <span>{edgeLabels?.center ?? ""}</span>
          <span>{edgeLabels?.right ?? String(max)}</span>
        </div>
      )}
      {showValueLabel && valueLabel && (
        <div className="metric-visual-label">{valueLabel}</div>
      )}
    </div>
  );
}
