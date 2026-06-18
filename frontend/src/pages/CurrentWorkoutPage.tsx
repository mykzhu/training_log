import { useEffect, useMemo, useState } from "react";

import {
  addCurrentWorkoutExercise,
  addCurrentWorkoutSet,
  clearCurrentWorkout,
  deleteCurrentWorkoutExercise,
  deleteCurrentWorkoutSet,
  finishCurrentWorkout,
  getCurrentWorkout,
  startCurrentWorkout,
  updateCurrentWorkoutMetadata,
} from "../api/currentWorkout";
import { createExercise, getExercises } from "../api/exercises";
import type {
  CurrentWorkout,
  NextWorkoutRecommendation,
  RecoveryContext,
  Exercise,
} from "../api/types";
import LegacyActiveWorkoutView from "../components/LegacyActiveWorkoutView";

function formatNumber(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return Number(value).toFixed(digits);
}

function formatRatio(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return `${Number(value).toFixed(2)}×`;
}

function metricClassForLoad(loadLabel: string | null | undefined) {
  if (loadLabel === "Light" || loadLabel === "Below usual") {
    return "metric-green";
  }
  if (loadLabel === "Normal") {
    return "metric-lime";
  }
  if (loadLabel === "Medium") {
    return "metric-yellow";
  }
  if (loadLabel === "Hard" || loadLabel === "Elevated") {
    return "metric-orange";
  }
  if (loadLabel === "Very hard" || loadLabel === "High") {
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

function metricClassForBackStress(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "metric-neutral";
  }
  if (value < 4) {
    return "metric-green";
  }
  if (value < 8) {
    return "metric-yellow";
  }
  if (value < 12) {
    return "metric-orange";
  }

  return "metric-red";
}

function metricClassForRatio(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "metric-neutral";
  }
  if (value < 0.75) {
    return "metric-green";
  }
  if (value <= 1.25) {
    return "metric-lime";
  }
  if (value <= 1.5) {
    return "metric-orange";
  }

  return "metric-red";
}

function metricClassForConfidence(value: string) {
  if (value === "high") {
    return "metric-green";
  }
  if (value === "medium") {
    return "metric-lime";
  }

  return "metric-neutral";
}

function metricClassForReadiness(status: string) {
  if (status === "progress") {
    return "metric-green";
  }
  if (status === "progress_carefully") {
    return "metric-lime";
  }
  if (status === "repeat") {
    return "metric-yellow";
  }
  if (status === "deload") {
    return "metric-orange";
  }

  return "metric-red";
}

