import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

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
import { syncGarmin } from "../api/garmin";
import type {
  CurrentWorkout,
  GarminDailyMetric,
  GarminRecoverySnapshot,
  NextWorkoutRecommendation,
  RecoveryContext,
  Exercise,
  SuggestedSet,
} from "../api/types";
import LegacyActiveWorkoutView from "../components/LegacyActiveWorkoutView";

function formatGarminDate(value: string | null | undefined) {
  if (!value) {
    return "-";
  }

  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatGarminDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatGarminMetric(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function garminBatteryLabel(metric: GarminDailyMetric) {
  if (metric.body_battery_start === null && metric.body_battery_end === null) {
    return null;
  }

  return `BB ${formatGarminMetric(metric.body_battery_start)} -> ${formatGarminMetric(
    metric.body_battery_end,
  )}`;
}

function garminMetricSummary(metric: GarminDailyMetric | null) {
  if (!metric) {
    return "No data";
  }

  const parts = [
    metric.resting_heart_rate === null
      ? null
      : `RHR ${formatGarminMetric(metric.resting_heart_rate)}`,
    metric.hrv_ms === null ? null : `HRV ${formatGarminMetric(metric.hrv_ms, 1)}`,
    metric.stress_avg === null ? null : `Stress ${formatGarminMetric(metric.stress_avg)}`,
    garminBatteryLabel(metric),
    metric.steps === null ? null : `Steps ${formatGarminMetric(metric.steps)}`,
  ].filter(Boolean);

  return parts.length ? parts.join(" / ") : "No values";
}

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

function formatSuggestedWeight(value: number) {
  if (Number.isInteger(value)) {
    return String(value);
  }

  return Number(value).toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function formatSuggestedSet(set: SuggestedSet) {
  if (set.weight <= 0) {
    return `${set.set_number}) ${set.reps} reps`;
  }

  return `${set.set_number}) ${formatSuggestedWeight(set.weight)} kg × ${set.reps}`;
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

function formatScoreDelta(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  return value > 0 ? `+${value}` : String(value);
}

function metricClassForGarminDelta(value: number | null | undefined) {
  if (value === null || value === undefined || value === 0) {
    return "metric-neutral";
  }

  if (value > 0) {
    return "metric-green";
  }

  return value <= -10 ? "metric-red" : "metric-orange";
}

function shouldShowGarminAdjustment(status: string | undefined) {
  return Boolean(status && status !== "not_available");
}

function metricClassForReadiness(status: string) {
  if (status === "needs_feedback") {
    return "metric-orange";
  }
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

function baselineRatioClass(
  context: RecoveryContext,
  value: number | null | undefined,
) {
  const displayValue =
    value ??
    (value === context.relative_load.acute_to_baseline
      ? context.relative_load.display_acute_to_baseline
      : context.relative_load.display_acute_back_to_baseline);

  if (
    !context.relative_load.baseline_is_reliable ||
    displayValue === null ||
    displayValue === undefined
  ) {
    return "metric-neutral";
  }

  return metricClassForRatio(displayValue);
}

function formatBaselineRatio(
  context: RecoveryContext,
  value: number | null | undefined,
) {
  const displayValue =
    value ??
    (value === context.relative_load.acute_to_baseline
      ? context.relative_load.display_acute_to_baseline
      : context.relative_load.display_acute_back_to_baseline);

  if (
    !context.relative_load.baseline_is_reliable ||
    displayValue === null ||
    displayValue === undefined
  ) {
    return "building";
  }

  return formatRatio(displayValue);
}

export default function CurrentWorkoutPage() {
  const [currentWorkout, setCurrentWorkout] = useState<CurrentWorkout | null>(null);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedExerciseId, setSelectedExerciseId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [garminError, setGarminError] = useState<string | null>(null);
  const [garminPending, setGarminPending] = useState(false);
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

  async function syncGarminRecovery() {
    setGarminPending(true);
    setGarminError(null);
    try {
      await syncGarmin(35);
      const response = await getCurrentWorkout();
      setCurrentWorkout(response);
      setElapsedSeconds(response.elapsed_seconds);
    } catch (reason: unknown) {
      setGarminError(
        reason instanceof Error ? reason.message : "Garmin sync failed.",
      );
    } finally {
      setGarminPending(false);
    }
  }

  async function addSelectedExercise() {
    const exerciseId = Number(selectedExerciseId);
    if (!exerciseId) {
      return;
    }
    await runAction(() => addCurrentWorkoutExercise(exerciseId));
  }

  async function createNewExercise(name: string, initialWeight: number) {
    const cleanName = name.trim();
    if (!cleanName || !Number.isFinite(initialWeight) || initialWeight < 0) {
      return;
    }

    setPending(true);
    setError(null);
    try {
      const response = await createExercise({
        name: cleanName,
        weights: [initialWeight],
      });
      const exerciseResponse = await getExercises();
      const workoutResponse = await addCurrentWorkoutExercise(response.exercise.id);
      setExercises(exerciseResponse.exercises);
      setSelectedExerciseId(String(response.exercise.id));
      setCurrentWorkout(workoutResponse);
      setElapsedSeconds(workoutResponse.elapsed_seconds);
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
        {currentWorkout.garmin_recovery && (
          <GarminRecoveryCard
            error={garminError}
            onSync={syncGarminRecovery}
            pending={garminPending}
            snapshot={currentWorkout.garmin_recovery}
          />
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
          <Link className="card-link" to={`/workouts/${context.previous_workout_id}`}>
            Last workout
          </Link>
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
        <MetricTile
          className={baselineRatioClass(context, context.relative_load.acute_to_baseline)}
          value={formatBaselineRatio(context, context.relative_load.acute_to_baseline)}
          label="load vs baseline"
        />
        <MetricTile
          className={baselineRatioClass(context, context.relative_load.acute_back_to_baseline)}
          value={formatBaselineRatio(context, context.relative_load.acute_back_to_baseline)}
          label="back vs baseline"
        />
        <MetricTile
          className={metricClassForConfidence(
            context.relative_load.baseline_confidence,
          )}
          value={context.relative_load.baseline_confidence}
          label="baseline confidence"
        />
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

type GarminRecoveryCardProps = {
  error: string | null;
  onSync: () => void;
  pending: boolean;
  snapshot: GarminRecoverySnapshot;
};

function GarminRecoveryCard({
  error,
  onSync,
  pending,
  snapshot,
}: GarminRecoveryCardProps) {
  return (
    <section className="panel context-card garmin-recovery-card">
      <div className="panel-header">
        <div>
          <h2>Garmin recovery</h2>
          <div className="muted small">{snapshot.message}</div>
        </div>
        <button
          className="ghost-button compact-action"
          disabled={pending || !snapshot.connected}
          onClick={onSync}
          type="button"
        >
          {pending ? "Syncing" : "Sync"}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="recovery-grid">
        <MetricTile
          className={snapshot.connected ? "metric-green" : "metric-neutral"}
          value={snapshot.connected ? "connected" : "off"}
          label="Garmin"
        />
        <MetricTile
          value={formatGarminDateTime(snapshot.last_synced_at)}
          label="last sync"
        />
        <MetricTile
          value={snapshot.sample_count_35d}
          label="35d samples"
        />
      </div>

      <div className="garmin-metric-list">
        <GarminMetricRow label="Today" metric={snapshot.today} />
        <GarminMetricRow label="Yesterday" metric={snapshot.yesterday} />
        <GarminMetricRow label="Latest" metric={snapshot.latest} />
      </div>
    </section>
  );
}

type GarminMetricRowProps = {
  label: string;
  metric: GarminDailyMetric | null;
};

function GarminMetricRow({ label, metric }: GarminMetricRowProps) {
  return (
    <div className="garmin-metric-row">
      <strong>{label}</strong>
      <span>{metric ? formatGarminDate(metric.date) : "-"}</span>
      <span className="muted">{garminMetricSummary(metric)}</span>
    </div>
  );
}

type NextWorkoutCardProps = {
  recommendation: NextWorkoutRecommendation;
};

function nextWorkoutSubtitle(status: string) {
  if (status === "needs_feedback") {
    return "Latest workout feedback is required first";
  }
  if (status === "recovery") {
    return "Recovery-first guidance";
  }

  return "Rule-based recommendation from your latest workout";
}

function NextWorkoutCard({ recommendation }: NextWorkoutCardProps) {
  const garminAdjustment = recommendation.garmin_adjustment;
  const showGarminAdjustment = shouldShowGarminAdjustment(
    garminAdjustment?.status,
  );
  const showExerciseTargets =
    recommendation.status !== "recovery" &&
    recommendation.status !== "needs_feedback" &&
    recommendation.exercise_recommendations.length > 0;
  const actionValue =
    recommendation.status === "recovery"
      ? "pause"
      : recommendation.status === "needs_feedback"
        ? "log"
        : recommendation.exercise_recommendations.length;
  const actionLabel = showExerciseTargets ? "exercises" : "action";

  return (
    <section className="panel context-card">
      <div className="panel-header">
        <div>
          <h2>Next workout</h2>
          <div className="muted small">
            {nextWorkoutSubtitle(recommendation.status)}
          </div>
        </div>
        {recommendation.last_workout_id && (
          <Link
            className="card-link"
            to={`/workouts/${recommendation.last_workout_id}`}
          >
            Source
          </Link>
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
          value={recommendation.score ?? "—"}
          label="readiness"
        />
        <MetricTile
          value={actionValue}
          label={actionLabel}
        />
        {showGarminAdjustment && garminAdjustment && (
          <MetricTile
            className={metricClassForGarminDelta(garminAdjustment.score_delta)}
            value={formatScoreDelta(garminAdjustment.score_delta)}
            label="Garmin adj"
          />
        )}
      </div>

      <p className="recovery-hint">{recommendation.summary}</p>
      {showGarminAdjustment && garminAdjustment && (
        <p className="recovery-hint">Garmin: {garminAdjustment.summary}</p>
      )}

      {recommendation.reasons.length > 0 && (
        <ul className="recommendation-reasons">
          {recommendation.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}

      {showExerciseTargets && (
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
                {exercise.gap_status_label} · interval confidence:{" "}
                {exercise.interval_confidence}
              </div>
              <div className="recommendation-reason">
                Strategy: {exercise.target_strategy} · sets:{" "}
                {exercise.suggested_sets.length}
              </div>
              {exercise.suggested_sets.length > 0 && (
                <div className="recommendation-reason">
                  Suggested:{" "}
                  {exercise.suggested_sets.map(formatSuggestedSet).join(" · ")}
                </div>
              )}
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
