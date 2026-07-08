import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { CurrentWorkout, CurrentWorkoutExercise } from "../api/types";
import { rpeOptionLabel } from "../utils/rpeLabels";
import {
  buildRepsOptions,
  buildWeightOptions,
  formatSetOption,
} from "../utils/setOptions";
import "./LegacyActiveWorkoutView.css";

type ExerciseOption = {
  value: string;
  label: string;
};

type LegacyActiveWorkoutViewProps = {
  currentWorkout: CurrentWorkout;
  disabled: boolean;
  elapsedSeconds: number;
  error: string | null;
  exerciseOptions: ExerciseOption[];
  metadataSaveStatus: "idle" | "saving" | "saved" | "error";
  selectedExerciseId: string;
  onAddExercise: () => Promise<void> | void;
  onAddSet: (exerciseId: number, weight: number, reps: number) => Promise<void> | void;
  onCancel: () => Promise<void> | void;
  onDeleteExercise: (exerciseId: number) => Promise<void> | void;
  onDeleteSet: (setId: number) => Promise<void> | void;
  onFinish: () => Promise<void> | void;
  onSaveMetadata: (
    sessionRpe: number | null,
    lowerBackPain: number | null,
  ) => Promise<void> | void;
  onSelectExercise: (exerciseId: string) => void;
};

type RecommendationTone = "good" | "warning" | "danger";

type ActiveRecommendation = {
  tone: RecommendationTone;
  title: string;
  message: string;
};

type ExerciseStrengthSummary = {
  bestSet: { weight: number; reps: number } | null;
  bestE1rm: number | null;
  bestE1rmSet: { weight: number; reps: number } | null;
};

function formatNumber(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return Number(value).toFixed(digits);
}

