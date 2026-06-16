import { useEffect, useMemo, useState } from "react";

import { getExercises } from "../api/exercises";
import type { Exercise, WorkoutDetail, WorkoutSummary } from "../api/types";
import {
  addWorkoutExercise,
  addWorkoutExerciseSet,
  deleteWorkout,
  deleteWorkoutExercise,
  deleteWorkoutSet,
  duplicateWorkoutExerciseSet,
  getWorkout,
  getWorkouts,
  updateWorkout,
  updateWorkoutSet,
} from "../api/workouts";
import ExerciseCard from "../components/ExerciseCard";
import StatCard from "../components/StatCard";
import StatusBadge from "../components/StatusBadge";
import { rpeOptionLabel } from "../utils/rpeLabels";

function toDateTimeLocal(value: string) {
  return value.slice(0, 16);
}

function formatNumber(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return Number(value).toFixed(digits);
}

function formatDuration(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) {
    return "—";
  }

  const totalMinutes = Math.floor(seconds / 60);
  if (totalMinutes < 1) {
    return `${seconds}s`;
  }

  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) {
    return `${minutes}m`;
  }

  return minutes === 0 ? `${hours}h` : `${hours}h ${minutes}m`;
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

function formatOptionalScore(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : String(value);
}

function formatScoreOutOfTen(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${value}/10`;
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

function formatBestSet(setEntry: { weight: number; reps: number } | null) {
  if (!setEntry) {
    return "—";
  }

  if (setEntry.weight > 0) {
    return `${formatNumber(setEntry.weight)} × ${setEntry.reps}`;
  }

  return `${setEntry.reps} reps`;
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

function pushHistoryRoute(path: string) {
  window.history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

type HistoryPageProps = {
  initialWorkoutId: number | null;
};

export default function HistoryPage({ initialWorkoutId }: HistoryPageProps) {
  const [workouts, setWorkouts] = useState<WorkoutSummary[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedWorkoutId, setSelectedWorkoutId] = useState<number | null>(
    initialWorkoutId,
  );
  const [detail, setDetail] = useState<WorkoutDetail | null>(null);
  const [selectedExerciseId, setSelectedExerciseId] = useState("");
  const [createdAt, setCreatedAt] = useState("");
  const [sessionRpe, setSessionRpe] = useState("");
  const [lowerBackPain, setLowerBackPain] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const exerciseOptions = useMemo(
    () => exercises.map((exercise) => ({ value: String(exercise.id), label: exercise.name })),
    [exercises],
  );
  const prFlagsByExercise = useMemo(() => {
    const flags = new Map<number, string[]>();

    for (const exercise of detail?.analysis.exercises ?? []) {
      if (exercise.pr_flags.length > 0) {
        flags.set(exercise.exercise_id, exercise.pr_flags);
      }
    }

    return flags;
  }, [detail]);

  function hydrateDetail(response: WorkoutDetail) {
    setDetail(response);
    setCreatedAt(toDateTimeLocal(response.workout.created_at));
    setSessionRpe(String(response.workout.session_rpe ?? ""));
    setLowerBackPain(String(response.workout.lower_back_pain ?? ""));
  }

  async function loadWorkouts() {
    const response = await getWorkouts();
    setWorkouts(response.workouts);
  }

  async function loadExercises() {
    const response = await getExercises();
    setExercises(response.exercises);
    if (!selectedExerciseId && response.exercises.length > 0) {
      setSelectedExerciseId(String(response.exercises[0].id));
    }
  }

  useEffect(() => {
    Promise.all([loadWorkouts(), loadExercises()]).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Failed to load.");
    });
  }, []);

  useEffect(() => {
    setSelectedWorkoutId(initialWorkoutId);
  }, [initialWorkoutId]);

  useEffect(() => {
    if (selectedWorkoutId === null) {
      setDetail(null);
      return;
    }

    setPending(true);
    setError(null);
    getWorkout(selectedWorkoutId)
      .then(hydrateDetail)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Failed to load workout.");
      })
      .finally(() => setPending(false));
  }, [selectedWorkoutId]);

  async function runDetailAction(action: () => Promise<WorkoutDetail>) {
    setPending(true);
    setError(null);
    setMessage(null);
    try {
      const response = await action();
      hydrateDetail(response);
      await loadWorkouts();
      setMessage("Workout updated");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPending(false);
    }
  }

  async function saveMetadata() {
    if (!detail) {
      return;
    }

    await runDetailAction(() =>
      updateWorkout(detail.workout.id, {
        created_at: createdAt,
        session_rpe: sessionRpe ? Number(sessionRpe) : null,
        lower_back_pain: lowerBackPain ? Number(lowerBackPain) : null,
      }),
    );
  }

  async function deleteSelectedWorkout() {
    if (!detail || !window.confirm("Delete this workout?")) {
      return;
    }

    setPending(true);
    setError(null);
    setMessage(null);
    try {
      await deleteWorkout(detail.workout.id);
      setSelectedWorkoutId(null);
      setDetail(null);
      pushHistoryRoute("/history");
      await loadWorkouts();
      setMessage("Workout deleted");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPending(false);
    }
  }

  function openWorkout(workoutId: number) {
    setSelectedWorkoutId(workoutId);
    pushHistoryRoute(`/workouts/${workoutId}`);
  }

  function backToHistory() {
    setSelectedWorkoutId(null);
    setDetail(null);
    pushHistoryRoute("/history");
  }

  async function deleteWorkoutFromList(workout: WorkoutSummary) {
    if (
      !window.confirm(`Delete workout #${workout.id} and all its sets?`)
    ) {
      return;
    }

    setPending(true);
    setError(null);
    setMessage(null);
    try {
      await deleteWorkout(workout.id);
      await loadWorkouts();
      setMessage("Workout deleted");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPending(false);
    }
  }

  async function addSelectedExercise() {
    if (!detail) {
      return;
    }

    const exerciseId = Number(selectedExerciseId);
    if (!exerciseId) {
      return;
    }

    await runDetailAction(() => addWorkoutExercise(detail.workout.id, exerciseId));
  }

  function openSettings() {
    window.history.pushState(null, "", "/settings");
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  return (
    <section className="page-stack">
      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      {selectedWorkoutId === null && (
        <div className="table-list">
          {workouts.map((workout) => (
            <article className="history-card" key={workout.id}>
              <div className="history-card-header">
                <button
                  className="history-title-button"
                  disabled={pending}
                  onClick={() => openWorkout(workout.id)}
                  type="button"
                >
                  Workout #{workout.id}
                </button>
                <div className="history-actions">
                  <button
                    className="primary-button compact-action"
                    disabled={pending}
                    onClick={() => openWorkout(workout.id)}
                    type="button"
                  >
                    Edit
                  </button>
                  <button
                    className="danger-button compact-action"
                    disabled={pending}
                    onClick={() => deleteWorkoutFromList(workout)}
                    type="button"
                  >
                    Delete
                  </button>
                </div>
              </div>

              <div className="history-meta">
                <span>{formatDateTime(workout.created_at)}</span>
                <StatusBadge tone="good">finished</StatusBadge>
                <span
                  className={`status-badge ${loadMetricClass(
                    workout.load_metrics.load_label,
                  )}`}
                >
                  {workout.load_metrics.load_label} ·{" "}
                  {formatNumber(workout.load_metrics.load_score)}
                </span>
                <span>· Duration: {formatClockDuration(workout.duration_seconds)}</span>
              </div>

              <div className="history-stat-grid">
                <HistoryStat value={workout.exercises_count} label="exercises" />
                <HistoryStat value={workout.total_sets} label="sets" />
                <HistoryStat value={workout.total_reps} label="reps" />
                <HistoryStat
                  value={workout.total_volume.toFixed(1)}
                  label="kg"
                />
                <HistoryStat
                  className={scoreMetricClass(workout.session_rpe)}
                  value={formatScoreOutOfTen(workout.session_rpe)}
                  label="RPE"
                />
                <HistoryStat
                  className={scoreMetricClass(workout.lower_back_pain)}
                  value={formatScoreOutOfTen(workout.lower_back_pain)}
                  label="Back Pain"
                />
              </div>
            </article>
          ))}
        </div>
      )}

      {selectedWorkoutId !== null && !detail && (
        <section className="panel">Loading workout</section>
      )}

      {selectedWorkoutId !== null && detail && (
        <section className="page-stack">
          <div className="row-actions">
            <button
              className="ghost-button"
              disabled={pending}
              onClick={backToHistory}
              type="button"
            >
              Back to history
            </button>
          </div>

          <section className="summary-band">
            <div>
              <StatusBadge>{detail.load_metrics.load_label}</StatusBadge>
              <div>
                <h2>{detail.workout.workout_date}</h2>
                <p>
                  {detail.total_sets} sets · {detail.total_reps} reps ·{" "}
                  {detail.total_volume.toFixed(0)} kg
                </p>
              </div>
            </div>
            <button
              className="ghost-button danger-text"
              disabled={pending}
              onClick={deleteSelectedWorkout}
              type="button"
            >
              Delete
            </button>
          </section>

          <div className="stat-grid">
            <StatCard
              label="Duration"
              value={formatDuration(detail.workout.duration_seconds)}
            />
            <StatCard label="Volume" value={`${detail.total_volume.toFixed(0)} kg`} />
            <StatCard label="Sets" value={detail.total_sets} />
            <StatCard label="Reps" value={detail.total_reps} />
            <StatCard
              label="Avg Load"
              value={
                detail.total_reps
                  ? `${formatNumber(detail.total_volume / detail.total_reps)} kg`
                  : "—"
              }
            />
            <StatCard label="Load" value={detail.load_metrics.load_label} />
            <StatCard
              label="Back Stress"
              value={formatNumber(detail.load_metrics.back_stress_score)}
            />
            <StatCard
              label="RPE"
              value={formatOptionalScore(detail.workout.session_rpe)}
            />
            <StatCard
              label="Back Pain"
              value={formatOptionalScore(detail.workout.lower_back_pain)}
            />
          </div>

          <section className="panel analysis-card">
            <h2>Analysis</h2>
            <section
              className={`analysis-section ${loadMetricClass(
                detail.load_metrics.load_label,
              )}`}
            >
              <h3>Workout load</h3>
              <div className="analysis-row">
                <div>
                  <div className="analysis-main">
                    {detail.load_metrics.load_label}
                  </div>
                  <div className="muted small">overall training difficulty</div>
                </div>
                <div className="analysis-value">
                  {formatNumber(detail.load_metrics.load_score)}
                </div>
              </div>
              <div className="analysis-row">
                <div>
                  <div className="analysis-main">Compound score</div>
                  <div className="muted small">base exercise contribution</div>
                </div>
                <div className="analysis-value">
                  {formatNumber(detail.load_metrics.compound_score)}
                </div>
              </div>
              <div className="analysis-row">
                <div>
                  <div className="analysis-main">Intensity score</div>
                  <div className="muted small">relative to your history</div>
                </div>
                <div className="analysis-value">
                  {detail.load_metrics.intensity_score === null
                    ? "—"
                    : `${formatNumber(detail.load_metrics.intensity_score, 0)}%`}
                </div>
              </div>
              <div className="analysis-row">
                <div>
                  <div className="analysis-main">Back stress</div>
                  <div className="muted small">deadlift / squat / row stress</div>
                </div>
                <div className="analysis-value">
                  {formatNumber(detail.load_metrics.back_stress_score)}
                </div>
              </div>
              <p className="analysis-note">
                Load score uses exercise type, reps, relative intensity and RPE.
                This is more useful than tonnage alone when comparing heavy
                compound work with light accessory volume.
              </p>
            </section>

            <div className="analysis-grid">
              <section className="analysis-section">
                <h3>Best sets</h3>
                {detail.analysis.exercises.length === 0 ? (
                  <div className="muted">No sets yet.</div>
                ) : (
                  detail.analysis.exercises.map((exercise) => (
                    <div className="analysis-row" key={exercise.exercise_id}>
                      <div>
                        <div className="analysis-main">
                          {exercise.exercise_name}
                        </div>
                        <div className="muted small">
                          {exercise.best_e1rm_set
                            ? "best reliable strength set"
                            : "best by set volume"}
                        </div>
                      </div>
                      <div className="analysis-value">
                        {formatBestSet(exercise.best_set)}
                      </div>
                    </div>
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
                      <div className="analysis-row" key={exercise.exercise_id}>
                        <div>
                          <div className="analysis-main">
                            {exercise.exercise_name}
                          </div>
                          <div className="muted small">
                            from {formatBestSet(exercise.best_e1rm_set)}
                          </div>
                        </div>
                        <div className="analysis-value">
                          {formatNumber(exercise.best_e1rm)} kg
                        </div>
                      </div>
                    ))
                )}
                <p className="analysis-note">
                  e1RM is shown only for weighted sets with 3-12 reps.
                </p>
              </section>

              <section className="analysis-section">
                <h3>PRs</h3>
                {detail.analysis.prs.length === 0 ? (
                  <div className="muted">No PRs in this workout.</div>
                ) : (
                  detail.analysis.prs.map((pr) => (
                    <div
                      className="analysis-row"
                      key={`${pr.exercise_name}-${pr.type}`}
                    >
                      <div className="analysis-main">{pr.exercise_name}</div>
                      <div className="analysis-value">{pr.type}</div>
                    </div>
                  ))
                )}
              </section>

              <section className="analysis-section">
                <h3>Intensity</h3>
                <div className="analysis-row">
                  <div className="analysis-main">Average weight per rep</div>
                  <div className="analysis-value">
                    {detail.total_reps
                      ? `${formatNumber(detail.total_volume / detail.total_reps)} kg/rep`
                      : "—"}
                  </div>
                </div>
              </section>
            </div>
          </section>

          <section className="panel controls-grid">
            <label>
              Started
              <input
                disabled={pending}
                onChange={(event) => setCreatedAt(event.target.value)}
                type="datetime-local"
                value={createdAt}
              />
            </label>
            <label>
              RPE
              <select
                disabled={pending}
                onChange={(event) => setSessionRpe(event.target.value)}
                value={sessionRpe}
              >
                <option value="">-</option>
                {Array.from({ length: 10 }, (_, index) => index + 1).map((value) => (
                  <option key={value} value={value}>
                    {rpeOptionLabel(value)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Back
              <select
                disabled={pending}
                onChange={(event) => setLowerBackPain(event.target.value)}
                value={lowerBackPain}
              >
                <option value="">-</option>
                {Array.from({ length: 11 }, (_, index) => index).map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="primary-button"
              disabled={pending || !createdAt}
              onClick={saveMetadata}
              type="button"
            >
              Save
            </button>
          </section>

          <section className="panel add-exercise">
            <label>
              Exercise
              <select
                disabled={pending || exerciseOptions.length === 0}
                onChange={(event) => setSelectedExerciseId(event.target.value)}
                value={selectedExerciseId}
              >
                {exerciseOptions.map((exercise) => (
                  <option key={exercise.value} value={exercise.value}>
                    {exercise.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="secondary-button"
              disabled={pending || !selectedExerciseId}
              onClick={addSelectedExercise}
              type="button"
            >
              Add
            </button>
            <button
              className="ghost-button"
              disabled={pending}
              onClick={openSettings}
              type="button"
            >
              Settings
            </button>
          </section>

          <div className="exercise-list">
            {detail.exercises.map((exercise) => (
              <ExerciseCard
                badges={prFlagsByExercise.get(exercise.exercise_id) ?? []}
                disabled={pending}
                exercise={exercise}
                key={exercise.workout_exercise_id}
                onAddSet={(exerciseId, weight, reps) =>
                  runDetailAction(() =>
                    addWorkoutExerciseSet(exerciseId, { weight, reps }),
                  )
                }
                onDeleteExercise={(exerciseId) =>
                  runDetailAction(() =>
                    deleteWorkoutExercise(detail.workout.id, exerciseId),
                  )
                }
                onDeleteSet={(setId) => runDetailAction(() => deleteWorkoutSet(setId))}
                onDuplicateSet={(exerciseId) =>
                  runDetailAction(() => duplicateWorkoutExerciseSet(exerciseId))
                }
                onUpdateSet={(setId, payload) =>
                  runDetailAction(() => updateWorkoutSet(setId, payload))
                }
              />
            ))}
          </div>
        </section>
      )}
    </section>
  );
}

type HistoryStatProps = {
  className?: string;
  label: string;
  value: number | string;
};

function HistoryStat({
  className = "metric-neutral",
  label,
  value,
}: HistoryStatProps) {
  return (
    <div className={`history-stat ${className}`}>
      <strong>{value}</strong>
      <span className="muted">{label}</span>
    </div>
  );
}
