export type MetricStatus = "good" | "watch" | "bad" | "neutral" | "info";

type MetricStatusBadgeProps = {
  status: MetricStatus;
  label: string;
};

export default function MetricStatusBadge({
  label,
  status,
}: MetricStatusBadgeProps) {
  return <span className={`metric-status-badge metric-status-${status}`}>{label}</span>;
}
