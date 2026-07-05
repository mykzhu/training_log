import type { ReactNode } from "react";

import MetricStatusBadge from "./MetricStatusBadge";
import type { MetricStatus } from "./MetricStatusBadge";

type MetricRowProps = {
  label: string;
  description: string;
  value: string;
  status: MetricStatus;
  visual: ReactNode;
};

export default function MetricRow({
  description,
  label,
  status,
  value,
  visual,
}: MetricRowProps) {
  return (
    <div className="metric-row">
      <div>
        <strong>{label}</strong>
        <span>{description}</span>
      </div>
      <div className="metric-row-visual">{visual}</div>
      <b>{value}</b>
      <MetricStatusBadge label={status === "neutral" ? "No data" : status} status={status} />
    </div>
  );
}
