export type MetricStatus = "good" | "watch" | "bad" | "neutral" | "info";

type MetricStatusBadgeProps = {
  status: MetricStatus;
  label?: string;
};

export function metricStatusDisplay(status: MetricStatus) {
  if (status === "good") {
    return "Good";
  }

  if (status === "watch") {
    return "Watch";
  }

  if (status === "bad") {
    return "Risk";
  }

  if (status === "info") {
    return "Info";
  }

  return "No data";
}

export default function MetricStatusBadge({
  label,
  status,
}: MetricStatusBadgeProps) {
  return (
    <span className={`metric-status-badge metric-status-${status}`}>
      {label ?? metricStatusDisplay(status)}
    </span>
  );
}
