import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getExercises } from "../api/exercises";
import type {
  Exercise,
  SetEntry,
  WorkoutDetail,
  WorkoutExercise,
  WorkoutSummary,
} from "../api/types";
import {
  addWorkoutExercise,
  addWorkoutExerciseSet,
  deleteWorkout,
  deleteWorkoutExercise,
  deleteWorkoutSet,
  getWorkout,
  getWorkouts,
  updateWorkout,
  updateWorkoutSet,
} from "../api/workouts";
import ExerciseCard from "../components/ExerciseCard";
import ReadonlyWorkoutDetail, {
  PostWorkoutRecommendationCard,
} from "../components/ReadonlyWorkoutDetail";
import StatCard from "../components/StatCard";
import { rpeOptionLabel } from "../utils/rpeLabels";
import "../edit-workout-legacy.css";

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

type SaveStatus = "idle" | "saving" | "saved" | "error";

function parseOptionalScore(value: string) {
  return value === "" ? null : Number(value);
}

function saveStatusLabel(status: SaveStatus) {
  if (status === "saving") {
    return "Saving...";
  }
  if (status === "saved") {
    return "Workout saved";
  }
  if (status === "error") {
    return "Could not save workout";
  }

  return "No changes";
}

function recalculateExercise(exercise: WorkoutExercise): WorkoutExercise {
  const sets = exercise.sets.map((setEntry, index) => ({
    ...setEntry,
    set_number: index + 1,
  }));
  return {
    ...exercise,
    sets,
    total_sets: sets.length,
    total_reps: sets.reduce((sum, setEntry) => sum + setEntry.reps, 0),
    total_volume: sets.reduce(
      (sum, setEntry) => sum + setEntry.weight * setEntry.reps,
      0,
    ),
  };
}

function recalculateDetail(detail: WorkoutDetail): WorkoutDetail {
  const exercises = detail.exercises.map(recalculateExercise);
  return {
    ...detail,
    exercises,
    total_sets: exercises.reduce((sum, exercise) => sum + exercise.total_sets, 0),
    total_reps: exercises.reduce((sum, exercise) => sum + exercise.total_reps, 0),
    total_volume: exercises.reduce(
      (sum, exercise) => sum + exercise.total_volume,
      0,
    ),
  };
}

function cloneDetail(detail: WorkoutDetail): WorkoutDetail {
  return {
    ...detail,
    workout: { ...detail.workout },
    exercises: detail.exercises.map((exercise) => ({
      ...exercise,
      sets: exercise.sets.map((setEntry) => ({ ...setEntry })),
    })),
  };
}

type HistoryPageProps = {
  initialEditMode: boolean;
  initialWorkoutId: number | null;
};

