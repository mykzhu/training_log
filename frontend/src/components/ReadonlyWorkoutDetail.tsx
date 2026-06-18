import type { WorkoutDetail } from "../api/types";

type ReadonlyWorkoutDetailProps = {
  detail: WorkoutDetail;
  disabled: boolean;
  onDelete: () => void;
  onEdit: () => void;
};

function formatNumber(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return Number(value).toFixed(digits);
}

function formatClockDuration(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) {
    return "—";
  }

  const totalSeconds = Math.max(0, seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const remainingSeconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${remainingSeconds
      .toString()
      .padStart(2, "0")}`;
  }

  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}

function formatDateTime(value: string) {
  return value.slice(0, 16).replace("T", " ");
}

function formatScoreOutOfTen(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${value}/10`;
}

function formatBestSet(setEntry: { weight: number; reps: number } | null) {
  if (!setEntry) {
    return "—";
  }

  if (setEntry.weight > 0) {
    return `${formatNumber(setEntry.weight)} × ${setEntry.reps}`;
  }

  return `${setEntry.reps} reps`;
}

function loadMetricClass(loadLabel: string | null | undefined) {
  if (loadLabel === "Light") {
    return "metric-green";
  }
  if (loadLabel === "Medium") {
    return "metric-yellow";
  }
  if (loadLabel === "Hard") {
    return "metric-orange";
  }
  if (loadLabel === "Very hard") {
    return "metric-red";
  }

  return "metric-neutral";
}

function scoreMetricClass(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "metric-neutral";
  }
  if (value <= 2) {
    return "metric-green";
  }
  if (value <= 4) {
    return "metric-lime";
  }
  if (value <= 6) {
    return "metric-yellow";
  }
  if (value <= 8) {
    return "metric-orange";
  }

  return "metric-red";
}

type RecommendationTone = "good" | "warning" | "danger";

type PostWorkoutRecommendation = {
  tone: RecommendationTone;
  title: string;
  message: string;
};

function buildPostWorkoutRecommendation(
  detail: WorkoutDetail,
): PostWorkoutRecommendation {
  const rpe = detail.workout.session_rpe;
  const backPain = detail.workout.lower_back_pain;
  const {
    back_stress_score: backStress,
    intensity_score: intensityScore,
    load_label: loadLabel,
    load_score: loadScore,
  } = detail.load_metrics;

  if (backPain !== null && backPain >= 3) {
    return {
      tone: "danger",
      title: "⛔ Progression paused.",
      message: `Back pain is ${backPain}/10. Keep the next session conservative and avoid increasing deadlift, squat or back-loading work.`,
    };
  }

  if (loadLabel === "Very hard" || loadScore >= 14) {
    return {
      tone: "danger",
      title: "⛔ No progression after very hard session.",
      message: `This workout was ${loadLabel} with load score ${formatNumber(loadScore)}. Even with low RPE and calm back pain, repeat or reduce the next session instead of adding weight or reps.`,
    };
  }

  if (backStress >= 8) {
    return {
      tone: "warning",
      title: "⚠️ Back stress is high.",
      message: `Back pain is low, but calculated back stress is ${formatNumber(backStress)}. Keep the next lower-back-loading work stable and avoid adding deadlift, squat or row volume.`,
    };
  }

  if (rpe !== null && rpe >= 8) {
    return {
      tone: "warning",
      title: "⚠️ Keep load stable.",
      message: `RPE is ${rpe}/10. This was hard enough; repeat the same load or add only a small rep if back stays calm.`,
    };
  }

  if (intensityScore !== null && intensityScore >= 95) {
    return {
      tone: "warning",
      title: "⚠️ High relative intensity.",
      message: `Intensity was around ${formatNumber(intensityScore, 0)}% of your recent history. Do not increase weight next time; repeat the same loads or add only easy reps.`,
    };
  }

  if (detail.total_reps === 0) {
    return {
      tone: "warning",
      title: "ℹ️ No training stimulus yet.",
      message: "Add working sets before judging progression.",
    };
  }

  if (loadLabel === "Hard" || loadScore >= 8) {
    return {
      tone: "warning",
      title: "⚠️ Progress carefully.",
      message:
        "This was a hard session. If back stays calm, add only a small amount to one main exercise, not to the whole workout.",
    };
  }

  if (
    rpe !== null &&
    backPain !== null &&
    rpe <= 7 &&
    backPain <= 2
  ) {
    return {
      tone: "good",
      title: "✅ Progress allowed.",
      message:
        "RPE, back pain and calculated load are in a safe range. Next time you can add a small amount of weight or 1–2 reps to one main exercise.",
    };
  }

  return {
    tone: "warning",
    title: "ℹ️ Progress unclear.",
    message:
      "Log RPE and Back Pain to make the next-session recommendation more reliable.",
  };
}

