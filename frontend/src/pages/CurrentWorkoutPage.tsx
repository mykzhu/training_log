import { useEffect, useMemo, useState } from "react";

import {
  addCurrentWorkoutExercise,
  addCurrentWorkoutSet,
  deleteCurrentWorkoutExercise,
  deleteCurrentWorkoutSet,
  duplicateCurrentWorkoutSet,
  finishCurrentWorkout,
  getCurrentWorkout,
  startCurrentWorkout,
  updateCurrentWorkoutMetadata,
  updateCurrentWorkoutSet,
} from "../api/currentWorkout";
import { createExercise, getExercises } from "../api/exercises";
import type { CurrentWorkout, Exercise } from "../api/types";
import ExerciseCard from "../components/ExerciseCard";
import StatCard from "../components/StatCard";
import StatusBadge from "../components/StatusBadge";
import WorkoutTimer from "../components/WorkoutTimer";

export default function CurrentWorkoutPage() {
  const [currentWorkout, setCurrentWorkout] = useState<CurrentWorkout | null>(null);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedExerciseId, setSelectedExerciseId] = useState("");
  const [newExerciseName, setNewExerciseName] = useState("");
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

  const rpeValue = currentWorkout?.session_rpe ?? "";
  const painValue = currentWorkout?.lower_back_pain ?? "";
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

  async function createAndAddExercise() {
    const name = newExerciseName.trim();
    if (!name) {
      return;
    }

    setPending(true);
    setError(null);
    try {
      const response = await createExercise(name);
      const exerciseResponse = await getExercises();
      setExercises(exerciseResponse.exercises);
      setSelectedExerciseId(String(response.exercise.id));
      const workoutResponse = await addCurrentWorkoutExercise(response.exercise.id);
      setCurrentWorkout(workoutResponse);
      setElapsedSeconds(workoutResponse.elapsed_seconds);
      setNewExerciseName("");
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

  if (!currentWorkout) {
    return <section className="panel">Loading</section>;
  }

  if (!currentWorkout.active) {
    return (
      <section className="page-stack">
        {error && <div className="error-banner">{error}</div>}
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
    <section className="page-stack">
      {error && <div className="error-banner">{error}</div>}

      <section className="summary-band">
        <div>
          <StatusBadge tone="danger">Active</StatusBadge>
          <WorkoutTimer elapsedSeconds={elapsedSeconds} />
        </div>
        <div className="summary-actions">
          <button
            className="primary-button finish-button"
            disabled={pending}
            onClick={finishWorkout}
            type="button"
          >
            Finish workout
          </button>
        </div>
      </section>

      <div className="stat-grid">
        <StatCard label="Volume" value={`${currentWorkout.total_volume.toFixed(0)} kg`} />
        <StatCard label="Sets" value={currentWorkout.total_sets} />
        <StatCard label="Reps" value={currentWorkout.total_reps} />
        <StatCard
          label="Load"
          value={currentWorkout.load_metrics?.load_label ?? "—"}
        />
      </div>

      <section className="panel controls-grid">
        <label>
          RPE
          <select
            disabled={pending}
            onChange={(event) =>
              runAction(() =>
                updateCurrentWorkoutMetadata({
                  session_rpe: event.target.value ? Number(event.target.value) : null,
                  lower_back_pain: currentWorkout.lower_back_pain,
                }),
              )
            }
            value={rpeValue}
          >
            <option value="">RPE</option>
            {Array.from({ length: 10 }, (_, index) => index + 1).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label>
          Back
          <select
            disabled={pending}
            onChange={(event) =>
              runAction(() =>
                updateCurrentWorkoutMetadata({
                  session_rpe: currentWorkout.session_rpe,
                  lower_back_pain: event.target.value
                    ? Number(event.target.value)
                    : null,
                }),
              )
            }
            value={painValue}
          >
            <option value="">Back Pain</option>
            {Array.from({ length: 11 }, (_, index) => index).map((value) => (
              <option key={value} value={value}>
                Back Pain {value}/10
              </option>
            ))}
          </select>
        </label>
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
          disabled={disabled || !selectedExerciseId}
          onClick={addSelectedExercise}
          type="button"
        >
          Add
        </button>
        <label>
          New
          <input
            disabled={pending}
            onChange={(event) => setNewExerciseName(event.target.value)}
            placeholder="New exercise name"
            value={newExerciseName}
          />
        </label>
        <button
          className="ghost-button"
          disabled={disabled || !newExerciseName.trim()}
          onClick={createAndAddExercise}
          type="button"
        >
          Create
        </button>
      </section>

      <div className="exercise-list">
        {currentWorkout.exercises.map((exercise) => (
          <ExerciseCard
            disabled={pending}
            exercise={exercise}
            key={exercise.draft_exercise_id}
            setEditorMode="select"
            onAddSet={(exerciseId, weight, reps) =>
              runAction(() => addCurrentWorkoutSet(exerciseId, { weight, reps }))
            }
            onDeleteExercise={(exerciseId) =>
              runAction(() => deleteCurrentWorkoutExercise(exerciseId))
            }
            onDeleteSet={(setId) => runAction(() => deleteCurrentWorkoutSet(setId))}
            onDuplicateSet={(exerciseId) =>
              runAction(() => duplicateCurrentWorkoutSet(exerciseId))
            }
            onUpdateSet={(setId, payload) =>
              runAction(() => updateCurrentWorkoutSet(setId, payload))
            }
          />
        ))}
      </div>
    </section>
  );
}
