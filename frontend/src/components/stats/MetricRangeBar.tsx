import type { MetricStatus } from "./MetricStatusBadge";

type MetricRangeBarProps = {
  value: number | null;
  min: number;
  max: number;
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
  max,
  min,
  value,
  valueLabel,
  zones,
}: MetricRangeBarProps) {
  const percent =
    value === null ? null : ((clamp(value, min, max) - min) / (max - min)) * 100;

  return (
    <div className="metric-range">
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
          <span className="metric-range-marker" style={{ left: `${percent}%` }} />
        )}
      </div>
      {valueLabel && <div className="metric-visual-label">{valueLabel}</div>}
    </div>
  );
}
