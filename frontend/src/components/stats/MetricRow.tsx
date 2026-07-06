import type { ReactNode } from "react";

import MetricStatusBadge from "./MetricStatusBadge";
import { metricStatusDisplay } from "./MetricStatusBadge";
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
      <div className="metric-row-main">
        <strong>{label}</strong>
        <span>{description}</span>
      </div>
      <div className="metric-row-visual">{visual}</div>
      <div className="metric-row-value">{value}</div>
      <MetricStatusBadge label={metricStatusDisplay(status)} status={status} />
    </div>
  );
}
