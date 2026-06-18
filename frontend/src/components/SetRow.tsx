import { useEffect, useState } from "react";

import type { SetEntry } from "../api/types";
import {
  buildRepsOptions,
  buildWeightOptions,
  formatSetOption,
} from "../utils/setOptions";

type SetEditorMode = "input" | "select";
type SetRowVariant = "default" | "legacy-edit";

type SetRowProps = {
  disabled: boolean;
  editorMode?: SetEditorMode;
  repsOptions?: number[];
  setEntry: SetEntry;
  variant?: SetRowVariant;
  weightOptions?: number[];
  onDelete: (setId: number) => void;
  onUpdate?: (setId: number, payload: { weight?: number; reps?: number }) => void;
};

export default function SetRow({
  disabled,
  editorMode = "input",
  onDelete,
  onUpdate,
  repsOptions,
  setEntry,
  variant = "default",
  weightOptions,
}: SetRowProps) {
  const [weight, setWeight] = useState(String(setEntry.weight));
  const [reps, setReps] = useState(String(setEntry.reps));
  const isLegacyEdit = variant === "legacy-edit";

  useEffect(() => {
    setWeight(String(setEntry.weight));
    setReps(String(setEntry.reps));
  }, [setEntry.weight, setEntry.reps]);

  const parsedWeight = Number(weight);
  const parsedReps = Number(reps);
  const valuesAreValid =
    Number.isFinite(parsedWeight) &&
    Number.isInteger(parsedReps) &&
    parsedWeight >= 0 &&
    parsedReps >= 1;
  const valuesChanged =
    parsedWeight !== setEntry.weight || parsedReps !== setEntry.reps;
  const canSave =
    onUpdate !== undefined &&
    valuesAreValid &&
    (isLegacyEdit || valuesChanged);
  const selectWeightOptions = weightOptions ?? buildWeightOptions(setEntry.weight);
  const selectRepsOptions = repsOptions ?? buildRepsOptions(setEntry.reps);

  function deleteSet() {
    if (
      isLegacyEdit &&
      !window.confirm(`Delete set #${setEntry.set_number}?`)
    ) {
      return;
    }

    onDelete(setEntry.id);
  }

  return (
    <div className={`set-row ${isLegacyEdit ? "edit-set-row" : ""}`.trim()}>
      <span>#{setEntry.set_number}</span>
      <label>
        Kg
        {editorMode === "select" ? (
          <select
            aria-label={isLegacyEdit ? `Set ${setEntry.set_number} weight` : undefined}
            className="scroll-select"
            disabled={disabled || !onUpdate}
            onChange={(event) => setWeight(event.target.value)}
            value={weight}
          >
            {selectWeightOptions.map((option) => (
              <option key={option} value={formatSetOption(option)}>
                {formatSetOption(option)}
              </option>
            ))}
          </select>
        ) : (
          <input
            disabled={disabled || !onUpdate}
            inputMode="decimal"
            min="0"
            onChange={(event) => setWeight(event.target.value)}
            step="0.25"
            type="number"
            value={weight}
          />
        )}
      </label>
      <label>
        Reps
        {editorMode === "select" ? (
          <select
            aria-label={isLegacyEdit ? `Set ${setEntry.set_number} repetitions` : undefined}
            className="scroll-select"
            disabled={disabled || !onUpdate}
            onChange={(event) => setReps(event.target.value)}
            value={reps}
          >
            {selectRepsOptions.map((option) => (
              <option key={option} value={formatSetOption(option)}>
                {formatSetOption(option)}
              </option>
            ))}
          </select>
        ) : (
          <input
            disabled={disabled || !onUpdate}
            inputMode="numeric"
            min="1"
            onChange={(event) => setReps(event.target.value)}
            step="1"
            type="number"
            value={reps}
          />
        )}
      </label>
      {onUpdate && (
        <button
          className={
            isLegacyEdit
              ? "edit-set-save-button"
              : "secondary-button compact-button"
          }
          disabled={disabled || !canSave}
          onClick={() =>
            onUpdate(setEntry.id, {
              weight: parsedWeight,
              reps: parsedReps,
            })
          }
          type="button"
        >
          Save
        </button>
      )}
      <button
        className={
          isLegacyEdit
            ? "edit-set-delete-button"
            : "ghost-button compact-button danger-text"
        }
        disabled={disabled}
        onClick={deleteSet}
        type="button"
      >
        {isLegacyEdit ? "×" : "Delete"}
      </button>
    </div>
  );
}
