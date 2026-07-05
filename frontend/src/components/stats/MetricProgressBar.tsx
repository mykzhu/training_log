import type { MetricStatus } from "./MetricStatusBadge";

type MetricProgressBarProps = {
  value: number | null;
  min?: number;
  max?: number;
  markerLabel?: string;
  zones?: Array<{
    from: number;
    to: number;
    status: MetricStatus;
    label?: string;
  }>;
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export default function MetricProgressBar({
  markerLabel,
  max = 100,
  min = 0,
  value,
  zones = [],
}: MetricProgressBarProps) {
  const percent =
    value === null ? null : ((clamp(value, min, max) - min) / (max - min)) * 100;

  return (
    <div className="metric-progress">
      <div className="metric-progress-track">
        {zones.length > 0
          ? zones.map((zone) => (
              <span
                className={`metric-zone metric-zone-${zone.status}`}
                key={`${zone.from}-${zone.to}-${zone.status}`}
                style={{
                  left: `${((zone.from - min) / (max - min)) * 100}%`,
                  width: `${((zone.to - zone.from) / (max - min)) * 100}%`,
                }}
                title={zone.label}
              />
            ))
          : <span className="metric-zone metric-zone-info" />}
        {percent !== null && (
          <span className="metric-progress-marker" style={{ left: `${percent}%` }} />
        )}
      </div>
      {markerLabel && <div className="metric-visual-label">{markerLabel}</div>}
    </div>
  );
}
