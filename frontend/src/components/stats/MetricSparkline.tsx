import { useId } from "react";

export type MetricSparklinePoint = {
  date: string;
  value: number;
};

type MetricSparklineProps = {
  data: MetricSparklinePoint[];
  tone?: "load" | "strength" | "consistency" | "neutral";
  label?: string;
  emptyLabel?: string;
  showArea?: boolean;
};

export default function MetricSparkline({
  data,
  emptyLabel = "No trend yet",
  label,
  showArea = true,
  tone = "neutral",
}: MetricSparklineProps) {
  const id = useId().replace(/:/g, "");

  if (data.length < 2) {
    return <div className="metric-sparkline-empty">{emptyLabel}</div>;
  }

  const values = data.map((point) => point.value);
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const spread = Math.max(max - min, 1);
  const points = data
    .map((point, index) => {
      const x = data.length <= 1 ? 50 : (index / (data.length - 1)) * 100;
      const y = 34 - ((point.value - min) / spread) * 28;
      return `${x},${y}`;
    })
    .join(" ");
  const areaPoints = `0,38 ${points} 100,38`;
  const endPoint = data[data.length - 1];
  const endX = 100;
  const endY = 34 - ((endPoint.value - min) / spread) * 28;
  const gradientId = `metric-sparkline-${tone}-${id}`;

  return (
    <div className={`metric-sparkline metric-sparkline-${tone}`} aria-label={label}>
      <svg viewBox="0 0 100 40" role="img">
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop className="metric-sparkline-fill-start" offset="0%" />
            <stop className="metric-sparkline-fill-end" offset="100%" />
          </linearGradient>
        </defs>
        <line className="metric-sparkline-baseline" x1="0" x2="100" y1="34" y2="34" />
        {showArea && (
          <polygon
            className="metric-sparkline-area"
            points={areaPoints}
            style={{ fill: `url(#${gradientId})` }}
          />
        )}
        <polyline className="metric-sparkline-line" points={points} />
        <circle className="metric-sparkline-end" cx={endX} cy={endY} r="2.8" />
      </svg>
    </div>
  );
}
