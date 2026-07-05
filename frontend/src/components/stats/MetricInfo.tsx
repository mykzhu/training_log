type MetricInfoProps = {
  children: string;
};

export default function MetricInfo({ children }: MetricInfoProps) {
  return <span className="metric-info" title={children}>i</span>;
}
