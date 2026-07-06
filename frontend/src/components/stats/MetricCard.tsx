import type { ReactNode } from "react";

import MetricStatusBadge from "./MetricStatusBadge";
import type { MetricStatus } from "./MetricStatusBadge";

type MetricTone =
  | "recovery"
  | "load"
  | "strength"
  | "pain"
  | "consistency"
  | "neutral";

type MetricCardProps = {
  title: string;
  value: string;
  subtitle?: string;
  icon?: ReactNode;
  tone?: MetricTone;
  status?: {
    label: string;
    status: MetricStatus;
  };
  visual?: ReactNode;
  description?: string;
};

export default function MetricCard({
  description,
  icon,
  status,
  subtitle,
  tone = "neutral",
  title,
  value,
  visual,
}: MetricCardProps) {
  return (
    <article className={`metric-card metric-card-${tone}`}>
      <div className="metric-card-top">
        <div className="metric-card-icon" aria-hidden="true">
          {icon}
        </div>
        <div className="metric-card-copy">
          <span className="metric-card-title">{title}</span>
          {subtitle && <small>{subtitle}</small>}
        </div>
        {status && <MetricStatusBadge label={status.label} status={status.status} />}
      </div>
      <div className="metric-card-value-row">
        <strong>{value}</strong>
      </div>
      {visual && <div className="metric-card-visual">{visual}</div>}
      {description && <p>{description}</p>}
    </article>
  );
}