export default function CurrentWorkoutPage() {
  const [currentWorkout, setCurrentWorkout] = useState<CurrentWorkout | null>(null);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedExerciseId, setSelectedExerciseId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  async function load() {
    const [workoutResponse, exerciseResponse] = await Promise.all([
      getCurrentWorkout(),
      getExercises(),
    ]);
    setCurrentWorkout(workoutResponse);
    setElapsedSeconds(workoutResponse.elapsed_seconds);
    setExercises(exerciseResponse.exercises);
    if (!selectedExerciseId && exerciseResponse.exercises.length > 0) {
      setSelectedExerciseId(String(exerciseResponse.exercises[0].id));
    }
  }

  useEffect(() => {
    load().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Failed to load.");
    });
  }, []);

  useEffect(() => {
    if (!currentWorkout?.active) {
      return;
    }

    const interval = window.setInterval(() => {
      setElapsedSeconds((value) => value + 1);
    }, 1000);

    return () => window.clearInterval(interval);
  }, [currentWorkout?.active]);

  const disabled = pending || currentWorkout === null;

  const exerciseOptions = useMemo(
    () => exercises.map((exercise) => ({ value: String(exercise.id), label: exercise.name })),
    [exercises],
  );

  async function runAction(action: () => Promise<CurrentWorkout>) {
    setPending(true);
    setError(null);
    try {
      const response = await action();
      setCurrentWorkout(response);
      setElapsedSeconds(response.elapsed_seconds);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPending(false);
    }
  }

  async function addSelectedExercise() {
    const exerciseId = Number(selectedExerciseId);
    if (!exerciseId) {
      return;
    }
    await runAction(() => addCurrentWorkoutExercise(exerciseId));
  }

  async function createNewExercise(name: string) {
    const cleanName = name.trim();
    if (!cleanName) {
      return;
    }

    setPending(true);
    setError(null);
    try {
      const response = await createExercise({ name: cleanName });
      const exerciseResponse = await getExercises();
      setExercises(exerciseResponse.exercises);
      setSelectedExerciseId(String(response.exercise.id));
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPending(false);
    }
  }

  async function finishWorkout() {
    setPending(true);
    setError(null);
    try {
      const response = await finishCurrentWorkout();
      setCurrentWorkout(response.current_workout);
      setElapsedSeconds(0);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPending(false);
    }
  }

  async function cancelWorkout() {
    if (!window.confirm("Discard this active workout and all logged sets?")) {
      return;
    }

    await runAction(clearCurrentWorkout);
  }

  if (!currentWorkout) {
    return <section className="panel">Loading</section>;
  }

  if (!currentWorkout.active) {
    return (
      <section className="page-stack">
        {error && <div className="error-banner">{error}</div>}
        {currentWorkout.recovery_context && (
          <RecoveryContextCard context={currentWorkout.recovery_context} />
        )}
        {currentWorkout.next_workout_recommendation && (
          <NextWorkoutCard
            recommendation={currentWorkout.next_workout_recommendation}
          />
        )}
        <section className="panel ready-card">
          <h2>Ready?</h2>
          <p className="muted">
            Workout will be created in the database only after you press Finish.
          </p>
          <button
            className="primary-button start-button"
            disabled={pending}
            onClick={() => runAction(startCurrentWorkout)}
            type="button"
          >
            Start workout
          </button>
        </section>
      </section>
    );
  }

  return (
    <LegacyActiveWorkoutView
      currentWorkout={currentWorkout}
      disabled={disabled}
      elapsedSeconds={elapsedSeconds}
      error={error}
      exerciseOptions={exerciseOptions}
      selectedExerciseId={selectedExerciseId}
      onAddExercise={addSelectedExercise}
      onAddSet={(exerciseId, weight, reps) =>
        runAction(() => addCurrentWorkoutSet(exerciseId, { weight, reps }))
      }
      onCancel={cancelWorkout}
      onCreateExercise={createNewExercise}
      onDeleteExercise={(exerciseId) =>
        runAction(() => deleteCurrentWorkoutExercise(exerciseId))
      }
      onDeleteSet={(setId) => runAction(() => deleteCurrentWorkoutSet(setId))}
      onFinish={finishWorkout}
      onSaveMetadata={(sessionRpe, lowerBackPain) =>
        runAction(() =>
          updateCurrentWorkoutMetadata({
            session_rpe: sessionRpe,
            lower_back_pain: lowerBackPain,
          }),
        )
      }
      onSelectExercise={setSelectedExerciseId}
    />
  );
}

type RecoveryContextCardProps = {
  context: RecoveryContext;
};