function formatClockDuration(seconds: number) {
  const totalSeconds = Math.max(0, Math.floor(seconds));
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

function formatDateTime(value: string | null) {
  if (!value) {
    return "—";
  }

  return value.slice(0, 16).replace("T", " ");
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

function estimatedOneRepMax(weight: number, reps: number) {
  if (weight <= 0 || reps < 3 || reps > 12) {
    return null;
  }

  return weight * (1 + reps / 30);
}

function buildStrengthSummary(
  exercise: CurrentWorkoutExercise,
): ExerciseStrengthSummary {
  let bestSet: { weight: number; reps: number } | null = null;
  let bestFallbackScore = -1;
  let bestE1rm: number | null = null;
  let bestE1rmSet: { weight: number; reps: number } | null = null;

  for (const setEntry of exercise.sets) {
    const candidate = {
      weight: Number(setEntry.weight),
      reps: Number(setEntry.reps),
    };
    const e1rm = estimatedOneRepMax(candidate.weight, candidate.reps);

    if (e1rm !== null) {
      if (bestE1rm === null || e1rm > bestE1rm) {
        bestE1rm = e1rm;
        bestE1rmSet = candidate;
        bestSet = candidate;
      }
      continue;
    }

    if (bestE1rm !== null) {
      continue;
    }

    const fallbackScore =
      candidate.weight > 0
        ? candidate.weight * candidate.reps
        : candidate.reps;
    if (fallbackScore > bestFallbackScore) {
      bestFallbackScore = fallbackScore;
      bestSet = candidate;
    }
  }

  return {
    bestSet,
    bestE1rm,
    bestE1rmSet,
  };
}

function metricClassForLoad(loadLabel: string | null | undefined) {
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

function metricClassForScore(value: number | null | undefined) {
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

function buildActiveRecommendation(
  currentWorkout: CurrentWorkout,
): ActiveRecommendation {
  const rpe = currentWorkout.session_rpe;
  const backPain = currentWorkout.lower_back_pain;
  const loadMetrics = currentWorkout.load_metrics;
  const loadLabel = loadMetrics?.load_label ?? null;
  const loadScore = loadMetrics?.load_score ?? 0;
  const backStress = loadMetrics?.back_stress_score ?? 0;
  const intensityScore = loadMetrics?.intensity_score ?? null;

  if (backPain !== null && backPain >= 3) {
    return {
      tone: "danger",
      title: "⛔ Progression paused.",
      message: `Back pain is ${backPain}/10. Keep this session conservative and avoid increasing deadlift, squat or back-loading work.`,
    };
  }

  if (loadLabel === "Very hard" || loadScore >= 14) {
    return {
      tone: "danger",
      title: "⛔ No more progression in this session.",
      message: `Current load is ${loadLabel ?? "very high"} with score ${formatNumber(loadScore)}. Finish or repeat easy work instead of adding weight or reps.`,
    };
  }

  if (backStress >= 8) {
    return {
      tone: "warning",
      title: "⚠️ Back stress is high.",
      message: `Calculated back stress is ${formatNumber(backStress)}. Keep deadlift, squat and row work stable for the rest of this session.`,
    };
  }

  if (rpe !== null && rpe >= 8) {
    return {
      tone: "warning",
      title: "⚠️ Keep load stable.",
      message: `RPE is ${rpe}/10. Avoid adding weight and use only easy additional reps if your back remains calm.`,
    };
  }

  if (intensityScore !== null && intensityScore >= 95) {
    return {
      tone: "warning",
      title: "⚠️ High relative intensity.",
      message: `Intensity is around ${formatNumber(intensityScore, 0)}% of recent history. Repeat the same loads instead of increasing them.`,
    };
  }

  if (currentWorkout.total_reps === 0) {
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
        "This is already a hard session. Add only a small amount to one main exercise, not to the whole workout.",
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
      title: "✅ Controlled progress is still available.",
      message:
        "RPE, back pain and calculated load are in a safe range. A small increase to one main exercise is reasonable.",
    };
  }

  return {
    tone: "warning",
    title: "ℹ️ Progress unclear.",
    message:
      "Set RPE and Back Pain to make the live recommendation more reliable.",
  };
}

function metadataSaveStatusLabel(
  status: LegacyActiveWorkoutViewProps["metadataSaveStatus"],
) {
  if (status === "saving") {
    return "Saving...";
  }
  if (status === "saved") {
    return "Saved";
  }
  if (status === "error") {
    return "Could not save";
  }

  return "Auto-saves";
}

export default function LegacyActiveWorkoutView({
  currentWorkout,
  disabled,
  elapsedSeconds,
  error,
  exerciseOptions,
  metadataSaveStatus,
  selectedExerciseId,
  onAddExercise,
  onAddSet,
  onCancel,
  onDeleteExercise,
  onDeleteSet,
  onFinish,
  onSaveMetadata,
  onSelectExercise,
}: LegacyActiveWorkoutViewProps) {
  const [sessionRpe, setSessionRpe] = useState(
    String(currentWorkout.session_rpe ?? ""),
  );
  const [backPain, setBackPain] = useState(
    String(currentWorkout.lower_back_pain ?? ""),
  );

  useEffect(() => {
    setSessionRpe(String(currentWorkout.session_rpe ?? ""));
    setBackPain(String(currentWorkout.lower_back_pain ?? ""));
  }, [currentWorkout.session_rpe, currentWorkout.lower_back_pain]);

  async function saveSessionStatus(nextSessionRpe: string, nextBackPain: string) {
    await onSaveMetadata(
      nextSessionRpe ? Number(nextSessionRpe) : null,
      nextBackPain !== "" ? Number(nextBackPain) : null,
    );
  }

  return (
    <section className="page-stack legacy-active-workout">
      {error && <div className="error-banner">{error}</div>}

      <div className="active-workout-meta">
        <span>Started · {formatDateTime(currentWorkout.started_at)}</span>
        <span className="active-status-badge">active</span>
      </div>

      <div className="active-workout-stat-grid">
        <ActiveStat label="duration" value={formatClockDuration(elapsedSeconds)} />
        <ActiveStat label="sets" value={currentWorkout.total_sets} />
        <ActiveStat label="reps" value={currentWorkout.total_reps} />
        <ActiveStat
          label="kg volume"
          value={currentWorkout.total_volume.toFixed(1)}
        />
        {currentWorkout.load_metrics && (
          <>
            <ActiveStat
              className={metricClassForLoad(
                currentWorkout.load_metrics.load_label,
              )}
              label={`${formatNumber(
                currentWorkout.load_metrics.load_score,
              )} load`}
              value={currentWorkout.load_metrics.load_label}
            />
            <ActiveStat
              className={metricClassForScore(
                currentWorkout.load_metrics.back_stress_score,
              )}
              label="back stress"
              value={formatNumber(
                currentWorkout.load_metrics.back_stress_score,
              )}
            />
          </>
        )}
      </div>

      {currentWorkout.exercises.length > 0 && (
        <ActiveWorkoutAnalysis currentWorkout={currentWorkout} />
      )}

      <section className="panel active-session-card">
        <div className="active-session-heading">
          <h2>Session status</h2>
          <span
            className={`active-save-status active-save-status-${metadataSaveStatus}`}
          >
            {metadataSaveStatusLabel(metadataSaveStatus)}
          </span>
        </div>
        <div className="active-session-row">
          <label>
            RPE
            <select
              className={`active-session-select ${metricClassForScore(
                sessionRpe ? Number(sessionRpe) : null,
              )}`}
              disabled={disabled}
              onChange={(event) => {
                const value = event.target.value;
                setSessionRpe(value);
                void saveSessionStatus(value, backPain);
              }}
              value={sessionRpe}
            >
              <option value="">RPE</option>
              {Array.from({ length: 10 }, (_, index) => index + 1).map(
                (value) => (
                  <option key={value} value={value}>
                    {rpeOptionLabel(value)}
                  </option>
                ),
              )}
            </select>
          </label>
          <label>
            Back Pain
            <select
              className={`active-session-select ${metricClassForScore(
                backPain !== "" ? Number(backPain) : null,
              )}`}
              disabled={disabled}
              onChange={(event) => {
                const value = event.target.value;
                setBackPain(value);
                void saveSessionStatus(sessionRpe, value);
              }}
              value={backPain}
            >
              <option value="">Back Pain</option>
              {Array.from({ length: 11 }, (_, index) => index).map((value) => (
                <option key={value} value={value}>
                  Back Pain {value}/10
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="panel active-add-exercise-card">
        <h2>Add exercise</h2>
        <div className="active-exercise-add-row">
          <select
            aria-label="Exercise"
            disabled={disabled || exerciseOptions.length === 0}
            onChange={(event) => onSelectExercise(event.target.value)}
            value={selectedExerciseId}
          >
            {exerciseOptions.map((exercise) => (
              <option key={exercise.value} value={exercise.value}>
                {exercise.label}
              </option>
            ))}
          </select>
          <button
            className="primary-button"
            disabled={disabled || !selectedExerciseId}
            onClick={() => void onAddExercise()}
            type="button"
          >
            Add
          </button>
        </div>
        <Link className="active-settings-link" to="/settings">
          Missing an exercise? Add it in Settings.
        </Link>
      </section>

      {currentWorkout.exercises.length > 0 ? (
        <div className="active-exercise-list">
          {currentWorkout.exercises.map((exercise) => (
            <LegacyActiveExerciseCard
              disabled={disabled}
              exercise={exercise}
              key={exercise.draft_exercise_id}
              onAddSet={onAddSet}
              onDeleteExercise={onDeleteExercise}
              onDeleteSet={onDeleteSet}
            />
          ))}
        </div>
      ) : (
        <section className="active-workout-empty">
          Add your first exercise for this workout.
        </section>
      )}

      <div className="active-workout-finish-actions">
        <button
          className="active-finish-button"
          disabled={disabled}
          onClick={() => void onFinish()}
          type="button"
        >
          Finish workout
        </button>
        <button
          className="active-cancel-button"
          disabled={disabled}
          onClick={() => void onCancel()}
          type="button"
        >
          Cancel workout
        </button>
      </div>
    </section>
  );
}

function ActiveWorkoutAnalysis({
  currentWorkout,
}: {
  currentWorkout: CurrentWorkout;
}) {
  const summaries = useMemo(
    () =>
      currentWorkout.exercises.map((exercise) => ({
        exercise,
        summary: buildStrengthSummary(exercise),
      })),
    [currentWorkout.exercises],
  );
  const recommendation = buildActiveRecommendation(currentWorkout);
  const loadMetrics = currentWorkout.load_metrics;

  if (!loadMetrics) {
    return null;
  }

  return (
    <section className="panel analysis-card active-analysis-card">
      <h2>Analysis</h2>
      <section
        className={`analysis-section ${metricClassForLoad(
          loadMetrics.load_label,
        )}`}
      >
        <h3>Workout load</h3>
        <AnalysisRow
          label={loadMetrics.load_label}
          note="overall training difficulty"
          value={formatNumber(loadMetrics.load_score)}
        />
        <AnalysisRow
          label="Compound score"
          note="base exercise contribution"
          value={formatNumber(loadMetrics.compound_score)}
        />
        <AnalysisRow
          label="Intensity score"
          note="relative to your history"
          value={
            loadMetrics.intensity_score === null
              ? "—"
              : `${formatNumber(loadMetrics.intensity_score, 0)}%`
          }
        />
        <AnalysisRow
          label="Back stress"
          note="deadlift / squat / row stress"
          value={formatNumber(loadMetrics.back_stress_score)}
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
          {summaries.map(({ exercise, summary }) => (
            <AnalysisRow
              key={exercise.exercise_id}
              label={exercise.exercise_name}
              note={
                summary.bestE1rmSet
                  ? "best reliable strength set"
                  : "best by set volume"
              }
              value={formatBestSet(summary.bestSet)}
            />
          ))}
        </section>

        <section className="analysis-section">
          <h3>Strength estimate</h3>
          {summaries.filter(({ summary }) => summary.bestE1rm !== null).length ===
          0 ? (
            <div className="muted">No reliable e1RM estimate yet.</div>
          ) : (
            summaries
              .filter(({ summary }) => summary.bestE1rm !== null)
              .map(({ exercise, summary }) => (
                <AnalysisRow
                  key={exercise.exercise_id}
                  label={exercise.exercise_name}
                  note={`from ${formatBestSet(summary.bestE1rmSet)}`}
                  value={`${formatNumber(summary.bestE1rm)} kg`}
                />
              ))
          )}
          <p className="analysis-note">
            e1RM is shown only for weighted sets with 3–12 reps.
          </p>
        </section>

        <section className="analysis-section">
          <h3>PRs</h3>
          <div className="muted">PRs are confirmed after finishing the workout.</div>
        </section>

        <section className="analysis-section">
          <h3>Intensity</h3>
          <AnalysisRow
            label="Average weight per rep"
            value={
              currentWorkout.total_reps
                ? `${formatNumber(
                    currentWorkout.total_volume / currentWorkout.total_reps,
                  )} kg/rep`
                : "—"
            }
          />
        </section>
      </div>

      <section
        aria-label="Live workout recommendation"
        className={`analysis-recommendation ${recommendation.tone}`}
      >
        <strong>{recommendation.title}</strong>
        <p>{recommendation.message}</p>
      </section>
    </section>
  );
}

function LegacyActiveExerciseCard({
  disabled,
  exercise,
  onAddSet,
  onDeleteExercise,
  onDeleteSet,
}: {
  disabled: boolean;
  exercise: CurrentWorkoutExercise;
  onAddSet: (exerciseId: number, weight: number, reps: number) => Promise<void> | void;
  onDeleteExercise: (exerciseId: number) => Promise<void> | void;
  onDeleteSet: (setId: number) => Promise<void> | void;
}) {
  const defaultWeight = Number(exercise.default_weight || 0);
  const defaultReps = Number(exercise.default_reps || 10);
  const [addWeight, setAddWeight] = useState(String(defaultWeight));
  const [addReps, setAddReps] = useState(String(defaultReps));
  const strengthSummary = useMemo(
    () => buildStrengthSummary(exercise),
    [exercise],
  );
  const weightOptions = buildWeightOptions(defaultWeight, [
    ...(exercise.weight_options ?? []),
    ...(exercise.configured_weights ?? []),
    ...exercise.sets.map((setEntry) => setEntry.weight),
  ]);
  const configuredRepsOptions = exercise.reps_options ?? [];
  const repsOptions = buildRepsOptions(defaultReps, [
    ...configuredRepsOptions,
    ...exercise.sets.map((setEntry) => setEntry.reps),
  ], configuredRepsOptions.length === 0);

  useEffect(() => {
    setAddWeight(String(defaultWeight));
    setAddReps(String(defaultReps));
  }, [defaultWeight, defaultReps]);

  function deleteExercise() {
    if (!window.confirm(`Delete ${exercise.exercise_name} from this workout?`)) {
      return;
    }

    void onDeleteExercise(exercise.draft_exercise_id);
  }

  return (
    <article className="active-exercise-card">
      <div className="active-exercise-header">
        <div>
          <h2>{exercise.exercise_name}</h2>
          <p>
            {exercise.total_sets} sets · {exercise.total_reps} reps ·{" "}
            {exercise.total_volume.toFixed(1)} kg
            {strengthSummary.bestE1rm !== null && (
              <> · e1RM {formatNumber(strengthSummary.bestE1rm)} kg</>
            )}
          </p>
        </div>
        <button
          aria-label={`Remove ${exercise.exercise_name}`}
          className="icon-delete-button active-exercise-delete-button"
          disabled={disabled}
          onClick={deleteExercise}
          title={`Remove ${exercise.exercise_name}`}
          type="button"
        >
          ×
        </button>
      </div>

      {exercise.sets.length > 0 ? (
        <div className="active-set-table-scroll">
          <table className="active-set-table">
            <thead>
              <tr>
                <th>Set</th>
                <th>Kg</th>
                <th>Reps</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {exercise.sets.map((setEntry) => (
                <tr key={setEntry.id}>
                  <td>{setEntry.set_number}</td>
                  <td>{formatSetOption(setEntry.weight)}</td>
                  <td>{setEntry.reps}</td>
                  <td>
                    <button
                      aria-label={`Remove set ${setEntry.set_number}`}
                      className="icon-delete-button active-set-delete-button"
                      disabled={disabled}
                      onClick={() => void onDeleteSet(setEntry.id)}
                      title={`Remove set ${setEntry.set_number}`}
                      type="button"
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted">No sets yet.</p>
      )}

      <div className="active-set-add-row">
        <select
          aria-label={`${exercise.exercise_name} weight`}
          disabled={disabled}
          onChange={(event) => setAddWeight(event.target.value)}
          value={addWeight}
        >
          {weightOptions.map((option) => (
            <option key={option} value={formatSetOption(option)}>
              {formatSetOption(option)} kg
            </option>
          ))}
        </select>
        <select
          aria-label={`${exercise.exercise_name} repetitions`}
          disabled={disabled}
          onChange={(event) => setAddReps(event.target.value)}
          value={addReps}
        >
          {repsOptions.map((option) => (
            <option key={option} value={formatSetOption(option)}>
              {formatSetOption(option)} reps
            </option>
          ))}
        </select>
        <button
          className="primary-button"
          disabled={disabled}
          onClick={() =>
            void onAddSet(
              exercise.draft_exercise_id,
              Number(addWeight),
              Number(addReps),
            )
          }
          type="button"
        >
          +
        </button>
      </div>
    </article>
  );
}

function ActiveStat({
  className = "metric-neutral",
  label,
  value,
}: {
  className?: string;
  label: string;
  value: number | string;
}) {
  return (
    <div className={`active-workout-stat ${className}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function AnalysisRow({
  label,
  note,
  value,
}: {
  label: string;
  note?: string;
  value: string;
}) {
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
