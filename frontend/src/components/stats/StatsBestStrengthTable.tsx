import type { ExerciseStats } from "../../api/types";
import {
  ChartCard,
  ChartInsight,
} from "./StatsChartScaffold";

type BestStrengthExercise = ExerciseStats & {
  best_e1rm: number;
  best_set: NonNullable<ExerciseStats["best_set"]>;
};

type StatsBestStrengthTableProps = {
  exercises: BestStrengthExercise[];
  formatNumber: (value: number | null | undefined, digits?: number) => string;
  onOpenExercise: (exerciseId: number) => void;
  onOpenWorkout: (workoutId: number) => void;
};

export default function StatsBestStrengthTable({
  exercises,
  formatNumber,
  onOpenExercise,
  onOpenWorkout,
}: StatsBestStrengthTableProps) {
  return (
    <ChartCard
      wide
      subtitle="e1RM is shown only for weighted sets with 3–12 reps"
      title="Best strength estimates"
    >
      {exercises.length > 0 ? (
        <div className="strength-table-scroll">
          <table className="strength-table">
            <thead>
              <tr>
                <th>Exercise</th>
                <th>Best e1RM</th>
                <th>From set</th>
                <th>Date</th>
              </tr>
            </thead>

            <tbody>
              {exercises.map((exercise) => (
                <tr key={exercise.exercise_id}>
                  <td>
                    <button
                      className="strength-table-link"
                      onClick={() =>
                        onOpenExercise(exercise.exercise_id)
                      }
                      type="button"
                    >
                      {exercise.name}
                    </button>
                  </td>

                  <td className="strength-table-value">
                    {formatNumber(exercise.best_e1rm, 1)} kg
                  </td>

                  <td className="strength-table-set">
                    {formatNumber(exercise.best_set.weight, 1)}
                    {" × "}
                    {exercise.best_set.reps}
                  </td>

                  <td>
                    <button
                      className="strength-table-link strength-table-date"
                      onClick={() =>
                        onOpenWorkout(exercise.best_set.workout_id)
                      }
                      type="button"
                    >
                      {exercise.best_set.date}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty">
          No eligible strength estimates yet.
        </div>
      )}

      <ChartInsight
        question="What does the estimated 1RM represent?"
        explanation="e1RM estimates the maximum weight you could lift once, based on a recorded working set."
      >
        <div className="chart-insight-details">
          <span>
            The estimate is calculated only from weighted sets containing 3–12
            repetitions.
          </span>

          <span>
            The From set column shows the exact weight and repetitions that produced
            the highest estimate for each exercise.
          </span>

          <span>
            Compare e1RM changes within the same exercise. Values from different
            exercises are not directly comparable.
          </span>

          <span>
            Select an exercise to open its statistics, or select the date to open
            the source workout.
          </span>
        </div>

        <p className="chart-insight-footnote">
          Sets such as 50 × 2, 20 × 15, and bodyweight sets such as 0 × 50 are
          intentionally excluded from the e1RM calculation.
        </p>
      </ChartInsight>
    </ChartCard>
  );
}