function RecoveryContextCard({ context }: RecoveryContextCardProps) {
  return (
    <section className="panel context-card">
      <div className="panel-header">
        <div>
          <h2>Recovery context</h2>
          <div className="muted small">
            Time-aware context for future recommendations
          </div>
        </div>
        {context.previous_workout_id && (
          <a className="card-link" href={`/workouts/${context.previous_workout_id}`}>
            Last workout
          </a>
        )}
      </div>

      <div className="recovery-grid">
        <MetricTile value={context.previous_gap_label} label="since last workout" />
        <MetricTile
          className={metricClassForLoad(context.last_7d.load_label)}
          value={formatNumber(context.last_7d.load_score)}
          label="7d load"
        />
        <MetricTile
          className={metricClassForBackStress(context.last_7d.back_stress_score)}
          value={formatNumber(context.last_7d.back_stress_score)}
          label="7d back stress"
        />
      </div>

      <div className="recovery-grid">
        <MetricTile
          className={metricClassForRatio(context.relative_load.acute_to_baseline)}
          value={formatRatio(context.relative_load.acute_to_baseline)}
          label="load vs baseline"
        />
        <MetricTile
          className={metricClassForRatio(context.relative_load.acute_back_to_baseline)}
          value={formatRatio(context.relative_load.acute_back_to_baseline)}
          label="back vs baseline"
        />
        <MetricTile
          className={metricClassForConfidence(
            context.relative_load.baseline_confidence,
          )}
          value={context.relative_load.baseline_confidence}
          label="baseline confidence"
        />
      </div>

      <div className="recovery-grid">
        <MetricTile
          value={context.last_7d.workout_count}
          label="workouts in 7d"
        />
        <MetricTile
          className={metricClassForScore(context.last_7d.avg_rpe)}
          value={formatNumber(context.last_7d.avg_rpe)}
          label="avg RPE"
        />
        <MetricTile
          className={metricClassForScore(context.last_7d.avg_back_pain)}
          value={formatNumber(context.last_7d.avg_back_pain)}
          label="avg back"
        />
      </div>

      <div className="recovery-grid">
        <MetricTile
          value={formatNumber(context.previous_21d.weekly_load_equivalent)}
          label="21d weekly load"
        />
        <MetricTile
          value={formatNumber(context.last_42d.weekly_load_equivalent)}
          label="42d weekly load"
        />
        <MetricTile
          value={formatNumber(context.last_42d.weekly_workout_average)}
          label="workouts per week"
        />
      </div>

      <p className="recovery-hint">{context.hint}</p>
    </section>
  );
}

type NextWorkoutCardProps = {
  recommendation: NextWorkoutRecommendation;
};

function NextWorkoutCard({ recommendation }: NextWorkoutCardProps) {
  return (
    <section className="panel context-card">
      <div className="panel-header">
        <div>
          <h2>Next workout</h2>
          <div className="muted small">
            Rule-based recommendation from your latest workout
          </div>
        </div>
        {recommendation.last_workout_id && (
          <a
            className="card-link"
            href={`/workouts/${recommendation.last_workout_id}`}
          >
            Source
          </a>
        )}
      </div>

      <div className="recovery-grid">
        <MetricTile
          className={metricClassForReadiness(recommendation.status)}
          value={recommendation.title}
          label="status"
        />
        <MetricTile
          className={metricClassForReadiness(recommendation.status)}
          value={recommendation.score}
          label="readiness"
        />
        <MetricTile
          value={recommendation.exercise_recommendations.length}
          label="exercises"
        />
      </div>

      <p className="recovery-hint">{recommendation.summary}</p>

      {recommendation.reasons.length > 0 && (
        <ul className="recommendation-reasons">
          {recommendation.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}

      {recommendation.exercise_recommendations.length > 0 && (
        <div className="recommendation-list">
          {recommendation.exercise_recommendations.map((exercise) => (
            <article className="recommendation-item" key={exercise.exercise_name}>
              <div className="recommendation-item-header">
                <strong>{exercise.exercise_name}</strong>
                <span className="recommendation-action">
                  {exercise.action_label}
                </span>
              </div>
              <div className="recommendation-target">{exercise.target}</div>
              <div className="recommendation-reason">
                Gap: {exercise.gap_label} · usual: {exercise.usual_gap_label} ·{" "}
                {exercise.gap_status_label}
              </div>
              <div className="recommendation-reason">
                Trend: {exercise.progression_label} · e1RM{" "}
                {exercise.e1rm_change_label} · volume{" "}
                {exercise.volume_change_label}
              </div>
              <div className="recommendation-reason">{exercise.reason}</div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

type MetricTileProps = {
  className?: string;
  label: string;
  value: number | string;
};

function MetricTile({
  className = "metric-neutral",
  label,
  value,
}: MetricTileProps) {
  return (
    <div className={`recovery-item ${className}`}>
      <strong>{value}</strong>
      <span className="muted">{label}</span>
    </div>
  );
}