type ExerciseAnalysis = WorkoutDetail["analysis"]["exercises"][number];

export default function ReadonlyWorkoutDetail({
  detail,
  disabled,
  onDelete,
  onEdit,
}: ReadonlyWorkoutDetailProps) {
  const analysisByExercise = new Map<number, ExerciseAnalysis>(
    detail.analysis.exercises.map(
      (exercise): [number, ExerciseAnalysis] => [
        exercise.exercise_id,
        exercise,
      ],
    ),
  );

  return (
    <section className="page-stack readonly-workout-detail">
      <div className="readonly-workout-meta">
        <span>{formatDateTime(detail.workout.created_at)}</span>
        <span>{detail.workout.finished_at ? "finished" : "active"}</span>
      </div>

      <div className="readonly-workout-stat-grid">
        <ReadonlyStat
          label="duration"
          value={formatClockDuration(detail.workout.duration_seconds)}
        />
        <ReadonlyStat label="sets" value={detail.total_sets} />
        <ReadonlyStat label="reps" value={detail.total_reps} />
        <ReadonlyStat
          label="kg volume"
          value={detail.total_volume.toFixed(1)}
        />
        <ReadonlyStat
          className={loadMetricClass(detail.load_metrics.load_label)}
          label={`${formatNumber(detail.load_metrics.load_score)} load`}
          value={detail.load_metrics.load_label}
        />
        <ReadonlyStat
          className={scoreMetricClass(detail.load_metrics.back_stress_score)}
          label="back stress"
          value={formatNumber(detail.load_metrics.back_stress_score)}
        />
        <ReadonlyStat
          className={scoreMetricClass(detail.workout.session_rpe)}
          label="RPE"
          value={formatScoreOutOfTen(detail.workout.session_rpe)}
        />
        <ReadonlyStat
          className={scoreMetricClass(detail.workout.lower_back_pain)}
          label="Back Pain"
          value={formatScoreOutOfTen(detail.workout.lower_back_pain)}
        />
      </div>

      <WorkoutAnalysis detail={detail} />

      <section className="panel readonly-workout-actions">
        <button
          className="ghost-button"
          disabled={disabled}
          onClick={onEdit}
          type="button"
        >
          Edit workout
        </button>
        <button
          className="danger-button"
          disabled={disabled}
          onClick={onDelete}
          type="button"
        >
          Delete workout
        </button>
      </section>

      <div className="readonly-exercise-list">
        {detail.exercises.length === 0 && (
          <section className="readonly-workout-empty">
            No exercises in this workout.
          </section>
        )}

        {detail.exercises.map((exercise) => {
          const exerciseAnalysis = analysisByExercise.get(exercise.exercise_id);

          return (
            <article
              className="readonly-exercise-card"
              key={exercise.workout_exercise_id}
            >
              <div className="readonly-exercise-header">
                <div>
                  <div className="readonly-exercise-title-row">
                    <h2>{exercise.exercise_name}</h2>
                    {exerciseAnalysis &&
                      exerciseAnalysis.pr_flags.length > 0 && (
                        <span className="readonly-pr-badge">
                          🏆 {exerciseAnalysis.pr_flags.join(", ")}
                        </span>
                      )}
                  </div>
                  <p>
                    {exercise.total_sets} sets · {exercise.total_reps} reps ·{" "}
                    {exercise.total_volume.toFixed(1)} kg
                    {exerciseAnalysis?.best_e1rm !== null &&
                      exerciseAnalysis?.best_e1rm !== undefined && (
                        <> · e1RM {formatNumber(exerciseAnalysis.best_e1rm)} kg</>
                      )}
                  </p>
                </div>
              </div>

              {exercise.sets.length === 0 ? (
                <p className="muted">No sets.</p>
              ) : (
                <div className="readonly-exercise-table-scroll">
                  <table className="readonly-exercise-table">
                    <thead>
                      <tr>
                        <th>Set</th>
                        <th>Kg</th>
                        <th>Reps</th>
                        <th>Volume</th>
                      </tr>
                    </thead>
                    <tbody>
                      {exercise.sets.map((setEntry) => (
                        <tr key={setEntry.id}>
                          <td>{setEntry.set_number}</td>
                          <td>{formatNumber(setEntry.weight)}</td>
                          <td>{setEntry.reps}</td>
                          <td>
                            {formatNumber(setEntry.weight * setEntry.reps)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function WorkoutAnalysis({ detail }: { detail: WorkoutDetail }) {
  const recommendation = buildPostWorkoutRecommendation(detail);

  return (
    <section className="panel analysis-card">
      <h2>Analysis</h2>
      <section
        className={`analysis-section ${loadMetricClass(
          detail.load_metrics.load_label,
        )}`}
      >
        <h3>Workout load</h3>
        <AnalysisRow
          label={detail.load_metrics.load_label}
          note="overall training difficulty"
          value={formatNumber(detail.load_metrics.load_score)}
        />
        <AnalysisRow
          label="Compound score"
          note="base exercise contribution"
          value={formatNumber(detail.load_metrics.compound_score)}
        />
        <AnalysisRow
          label="Intensity score"
          note="relative to your history"
          value={
            detail.load_metrics.intensity_score === null
              ? "—"
              : `${formatNumber(detail.load_metrics.intensity_score, 0)}%`
          }
        />
        <AnalysisRow
          label="Back stress"
          note="deadlift / squat / row stress"
          value={formatNumber(detail.load_metrics.back_stress_score)}
        />
        <p className="analysis-note">
          Load score uses exercise type, reps, relative intensity and RPE. This
          is more useful than tonnage alone when comparing heavy compound work
          with light accessory volume.
        </p>
      </section>

      <div className="analysis-grid">
        <section className="analysis-section">
          <h3>Best sets</h3>
          {detail.analysis.exercises.length === 0 ? (
            <div className="muted">No sets yet.</div>
          ) : (
            detail.analysis.exercises.map((exercise) => (
              <AnalysisRow
                key={exercise.exercise_id}
                label={exercise.exercise_name}
                note={
                  exercise.best_e1rm_set
                    ? "best reliable strength set"
                    : "best by set volume"
                }
                value={formatBestSet(exercise.best_set)}
              />
            ))
          )}
        </section>

        <section className="analysis-section">
          <h3>Strength estimate</h3>
          {detail.analysis.exercises.filter(
            (exercise) => exercise.best_e1rm !== null,
          ).length === 0 ? (
            <div className="muted">No reliable e1RM estimate yet.</div>
          ) : (
            detail.analysis.exercises
              .filter((exercise) => exercise.best_e1rm !== null)
              .map((exercise) => (
                <AnalysisRow
                  key={exercise.exercise_id}
                  label={exercise.exercise_name}
                  note={`from ${formatBestSet(exercise.best_e1rm_set)}`}
                  value={`${formatNumber(exercise.best_e1rm)} kg`}
                />
              ))
          )}
          <p className="analysis-note">
            e1RM is shown only for weighted sets with 3–12 reps.
          </p>
        </section>

        <section className="analysis-section">
          <h3>PRs</h3>
          {detail.analysis.prs.length === 0 ? (
            <div className="muted">No PRs in this workout.</div>
          ) : (
            detail.analysis.prs.map((pr) => (
              <AnalysisRow
                key={`${pr.exercise_name}-${pr.type}`}
                label={`🏆 ${pr.exercise_name}`}
                value={pr.type}
              />
            ))
          )}
        </section>

        <section className="analysis-section">
          <h3>Intensity</h3>
          <AnalysisRow
            label="Average weight per rep"
            value={
              detail.total_reps
                ? `${formatNumber(
                    detail.total_volume / detail.total_reps,
                  )} kg/rep`
                : "—"
            }
          />
        </section>
      </div>
        <section
          aria-label="Post-workout recommendation"
          className={`analysis-recommendation ${recommendation.tone}`}
        >
          <strong>{recommendation.title}</strong>
          <p>{recommendation.message}</p>
        </section>
    </section>
  );
}

type AnalysisRowProps = {
  label: string;
  note?: string;
  value: string;
};

function AnalysisRow({ label, note, value }: AnalysisRowProps) {
  return (
    <div className="analysis-row">
      <div>
        <div className="analysis-main">{label}</div>
        {note && <div className="muted small">{note}</div>}
      </div>
      <div className="analysis-value">{value}</div>
    </div>
  );
}

type ReadonlyStatProps = {
  className?: string;
  label: string;
  value: number | string;
};

function ReadonlyStat({
  className = "metric-neutral",
  label,
  value,
}: ReadonlyStatProps) {
  return (
    <div className={`readonly-workout-stat ${className}`}>
      <strong>{value}</strong>
      <span className="muted">{label}</span>
    </div>
  );
}
