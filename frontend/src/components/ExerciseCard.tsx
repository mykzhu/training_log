import { useEffect, useState } from "react";

import type { CurrentWorkoutExercise, WorkoutExercise } from "../api/types";
import {
  buildRepsOptions,
  buildWeightOptions,
  formatSetOption,
} from "../utils/setOptions";
import SetRow from "./SetRow";

type ExerciseLike = CurrentWorkoutExercise | WorkoutExercise;
type ExerciseCardVariant = "default" | "legacy-edit";

type ExerciseCardProps = {
  exercise: ExerciseLike;
  disabled: boolean;
  badges?: string[];
  bestE1rm?: number | null;
  setEditorMode?: "input" | "select";
  variant?: ExerciseCardVariant;
  onAddSet: (exerciseId: number, weight: number, reps: number) => void;
  onDeleteExercise: (exerciseId: number) => void;
  onDeleteSet: (setId: number) => void;
  onDuplicateSet: (exerciseId: number) => void;
  onUpdateSet?: (setId: number, payload: { weight?: number; reps?: number }) => void;
};

export default function ExerciseCard({
  badges = [],
  bestE1rm = null,
  exercise,
  disabled,
  onAddSet,
  onDeleteExercise,
  onDeleteSet,
  onDuplicateSet,
  onUpdateSet,
  setEditorMode = "input",
  variant = "default",
}: ExerciseCardProps) {
  const defaultWeight = Number(exercise.default_weight || 0);
  const defaultReps = Number(exercise.default_reps || 10);
  const [addWeight, setAddWeight] = useState(String(defaultWeight));
  const [addReps, setAddReps] = useState(String(defaultReps));
  const actionExerciseId =
    "draft_exercise_id" in exercise
      ? exercise.draft_exercise_id
      : exercise.workout_exercise_id;
  const isLegacyEdit = variant === "legacy-edit";
  const weightOptions = buildWeightOptions(defaultWeight, [
    ...(exercise.configured_weights ?? []),
    ...exercise.sets.map((setEntry) => setEntry.weight),
  ]);
  const repsOptions = buildRepsOptions(defaultReps);

  useEffect(() => {
    setAddWeight(String(defaultWeight));
    setAddReps(String(defaultReps));
  }, [defaultWeight, defaultReps]);

  function deleteExercise() {
    if (
      isLegacyEdit &&
      !window.confirm(`Delete ${exercise.exercise_name} from this workout?`)
    ) {
      return;
    }

    onDeleteExercise(actionExerciseId);
  }

  return (
    <section className={`exercise-card ${isLegacyEdit ? "edit-exercise-card" : ""}`.trim()}>
      <div className="exercise-header">
        <div>
          <div className="exercise-title-row">
            <h2>{exercise.exercise_name}</h2>
            {badges.length > 0 &&
              (isLegacyEdit ? (
                <span className="edit-pr-badge">🏆 {badges.join(", ")}</span>
              ) : (
                <div className="exercise-badges" aria-label="Exercise PRs">
                  {badges.map((badge) => (
                    <span className="pr-badge" key={badge}>
                      {badge}
                    </span>
                  ))}
                </div>
              ))}
          </div>
          <p>
            {exercise.total_sets} sets · {exercise.total_reps} reps ·{" "}
            {exercise.total_volume.toFixed(isLegacyEdit ? 1 : 0)} kg
            {bestE1rm !== null && <> · e1RM {bestE1rm.toFixed(1)} kg</>}
          </p>
        </div>
        <button
          className={
            isLegacyEdit
              ? "danger-button edit-exercise-delete-button"
              : "ghost-button danger-text"
          }
          disabled={disabled}
          onClick={deleteExercise}
          type="button"
        >
          {isLegacyEdit ? "×" : "Delete"}
        </button>
      </div>

      <div className="set-list">
        {exercise.sets.map((setEntry) => (
          <SetRow
            editorMode={setEditorMode}
            key={setEntry.id}
            onDelete={onDeleteSet}
            onUpdate={onUpdateSet}
            variant={variant}
            weightOptions={weightOptions}
            setEntry={setEntry}
            disabled={disabled}
          />
        ))}
      </div>

      <div className={isLegacyEdit ? "edit-set-add-row" : "set-actions"}>
        <label>
          Kg
          <select
            aria-label={isLegacyEdit ? "Weight" : undefined}
            className="scroll-select"
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
        </label>
        <label>
          Reps
          <select
            aria-label={isLegacyEdit ? "Repetitions" : undefined}
            className="scroll-select"
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
        </label>
        <button
          className="secondary-button"
          disabled={disabled}
          onClick={() =>
            onAddSet(actionExerciseId, Number(addWeight), Number(addReps))
          }
          type="button"
        >
          +
        </button>
        {!isLegacyEdit && (
          <button
            className="ghost-button"
            disabled={disabled}
            onClick={() => onDuplicateSet(actionExerciseId)}
            type="button"
          >
            Duplicate
          </button>
        )}
      </div>
    </section>
  );
}
