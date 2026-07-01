import type { ReactNode } from "react";

type ChartInsightProps = {
  question: string;
  explanation: string;
  children?: ReactNode;
};

type ChartCardProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
  wide?: boolean;
};

export function ChartInsight({
  children,
  explanation,
  question,
}: ChartInsightProps) {
  return (
    <div className="chart-insight">
      <div className="chart-insight-heading">
        <strong>{question}</strong>
        <span>{explanation}</span>
      </div>

      {children}
    </div>
  );
}

export function ChartCard({
  actions,
  children,
  subtitle,
  title,
  wide = false,
}: ChartCardProps) {
  return (
    <section className={wide ? "chart-card chart-card-wide" : "chart-card"}>
      <div
        className={
          actions
            ? "chart-heading chart-heading-with-actions"
            : "chart-heading"
        }
      >
        <div>
          <h2>{title}</h2>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>

        {actions && (
          <div className="chart-heading-actions">
            {actions}
          </div>
        )}
      </div>

      <div className="chart-frame">{children}</div>
    </section>
  );
}
