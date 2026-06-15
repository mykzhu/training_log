import { useEffect, useState } from "react";

import { getWorkouts } from "../api/workouts";
import type { WorkoutSummary } from "../api/types";
import StatusBadge from "../components/StatusBadge";

export default function HistoryPage() {
  const [workouts, setWorkouts] = useState<WorkoutSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getWorkouts()
      .then((response) => setWorkouts(response.workouts))
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Failed to load.");
      });
  }, []);

  return (
    <section className="page-stack">
      {error && <div className="error-banner">{error}</div>}
      <div className="table-list">
        {workouts.map((workout) => (
          <article className="list-row" key={workout.id}>
            <div>
              <h2>{workout.workout_date}</h2>
              <p>
                {workout.exercises_count} exercises · {workout.total_sets} sets ·{" "}
                {workout.total_volume.toFixed(0)} kg
              </p>
            </div>
            <StatusBadge>{workout.load_metrics.load_label}</StatusBadge>
          </article>
        ))}
      </div>
    </section>
  );
}
