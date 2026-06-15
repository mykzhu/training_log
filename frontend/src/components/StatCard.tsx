type StatCardProps = {
  label: string;
  value: string | number;
};

export default function StatCard({ label, value }: StatCardProps) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
