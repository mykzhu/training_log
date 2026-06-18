type StatCardProps = {
  className?: string;
  label: string;
  value: string | number;
};

export default function StatCard({
  className = "",
  label,
  value,
}: StatCardProps) {
  return (
    <div className={`stat-card ${className}`.trim()}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
