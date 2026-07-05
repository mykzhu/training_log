export type MetricSparklinePoint = {
  date: string;
  value: number;
};

type MetricSparklineProps = {
  data: MetricSparklinePoint[];
  valueKey?: "value";
  label?: string;
};

export default function MetricSparkline({
  data,
  label,
}: MetricSparklineProps) {
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

  return (
    <div className="metric-sparkline" aria-label={label}>
      <svg viewBox="0 0 100 40" role="img">
        <polyline points={points} />
      </svg>
    </div>
  );
}
