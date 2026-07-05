import type { ReactNode } from "react";

import MetricStatusBadge from "./MetricStatusBadge";
import type { MetricStatus } from "./MetricStatusBadge";

type MetricCardProps = {
  title: string;
  value: string;
  subtitle?: string;
  icon?: ReactNode;
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
  title,
  value,
  visual,
}: MetricCardProps) {
  return (
    <article className="metric-card">
      <div className="metric-card-heading">
        <div>
          <span className="metric-card-title">{title}</span>
          {subtitle && <small>{subtitle}</small>}
        </div>
        {icon}
        {status && <MetricStatusBadge label={status.label} status={status.status} />}
      </div>
      <strong>{value}</strong>
      {visual}
      {description && <p>{description}</p>}
    </article>
  );
}
