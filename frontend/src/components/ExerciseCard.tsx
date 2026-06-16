import type { CurrentWorkoutExercise, WorkoutExercise } from "../api/types";
import SetRow from "./SetRow";

type ExerciseLike = CurrentWorkoutExercise | WorkoutExercise;

type ExerciseCardProps = {
  exercise: ExerciseLike;
  disabled: boolean;
  onAddSet: (exerciseId: number, weight: number, reps: number) => void;
  onDeleteExercise: (exerciseId: number) => void;
  onDeleteSet: (setId: number) => void;
  onDuplicateSet: (exerciseId: number) => void;
  onUpdateSet?: (setId: number, payload: { weight?: number; reps?: number }) => void;
};

export default function ExerciseCard({
  exercise,
  disabled,
  onAddSet,
  onDeleteExercise,
  onDeleteSet,
  onDuplicateSet,
  onUpdateSet,
}: ExerciseCardProps) {
  const defaultWeight = Number(exercise.default_weight || 0);
  const defaultReps = Number(exercise.default_reps || 10);
  const actionExerciseId =
    "draft_exercise_id" in exercise
      ? exercise.draft_exercise_id
      : exercise.workout_exercise_id;

  return (
    <section className="exercise-card">
      <div className="exercise-header">
        <div>
          <h2>{exercise.exercise_name}</h2>
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
            key={setEntry.id}
            onDelete={onDeleteSet}
            onUpdate={onUpdateSet}
            setEntry={setEntry}
            disabled={disabled}
          />
        ))}
      </div>

      <div className="set-actions">
        <button
          className="secondary-button"
          disabled={disabled}
          onClick={() => onAddSet(actionExerciseId, defaultWeight, defaultReps)}
          type="button"
        >
          Add {defaultWeight} kg x {defaultReps}
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
