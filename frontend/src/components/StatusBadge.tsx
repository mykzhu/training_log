type StatusBadgeProps = {
  tone?: "neutral" | "good" | "warn" | "danger";
  children: string;
};

export default function StatusBadge({
  tone = "neutral",
  children,
}: StatusBadgeProps) {
  return <span className={`status-badge status-${tone}`}>{children}</span>;
}
