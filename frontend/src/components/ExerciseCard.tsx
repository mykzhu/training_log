import { useEffect, useState } from "react";

import type { CurrentWorkoutExercise, WorkoutExercise } from "../api/types";
import {
  buildRepsOptions,
  buildWeightOptions,
  formatSetOption,
} from "../utils/setOptions";
import SetRow from "./SetRow";

type ExerciseLike = CurrentWorkoutExercise | WorkoutExercise;

type ExerciseCardProps = {
  exercise: ExerciseLike;
  disabled: boolean;
  badges?: string[];
  setEditorMode?: "input" | "select";
  onAddSet: (exerciseId: number, weight: number, reps: number) => void;
  onDeleteExercise: (exerciseId: number) => void;
  onDeleteSet: (setId: number) => void;
  onDuplicateSet: (exerciseId: number) => void;
  onUpdateSet?: (setId: number, payload: { weight?: number; reps?: number }) => void;
};

export default function ExerciseCard({
  badges = [],
  exercise,
  disabled,
  onAddSet,
  onDeleteExercise,
  onDeleteSet,
  onDuplicateSet,
  onUpdateSet,
  setEditorMode = "input",
}: ExerciseCardProps) {
  const defaultWeight = Number(exercise.default_weight || 0);
  const defaultReps = Number(exercise.default_reps || 10);
  const [addWeight, setAddWeight] = useState(String(defaultWeight));
  const [addReps, setAddReps] = useState(String(defaultReps));
  const actionExerciseId =
    "draft_exercise_id" in exercise
      ? exercise.draft_exercise_id
      : exercise.workout_exercise_id;
  const weightOptions = buildWeightOptions(defaultWeight, [
    ...(exercise.configured_weights ?? []),
    ...exercise.sets.map((setEntry) => setEntry.weight),
  ]);
  const repsOptions = buildRepsOptions(defaultReps);

  useEffect(() => {
    setAddWeight(String(defaultWeight));
    setAddReps(String(defaultReps));
  }, [defaultWeight, defaultReps]);

  return (
    <section className="exercise-card">
      <div className="exercise-header">
        <div>
          <div className="exercise-title-row">
            <h2>{exercise.exercise_name}</h2>
            {badges.length > 0 && (
              <div className="exercise-badges" aria-label="Exercise PRs">
                {badges.map((badge) => (
                  <span className="pr-badge" key={badge}>
                    {badge}
                  </span>
                ))}
              </div>
            )}
          </div>
          <p>
            {exercise.total_sets} sets · {exercise.total_reps} reps ·{" "}
            {exercise.total_volume.toFixed(0)} kg
          </p>
        </div>
        <button
          className="ghost-button danger-text"
          disabled={disabled}
          onClick={() => onDeleteExercise(actionExerciseId)}
          type="button"
        >
          Delete
        </button>
      </div>

      <div className="set-list">
        {exercise.sets.map((setEntry) => (
          <SetRow
            editorMode={setEditorMode}
            key={setEntry.id}
            onDelete={onDeleteSet}
            onUpdate={onUpdateSet}
            weightOptions={weightOptions}
            setEntry={setEntry}
            disabled={disabled}
          />
        ))}
      </div>

      <div className="set-actions">
        <label>
          Kg
          <select
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
        <button
          className="ghost-button"
          disabled={disabled}
          onClick={() => onDuplicateSet(actionExerciseId)}
          type="button"
        >
          Duplicate
        </button>
      </div>
    </section>
  );
}