export default function HistoryPage({
  initialEditMode,
  initialWorkoutId,
}: HistoryPageProps) {
  const navigate = useNavigate();

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
  const [originalDetail, setOriginalDetail] = useState<WorkoutDetail | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const nextTempWorkoutExerciseId = useRef(-1);
  const nextTempSetId = useRef(-1);

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
    const nextDetail = cloneDetail(response);
    setDetail(nextDetail);
    setOriginalDetail(cloneDetail(nextDetail));
    setCreatedAt(toDateTimeLocal(response.workout.created_at));
    setSessionRpe(String(response.workout.session_rpe ?? ""));
    setLowerBackPain(String(response.workout.lower_back_pain ?? ""));
    setIsDirty(false);
    setSaveStatus("idle");
  }

  function markDirty() {
    setIsDirty(true);
    setSaveStatus("idle");
    setMessage(null);
  }

  function updateDraft(mutator: (current: WorkoutDetail) => WorkoutDetail) {
    setDetail((current) => {
      if (!current) {
        return current;
      }
      return recalculateDetail(mutator(cloneDetail(current)));
    });
    markDirty();
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
      setOriginalDetail(null);
      setIsDirty(false);
      setSaveStatus("idle");
      return;
    }

    setPending(true);
    setError(null);
    getWorkout(selectedWorkoutId)
      .then(hydrateDetail)
      .catch((reason: unknown) => {
        setDetail(null);
        setError(reason instanceof Error ? reason.message : "Failed to load workout.");
      })
      .finally(() => setPending(false));
  }, [selectedWorkoutId]);

  useEffect(() => {
    if (!isDirty) {
      return;
    }

    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  function updateCreatedAt(value: string) {
    setCreatedAt(value);
    markDirty();
  }

  function updateSessionRpe(value: string) {
    setSessionRpe(value);
    markDirty();
  }

  function updateLowerBackPain(value: string) {
    setLowerBackPain(value);
    markDirty();
  }

  function updateDraftSet(
    setId: number,
    payload: { weight?: number; reps?: number },
  ) {
    updateDraft((current) => ({
      ...current,
      exercises: current.exercises.map((exercise) => ({
        ...exercise,
        sets: exercise.sets.map((setEntry) =>
          setEntry.id === setId ? { ...setEntry, ...payload } : setEntry,
        ),
      })),
    }));
  }

  function addDraftSet(workoutExerciseId: number, weight: number, reps: number) {
    updateDraft((current) => ({
      ...current,
      exercises: current.exercises.map((exercise) => {
        if (exercise.workout_exercise_id !== workoutExerciseId) {
          return exercise;
        }

        const now = new Date().toISOString();
        const setEntry: SetEntry = {
          id: nextTempSetId.current--,
          workout_exercise_id: workoutExerciseId,
          set_number: exercise.sets.length + 1,
          weight,
          reps,
          created_at: now,
        };
        return {
          ...exercise,
          sets: [...exercise.sets, setEntry],
        };
      }),
    }));
  }

  function deleteDraftSet(setId: number) {
    updateDraft((current) => ({
      ...current,
      exercises: current.exercises.map((exercise) => ({
        ...exercise,
        sets: exercise.sets.filter((setEntry) => setEntry.id !== setId),
      })),
    }));
  }

  function deleteDraftExercise(workoutExerciseId: number) {
    updateDraft((current) => ({
      ...current,
      exercises: current.exercises.filter(
        (exercise) => exercise.workout_exercise_id !== workoutExerciseId,
      ),
    }));
  }

  async function saveWorkoutChanges() {
    if (!detail || !originalDetail) {
      return;
    }

    setPending(true);
    setError(null);
    setMessage(null);
    setSaveStatus("saving");

    try {
      let latest = await updateWorkout(detail.workout.id, {
        created_at: createdAt,
        session_rpe: parseOptionalScore(sessionRpe),
        lower_back_pain: parseOptionalScore(lowerBackPain),
      });

      const originalExercises = new Map(
        originalDetail.exercises.map((exercise) => [
          exercise.workout_exercise_id,
          exercise,
        ]),
      );
      const draftExercisesById = new Map(
        detail.exercises.map((exercise) => [
          exercise.workout_exercise_id,
          exercise,
        ]),
      );

      for (const originalExercise of originalDetail.exercises) {
        if (!draftExercisesById.has(originalExercise.workout_exercise_id)) {
          latest = await deleteWorkoutExercise(
            detail.workout.id,
            originalExercise.workout_exercise_id,
          );
        }
      }

      const usedWorkoutExerciseIds = new Set(
        latest.exercises.map((exercise) => exercise.workout_exercise_id),
      );

      for (const draftExercise of detail.exercises) {
        let realWorkoutExerciseId = draftExercise.workout_exercise_id;

        if (draftExercise.workout_exercise_id < 0) {
          latest = await addWorkoutExercise(
            detail.workout.id,
            draftExercise.exercise_id,
          );
          const addedExercise = [...latest.exercises]
            .reverse()
            .find(
              (exercise) =>
                exercise.exercise_id === draftExercise.exercise_id &&
                !usedWorkoutExerciseIds.has(exercise.workout_exercise_id),
            );
          if (!addedExercise) {
            throw new Error("Could not map added exercise.");
          }
          realWorkoutExerciseId = addedExercise.workout_exercise_id;
          usedWorkoutExerciseIds.add(realWorkoutExerciseId);
        }

        const originalExercise = originalExercises.get(realWorkoutExerciseId);
        const originalSets = new Map(
          (originalExercise?.sets ?? []).map((setEntry) => [setEntry.id, setEntry]),
        );
        const draftSetIds = new Set(draftExercise.sets.map((setEntry) => setEntry.id));

        if (originalExercise) {
          for (const originalSet of originalExercise.sets) {
            if (!draftSetIds.has(originalSet.id)) {
              latest = await deleteWorkoutSet(originalSet.id);
            }
          }
        }

        for (const draftSet of draftExercise.sets) {
          if (draftSet.id < 0) {
            latest = await addWorkoutExerciseSet(realWorkoutExerciseId, {
              weight: draftSet.weight,
              reps: draftSet.reps,
            });
            continue;
          }

          const originalSet = originalSets.get(draftSet.id);
          if (
            originalSet &&
            (originalSet.weight !== draftSet.weight ||
              originalSet.reps !== draftSet.reps)
          ) {
            latest = await updateWorkoutSet(draftSet.id, {
              weight: draftSet.weight,
              reps: draftSet.reps,
            });
          }
        }
      }

      hydrateDetail(latest);
      await loadWorkouts();
      setSaveStatus("saved");
      setMessage("Workout saved");
    } catch (reason: unknown) {
      setSaveStatus("error");
      setError(reason instanceof Error ? reason.message : "Could not save workout.");
    } finally {
      setPending(false);
    }
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
      navigate("/history");
      await loadWorkouts();
      setMessage("Workout deleted");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPending(false);
    }
  }

  function openWorkout(workoutId: number, editMode = false) {
    setSelectedWorkoutId(workoutId);
    navigate(editMode ? `/workouts/${workoutId}/edit` : `/workouts/${workoutId}`);
  }

  function backToHistory() {
    if (isDirty && !window.confirm("Discard unsaved workout changes?")) {
      return;
    }
    setSelectedWorkoutId(null);
    setDetail(null);
    navigate("/history");
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

    const exercise = exercises.find((candidate) => candidate.id === exerciseId);
    if (!exercise) {
      return;
    }

    updateDraft((current) => ({
      ...current,
      exercises: [
        ...current.exercises,
        {
          workout_exercise_id: nextTempWorkoutExerciseId.current--,
          exercise_id: exercise.id,
          exercise_name: exercise.name,
          profile_key: exercise.profile_key,
          position: current.exercises.length + 1,
          sets: [],
          total_sets: 0,
          total_reps: 0,
          total_volume: 0,
          default_weight: exercise.weights[0] ?? 0,
          default_reps: 10,
          configured_weights: exercise.weights,
        },
      ],
    }));
  }

  return (
    <section className="page-stack">
      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      {selectedWorkoutId === null && (
        <div className="table-list history-list">
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
                    onClick={() => openWorkout(workout.id, true)}
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
                <span>finished</span>
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

      {selectedWorkoutId !== null && !detail && !error && (
        <section className="panel">Loading workout</section>
      )}

      {selectedWorkoutId !== null && !detail && error && (
        <section className="panel">Workout unavailable.</section>
      )}

      {selectedWorkoutId !== null && detail && !initialEditMode && (
        <ReadonlyWorkoutDetail
          detail={detail}
          disabled={pending}
          onDelete={deleteSelectedWorkout}
          onEdit={() => openWorkout(detail.workout.id, true)}
        />
      )}

      {selectedWorkoutId !== null && detail && initialEditMode && (
        <section className="page-stack edit-workout-page">
          <section className="panel edit-workout-save-panel">
            <div>
              <h2>Edit workout</h2>
              <p className={isDirty ? "edit-dirty-text" : "muted"}>
                {isDirty ? "Unsaved changes" : saveStatusLabel(saveStatus)}
              </p>
            </div>
            <button
              className="primary-button edit-workout-save-button"
              disabled={pending || !isDirty || !createdAt}
              onClick={saveWorkoutChanges}
              type="button"
            >
              {saveStatus === "saving" ? "Saving..." : "Save workout"}
            </button>
          </section>

          <div className="edit-workout-meta">
            <span>{formatDateTime(detail.workout.created_at)}</span>
            <span>{detail.workout.finished_at ? "finished" : "active"}</span>
          </div>

          <div className="edit-workout-stat-grid">
            <StatCard
              label="duration"
              value={formatClockDuration(detail.workout.duration_seconds)}
            />
            <StatCard label="sets" value={detail.total_sets} />
            <StatCard label="reps" value={detail.total_reps} />
            <StatCard label="kg volume" value={detail.total_volume.toFixed(1)} />
            <StatCard
              className={scoreMetricClass(detail.workout.session_rpe)}
              label="RPE"
              value={formatScoreOutOfTen(detail.workout.session_rpe)}
            />
            <StatCard
              className={scoreMetricClass(detail.workout.lower_back_pain)}
              label="Back Pain"
              value={formatScoreOutOfTen(detail.workout.lower_back_pain)}
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
            <PostWorkoutRecommendationCard detail={detail} />
          </section>

          <section className="panel edit-workout-info-card">
            <h2>Workout info</h2>
            <label>
              Date and time
              <input
                disabled={pending}
                onChange={(event) => updateCreatedAt(event.target.value)}
                type="datetime-local"
                value={createdAt}
              />
            </label>
            <div className="edit-workout-two-column">
              <label>
                Session RPE
                <select
                  className={scoreMetricClass(
                    sessionRpe ? Number(sessionRpe) : null,
                  )}
                  disabled={pending}
                  onChange={(event) => updateSessionRpe(event.target.value)}
                  value={sessionRpe}
                >
                  <option value="">—</option>
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
                  className={scoreMetricClass(
                    lowerBackPain ? Number(lowerBackPain) : null,
                  )}
                  disabled={pending}
                  onChange={(event) => updateLowerBackPain(event.target.value)}
                  value={lowerBackPain}
                >
                  <option value="">—</option>
                  {Array.from({ length: 11 }, (_, index) => index).map(
                    (value) => (
                      <option key={value} value={value}>
                        Back Pain {value}/10
                      </option>
                    ),
                  )}
                </select>
              </label>
            </div>
          </section>

          <section className="panel edit-add-exercise-card">
            <h2>Add exercise</h2>
            <div className="edit-add-exercise-row">
              <select
                aria-label="Exercise"
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
              <button
                className="secondary-button"
                disabled={pending || !selectedExerciseId}
                onClick={addSelectedExercise}
                type="button"
              >
                Add
              </button>
            </div>
          </section>

          <div className="exercise-list">
            {detail.exercises.map((exercise) => (
              <ExerciseCard
                badges={prFlagsByExercise.get(exercise.exercise_id) ?? []}
                bestE1rm={
                  detail.analysis.exercises.find(
                    (candidate) => candidate.exercise_id === exercise.exercise_id,
                  )?.best_e1rm ?? null
                }
                disabled={pending}
                exercise={exercise}
                key={exercise.workout_exercise_id}
                onAddSet={addDraftSet}
                onDeleteExercise={deleteDraftExercise}
                onDeleteSet={deleteDraftSet}
                onDuplicateSet={() => undefined}
                onUpdateSet={updateDraftSet}
                setEditorMode="select"
                variant="legacy-edit"
              />
            ))}
          </div>

          <section className="panel edit-workout-navigation">
            <button
              className="ghost-button"
              disabled={pending}
              onClick={backToHistory}
              type="button"
            >
              Back to history
            </button>
            <button
              className="ghost-button"
              disabled={pending}
              onClick={() => openWorkout(detail.workout.id)}
              type="button"
            >
              View summary
            </button>
          </section>

          <section className="panel edit-workout-danger">
            <h2>Danger zone</h2>
            <button
              className="danger-button"
              disabled={pending}
              onClick={deleteSelectedWorkout}
              type="button"
            >
              Delete workout
            </button>
          </section>
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
