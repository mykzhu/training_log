import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  createExercise,
  getExerciseProfiles,
  getExercises,
  reorderExercises,
  replaceExerciseWeights,
  updateExercise,
} from "../api/exercises";
import type { Exercise, ExerciseProfile } from "../api/types";
import { formatSetOption, uniqueSortedNumbers } from "../utils/setOptions";

function normalizeWeights(weights: number[]) {
  return uniqueSortedNumbers(
    weights
      .filter((value) => Number.isFinite(value) && value >= 0)
      .map((value) => Math.round(value * 10000) / 10000),
  );
}

function weightsKey(weights: number[]) {
  return JSON.stringify(normalizeWeights(weights));
}

function replaceExerciseInList(exercises: Exercise[], updated: Exercise) {
  return exercises.map((exercise) =>
    exercise.id === updated.id ? updated : exercise,
  );
}

function parseWeight(value: string) {
  const weight = Number(value);
  return Number.isFinite(weight) && weight >= 0 ? weight : null;
}

export default function SettingsPage() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [profiles, setProfiles] = useState<ExerciseProfile[]>([]);
  const [nameDrafts, setNameDrafts] = useState<Record<number, string>>({});
  const [profileDrafts, setProfileDrafts] = useState<Record<number, string>>({});
  const [weightDrafts, setWeightDrafts] = useState<Record<number, number[]>>({});
  const [newWeightDrafts, setNewWeightDrafts] = useState<Record<number, string>>({});
  const [newExerciseName, setNewExerciseName] = useState("");
  const [newExerciseProfile, setNewExerciseProfile] = useState("");
  const [newExerciseWeight, setNewExerciseWeight] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const profileLabels = useMemo(
    () =>
      Object.fromEntries(
        profiles.map((profile) => [profile.key, profile.label]),
      ),
    [profiles],
  );

  function hydrate(responseExercises: Exercise[]) {
    setExercises(responseExercises);
    setNameDrafts(
      Object.fromEntries(
        responseExercises.map((exercise) => [exercise.id, exercise.name]),
      ),
    );
    setProfileDrafts(
      Object.fromEntries(
        responseExercises.map((exercise) => [exercise.id, exercise.profile_key]),
      ),
    );
    setWeightDrafts(
      Object.fromEntries(
        responseExercises.map((exercise) => [exercise.id, exercise.weights]),
      ),
    );
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [exerciseResponse, profileResponse] = await Promise.all([
        getExercises({ includeInactive: true }),
        getExerciseProfiles(),
      ]);
      hydrate(exerciseResponse.exercises);
      setProfiles(profileResponse.profiles);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Failed to load.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function isNameDirty(exercise: Exercise) {
    return (nameDrafts[exercise.id] ?? "") !== exercise.name;
  }

  function isProfileDirty(exercise: Exercise) {
    return (profileDrafts[exercise.id] ?? "") !== exercise.profile_key;
  }

  function isWeightDirty(exercise: Exercise) {
    return (
      weightsKey(weightDrafts[exercise.id] ?? []) !== weightsKey(exercise.weights)
    );
  }

  function isExerciseDirty(exercise: Exercise) {
    return (
      isNameDirty(exercise) ||
      isProfileDirty(exercise) ||
      isWeightDirty(exercise)
    );
  }

  const hasDirtyDrafts = exercises.some(isExerciseDirty);
  const isBusy = pendingAction !== null;

  async function runAction(
    actionKey: string,
    action: () => Promise<void>,
    successMessage: string,
  ) {
    setPendingAction(actionKey);
    setError(null);
    setMessage(null);
    try {
      await action();
      setMessage(successMessage);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPendingAction(null);
    }
  }

  async function addExercise(event?: FormEvent) {
    event?.preventDefault();
    const name = newExerciseName.trim();
    const initialWeight = parseWeight(newExerciseWeight);
    if (!name || initialWeight === null) {
      return;
    }

    await runAction(
      "create",
      async () => {
        const response = await createExercise({
          name,
          is_active: true,
          profile_key: newExerciseProfile || undefined,
          weights: [initialWeight],
        });
        setExercises((current) => [...current, response.exercise]);
        setNameDrafts((current) => ({
          ...current,
          [response.exercise.id]: response.exercise.name,
        }));
        setProfileDrafts((current) => ({
          ...current,
          [response.exercise.id]: response.exercise.profile_key,
        }));
        setWeightDrafts((current) => ({
          ...current,
          [response.exercise.id]: response.exercise.weights,
        }));
        setNewExerciseName("");
        setNewExerciseProfile("");
        setNewExerciseWeight("");
      },
      "Exercise added",
    );
  }

  async function saveDetails(exercise: Exercise) {
    const name = (nameDrafts[exercise.id] ?? "").trim();
    const profileKey = profileDrafts[exercise.id] ?? exercise.profile_key;
    if (!name || (!isNameDirty(exercise) && !isProfileDirty(exercise))) {
      return;
    }

    await runAction(
      `details:${exercise.id}`,
      async () => {
        const response = await updateExercise(exercise.id, {
          name,
          profile_key: profileKey,
        });
        setExercises((current) => replaceExerciseInList(current, response.exercise));
        setNameDrafts((current) => ({
          ...current,
          [exercise.id]: response.exercise.name,
        }));
        setProfileDrafts((current) => ({
          ...current,
          [exercise.id]: response.exercise.profile_key,
        }));
      },
      "Exercise saved",
    );
  }

  async function toggleActive(exercise: Exercise) {
    await runAction(
      `active:${exercise.id}`,
      async () => {
        const response = await updateExercise(exercise.id, {
          is_active: !exercise.is_active,
        });
        setExercises((current) => replaceExerciseInList(current, response.exercise));
      },
      exercise.is_active ? "Exercise deactivated" : "Exercise reactivated",
    );
  }

  async function moveExercise(index: number, direction: -1 | 1) {
    const targetIndex = index + direction;
    if (
      targetIndex < 0 ||
      targetIndex >= exercises.length ||
      hasDirtyDrafts
    ) {
      return;
    }

    await runAction(
      "reorder",
      async () => {
        const reordered = [...exercises];
        [reordered[index], reordered[targetIndex]] = [
          reordered[targetIndex],
          reordered[index],
        ];
        const response = await reorderExercises(
          reordered.map((exercise) => exercise.id),
        );
        hydrate(response.exercises);
      },
      "Exercise order updated",
    );
  }

  function addWeightDraft(exerciseId: number) {
    const value = parseWeight(newWeightDrafts[exerciseId] ?? "");
    if (value === null) {
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

    await runAction(
      `weights:${exercise.id}`,
      async () => {
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
      },
      "Weights saved",
    );
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

      <form className="panel settings-add" onSubmit={addExercise}>
        <label>
          Exercise
          <input
            disabled={pendingAction === "create"}
            onChange={(event) => setNewExerciseName(event.target.value)}
            placeholder="Exercise name"
            value={newExerciseName}
          />
        </label>
        <label>
          Analysis type
          <select
            disabled={pendingAction === "create"}
            onChange={(event) => setNewExerciseProfile(event.target.value)}
            value={newExerciseProfile}
          >
            <option value="">Infer from name</option>
            {profiles.map((profile) => (
              <option key={profile.key} value={profile.key}>
                {profile.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Initial weight
          <input
            disabled={pendingAction === "create"}
            inputMode="decimal"
            min="0"
            onChange={(event) => setNewExerciseWeight(event.target.value)}
            placeholder="0"
            step="0.25"
            type="number"
            value={newExerciseWeight}
          />
        </label>
        <button
          className="primary-button"
          disabled={
            pendingAction === "create" ||
            !newExerciseName.trim() ||
            parseWeight(newExerciseWeight) === null
          }
          type="submit"
        >
          Add
        </button>
      </form>

      {loading && <section className="panel muted">Loading settings...</section>}
      {!loading && exercises.length === 0 && (
        <section className="panel">
          <p>No exercises configured.</p>
          <button className="ghost-button" onClick={load} type="button">
            Retry
          </button>
        </section>
      )}
      {hasDirtyDrafts && (
        <div className="success-banner">
          Save exercise changes before reordering.
        </div>
      )}

      <div className="settings-list">
        {exercises.map((exercise, index) => {
          const weights = weightDrafts[exercise.id] ?? [];
          const detailsChanged =
            isNameDirty(exercise) || isProfileDirty(exercise);
          const weightChanged = isWeightDirty(exercise);
          const detailsPending = pendingAction === `details:${exercise.id}`;
          const activePending = pendingAction === `active:${exercise.id}`;
          const weightsPending = pendingAction === `weights:${exercise.id}`;
          const profileLabel =
            profileLabels[profileDrafts[exercise.id] ?? exercise.profile_key] ??
            "Accessory";

          return (
            <article className="settings-card" key={exercise.id}>
              <div className="settings-card-header">
                <div>
                  <h2>{exercise.name}</h2>
                  <p className="muted">{profileLabel}</p>
                </div>
                <button
                  className={
                    exercise.is_active
                      ? "secondary-button compact-action"
                      : "ghost-button compact-action"
                  }
                  disabled={activePending || isBusy || (weights.length === 0 && !exercise.is_active)}
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
                    disabled={detailsPending}
                    onChange={(event) =>
                      setNameDrafts((current) => ({
                        ...current,
                        [exercise.id]: event.target.value,
                      }))
                    }
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        saveDetails(exercise);
                      }
                    }}
                    value={nameDrafts[exercise.id] ?? ""}
                  />
                </label>
                <label>
                  Analysis type
                  <select
                    disabled={detailsPending}
                    onChange={(event) =>
                      setProfileDrafts((current) => ({
                        ...current,
                        [exercise.id]: event.target.value,
                      }))
                    }
                    value={profileDrafts[exercise.id] ?? exercise.profile_key}
                  >
                    {profiles.map((profile) => (
                      <option key={profile.key} value={profile.key}>
                        {profile.label}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="secondary-button"
                  disabled={
                    detailsPending ||
                    !detailsChanged ||
                    !nameDrafts[exercise.id]?.trim()
                  }
                  onClick={() => saveDetails(exercise)}
                  type="button"
                >
                  Save
                </button>
              </div>

              <div className="settings-order">
                <button
                  className="ghost-button compact-button"
                  disabled={isBusy || hasDirtyDrafts || index === 0}
                  onClick={() => moveExercise(index, -1)}
                  type="button"
                >
                  Up
                </button>
                <button
                  className="ghost-button compact-button"
                  disabled={isBusy || hasDirtyDrafts || index === exercises.length - 1}
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
                      aria-label={`Remove ${formatSetOption(weight)} kg`}
                      className="weight-chip"
                      disabled={weightsPending}
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
                      disabled={weightsPending}
                      inputMode="decimal"
                      min="0"
                      onChange={(event) =>
                        setNewWeightDrafts((current) => ({
                          ...current,
                          [exercise.id]: event.target.value,
                        }))
                      }
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          addWeightDraft(exercise.id);
                        }
                      }}
                      placeholder="0"
                      step="0.25"
                      type="number"
                      value={newWeightDrafts[exercise.id] ?? ""}
                    />
                  </label>
                  <button
                    className="ghost-button"
                    disabled={
                      weightsPending ||
                      parseWeight(newWeightDrafts[exercise.id] ?? "") === null
                    }
                    onClick={() => addWeightDraft(exercise.id)}
                    type="button"
                  >
                    Add
                  </button>
                  <button
                    className="secondary-button"
                    disabled={
                      weightsPending ||
                      !weightChanged ||
                      (exercise.is_active && normalizeWeights(weights).length === 0)
                    }
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
