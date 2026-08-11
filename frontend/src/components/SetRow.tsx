import { useEffect, useState } from "react";

import type { ExerciseMeasurementType, SetEntry } from "../api/types";
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
  measurementType?: ExerciseMeasurementType;
  repsUnit?: string;
  onDelete: (setId: number) => void;
  onUpdate?: (setId: number, payload: { weight?: number; reps?: number }) => void;
  updateOnChange?: boolean;
};

function measurementUsesWeight(measurementType: ExerciseMeasurementType) {
  return (
    measurementType === "weighted_reps" ||
    measurementType === "loaded_carry_time" ||
    measurementType === "loaded_carry_distance"
  );
}

function quantityLabel(measurementType: ExerciseMeasurementType) {
  if (measurementType === "loaded_carry_time" || measurementType === "duration_only") {
    return "Seconds";
  }

  if (measurementType === "loaded_carry_distance") {
    return "Meters";
  }

  return "Reps";
}

export default function SetRow({
  disabled,
  editorMode = "input",
  onDelete,
  onUpdate,
  repsOptions,
  repsUnit = "reps",
  setEntry,
  variant = "default",
  weightOptions,
  measurementType = "weighted_reps",
  updateOnChange = false,
}: SetRowProps) {
  const [weight, setWeight] = useState(String(setEntry.weight));
  const [reps, setReps] = useState(String(setEntry.reps));
  const isLegacyEdit = variant === "legacy-edit";
  const usesWeight = measurementUsesWeight(measurementType);
  const currentQuantityLabel = quantityLabel(measurementType);

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

  function updateSet(nextWeight: string, nextReps: string) {
    const nextParsedWeight = Number(nextWeight);
    const nextParsedReps = Number(nextReps);
    if (
      onUpdate &&
      Number.isFinite(nextParsedWeight) &&
      Number.isInteger(nextParsedReps) &&
      nextParsedWeight >= 0 &&
      nextParsedReps >= 1
    ) {
      onUpdate(setEntry.id, {
        weight: nextParsedWeight,
        reps: nextParsedReps,
      });
    }
  }

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
      {usesWeight && (
        <label>
          Kg
          {editorMode === "select" ? (
            <select
              aria-label={isLegacyEdit ? `Set ${setEntry.set_number} weight` : undefined}
              className="scroll-select"
              disabled={disabled || !onUpdate}
              onChange={(event) => {
                const value = event.target.value;
                setWeight(value);
                if (updateOnChange) {
                  updateSet(value, reps);
                }
              }}
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
      )}
      <label>
        {currentQuantityLabel}
        {editorMode === "select" ? (
          <select
            aria-label={isLegacyEdit ? `Set ${setEntry.set_number} ${currentQuantityLabel.toLowerCase()}` : undefined}
            className="scroll-select"
            disabled={disabled || !onUpdate}
            onChange={(event) => {
              const value = event.target.value;
              setReps(value);
              if (updateOnChange) {
                updateSet(weight, value);
              }
            }}
            value={reps}
          >
            {selectRepsOptions.map((option) => (
              <option key={option} value={formatSetOption(option)}>
                {formatSetOption(option)} {repsUnit}
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
      {onUpdate && !updateOnChange && (
        <button
          className="secondary-button compact-button"
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
            ? "icon-delete-button edit-set-delete-button"
            : "ghost-button compact-button danger-text"
        }
        aria-label={`Remove set ${setEntry.set_number}`}
        disabled={disabled}
        onClick={deleteSet}
        title={`Remove set ${setEntry.set_number}`}
        type="button"
      >
        {isLegacyEdit ? "×" : "Delete"}
      </button>
    </div>
  );
}
