import { useEffect, useState } from "react";

import {
  createExercise,
  getExercises,
  reorderExercises,
  replaceExerciseWeights,
  updateExercise,
} from "../api/exercises";
import type { Exercise } from "../api/types";
import { formatSetOption, uniqueSortedNumbers } from "../utils/setOptions";

function normalizeWeights(weights: number[]) {
  return uniqueSortedNumbers(
    weights
      .filter((value) => Number.isFinite(value) && value >= 0)
      .map((value) => Math.round(value * 10000) / 10000),
  );
}

function replaceExerciseInList(exercises: Exercise[], updated: Exercise) {
  return exercises.map((exercise) =>
    exercise.id === updated.id ? updated : exercise,
  );
}

export default function SettingsPage() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [nameDrafts, setNameDrafts] = useState<Record<number, string>>({});
  const [weightDrafts, setWeightDrafts] = useState<Record<number, number[]>>({});
  const [newWeightDrafts, setNewWeightDrafts] = useState<Record<number, string>>({});
  const [newExerciseName, setNewExerciseName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function hydrate(responseExercises: Exercise[]) {
    setExercises(responseExercises);
    setNameDrafts(
      Object.fromEntries(
        responseExercises.map((exercise) => [exercise.id, exercise.name]),
      ),
    );
    setWeightDrafts(
      Object.fromEntries(
        responseExercises.map((exercise) => [exercise.id, exercise.weights]),
      ),
    );
  }

  async function load() {
    const response = await getExercises({ includeInactive: true });
    hydrate(response.exercises);
  }

  useEffect(() => {
    load().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Failed to load.");
    });
  }, []);

  async function runAction(action: () => Promise<void>, successMessage: string) {
    setPending(true);
    setError(null);
    setMessage(null);
    try {
      await action();
      setMessage(successMessage);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPending(false);
    }
  }

  async function addExercise() {
    const name = newExerciseName.trim();
    if (!name) {
      return;
    }

    await runAction(async () => {
      const response = await createExercise({ name, is_active: true, weights: [] });
      setExercises((current) => [...current, response.exercise]);
      setNameDrafts((current) => ({
        ...current,
        [response.exercise.id]: response.exercise.name,
      }));
      setWeightDrafts((current) => ({
        ...current,
        [response.exercise.id]: response.exercise.weights,
      }));
      setNewExerciseName("");
    }, "Exercise added");
  }

  async function saveName(exercise: Exercise) {
    const name = (nameDrafts[exercise.id] ?? "").trim();
    if (!name || name === exercise.name) {
      return;
    }

    await runAction(async () => {
      const response = await updateExercise(exercise.id, { name });
      setExercises((current) => replaceExerciseInList(current, response.exercise));
      setNameDrafts((current) => ({
        ...current,
        [exercise.id]: response.exercise.name,
      }));
    }, "Exercise renamed");
  }

  async function toggleActive(exercise: Exercise) {
    await runAction(async () => {
      const response = await updateExercise(exercise.id, {
        is_active: !exercise.is_active,
      });
      setExercises((current) => replaceExerciseInList(current, response.exercise));
    }, exercise.is_active ? "Exercise deactivated" : "Exercise reactivated");
  }

  async function moveExercise(index: number, direction: -1 | 1) {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= exercises.length) {
      return;
    }

    await runAction(async () => {
      const reordered = [...exercises];
      [reordered[index], reordered[targetIndex]] = [
        reordered[targetIndex],
        reordered[index],
      ];
      const response = await reorderExercises(reordered.map((exercise) => exercise.id));
      hydrate(response.exercises);
    }, "Exercise order updated");
  }

  function addWeightDraft(exerciseId: number) {
    const value = Number(newWeightDrafts[exerciseId]);
    if (!Number.isFinite(value) || value < 0) {
      return;
    }

    setWeightDrafts((current) => ({
      ...current,
      [exerciseId]: normalizeWeights([...(current[exerciseId] ?? []), value]),
    }));
    setNewWeightDrafts((current) => ({
      ...current,
      [exerciseId]: "",
    }));
  }

  function removeWeightDraft(exerciseId: number, weight: number) {
    setWeightDrafts((current) => ({
      ...current,
      [exerciseId]: (current[exerciseId] ?? []).filter((value) => value !== weight),
    }));
  }

  async function saveWeights(exercise: Exercise) {
    const weights = normalizeWeights(weightDrafts[exercise.id] ?? []);

    await runAction(async () => {
      const response = await replaceExerciseWeights(exercise.id, weights);
      const updated = {
        ...exercise,
        weights: response.weights,
      };
      setExercises((current) => replaceExerciseInList(current, updated));
      setWeightDrafts((current) => ({
        ...current,
        [exercise.id]: response.weights,
      }));
    }, "Weights saved");
  }

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p className="muted">Exercises and weights</p>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      <section className="panel settings-add">
        <label>
          Exercise
          <input
            disabled={pending}
            onChange={(event) => setNewExerciseName(event.target.value)}
            placeholder="Exercise name"
            value={newExerciseName}
          />
        </label>
        <button
          className="primary-button"
          disabled={pending || !newExerciseName.trim()}
          onClick={addExercise}
          type="button"
        >
          Add exercise
        </button>
      </section>

      <div className="settings-list">
        {exercises.map((exercise, index) => {
          const weights = weightDrafts[exercise.id] ?? [];
          const weightChanged =
            JSON.stringify(normalizeWeights(weights)) !==
            JSON.stringify(exercise.weights);
          const nameChanged = (nameDrafts[exercise.id] ?? "") !== exercise.name;

          return (
            <article className="settings-card" key={exercise.id}>
              <div className="settings-card-header">
                <div>
                  <h2>{exercise.name}</h2>
                  <p className="muted">
                    {exercise.profile_key} · order {exercise.sort_order}
                  </p>
                </div>
                <button
                  className={
                    exercise.is_active
                      ? "secondary-button compact-action"
                      : "ghost-button compact-action"
                  }
                  disabled={pending}
                  onClick={() => toggleActive(exercise)}
                  type="button"
                >
                  {exercise.is_active ? "Active" : "Inactive"}
                </button>
              </div>

              <div className="settings-row">
                <label>
                  Name
                  <input
                    disabled={pending}
                    onChange={(event) =>
                      setNameDrafts((current) => ({
                        ...current,
                        [exercise.id]: event.target.value,
                      }))
                    }
                    value={nameDrafts[exercise.id] ?? ""}
                  />
                </label>
                <button
                  className="secondary-button"
                  disabled={pending || !nameChanged || !nameDrafts[exercise.id]?.trim()}
                  onClick={() => saveName(exercise)}
                  type="button"
                >
                  Save name
                </button>
              </div>

              <div className="settings-order">
                <button
                  className="ghost-button compact-button"
                  disabled={pending || index === 0}
                  onClick={() => moveExercise(index, -1)}
                  type="button"
                >
                  Up
                </button>
                <button
                  className="ghost-button compact-button"
                  disabled={pending || index === exercises.length - 1}
                  onClick={() => moveExercise(index, 1)}
                  type="button"
                >
                  Down
                </button>
              </div>

              <section className="settings-weights">
                <h3>Weights</h3>
                <div className="weight-chip-list">
                  {weights.length === 0 && (
                    <span className="muted small">No presets configured.</span>
                  )}
                  {weights.map((weight) => (
                    <button
                      className="weight-chip"
                      disabled={pending}
                      key={weight}
                      onClick={() => removeWeightDraft(exercise.id, weight)}
                      type="button"
                    >
                      {formatSetOption(weight)} kg
                    </button>
                  ))}
                </div>

                <div className="settings-row">
                  <label>
                    New weight
                    <input
                      disabled={pending}
                      inputMode="decimal"
                      min="0"
                      onChange={(event) =>
                        setNewWeightDrafts((current) => ({
                          ...current,
                          [exercise.id]: event.target.value,
                        }))
                      }
                      placeholder="0"
                      step="0.25"
                      type="number"
                      value={newWeightDrafts[exercise.id] ?? ""}
                    />
                  </label>
                  <button
                    className="ghost-button"
                    disabled={pending || !(newWeightDrafts[exercise.id] ?? "").trim()}
                    onClick={() => addWeightDraft(exercise.id)}
                    type="button"
                  >
                    Add weight
                  </button>
                  <button
                    className="secondary-button"
                    disabled={pending || !weightChanged}
                    onClick={() => saveWeights(exercise)}
                    type="button"
                  >
                    Save weights
                  </button>
                </div>
              </section>
            </article>
          );
        })}
      </div>
    </section>
  );
}
