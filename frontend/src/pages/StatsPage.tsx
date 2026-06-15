import { useEffect, useState } from "react";

import { getStats } from "../api/stats";
import type { StatsResponse } from "../api/types";
import StatCard from "../components/StatCard";

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "—";
  }
  return Number(value).toFixed(0);
}

export default function StatsPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Failed to load.");
      });
  }, []);

  const summary = stats?.stats.summary;

  return (
    <section className="page-stack">
      {error && <div className="error-banner">{error}</div>}
      <div className="stat-grid">
        <StatCard label="Workouts" value={formatNumber(summary?.workout_count)} />
        <StatCard label="Volume" value={`${formatNumber(summary?.total_volume)} kg`} />
        <StatCard label="Sets" value={formatNumber(summary?.total_sets)} />
        <StatCard label="Load" value={formatNumber(summary?.total_load_score)} />
      </div>
    </section>
  );
}
