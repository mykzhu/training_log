import { useEffect, useState } from "react";

import type { ExerciseMeasurementType, SetEntry } from "../api/types";
import {
  buildRepsOptions,
  buildWeightOptions,
  formatSetOption,
} from "../utils/setOptions";
import { measurementUi } from "../utils/measurementUi";

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
  const ui = measurementUi(measurementType, repsUnit);

  useEffect(() => {
    setWeight(String(setEntry.weight));
    setReps(String(setEntry.reps));
  }, [setEntry.weight, setEntry.reps]);

  const parsedWeight = Number(weight);
  const parsedReps = Number(reps);
  const valuesAreValid =
    (ui.usesWeight ? Number.isFinite(parsedWeight) : true) &&
    Number.isInteger(parsedReps) &&
    (ui.usesWeight ? parsedWeight >= 0 : true) &&
    parsedReps >= 1;
  const valuesChanged =
    (ui.usesWeight ? parsedWeight !== setEntry.weight : setEntry.weight !== 0) ||
    parsedReps !== setEntry.reps;
  const canSave =
    onUpdate !== undefined &&
    valuesAreValid &&
    (isLegacyEdit || valuesChanged);
  const selectWeightOptions = weightOptions ?? buildWeightOptions(setEntry.weight);
  const selectRepsOptions = repsOptions ?? buildRepsOptions(setEntry.reps);

  function updateSet(nextWeight: string, nextReps: string) {
    const nextParsedWeight = ui.usesWeight ? Number(nextWeight) : 0;
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
      {ui.usesWeight && (
        <label>
          {ui.weightLabel}
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
        {ui.quantityLabel}
        {editorMode === "select" ? (
          <select
            aria-label={isLegacyEdit ? `Set ${setEntry.set_number} ${ui.quantityLabel.toLowerCase()}` : undefined}
            className="scroll-select"
            disabled={disabled || !onUpdate}
            onChange={(event) => {
              const value = event.target.value;
              setReps(value);
              if (updateOnChange) {
                updateSet(ui.usesWeight ? weight : "0", value);
              }
            }}
            value={reps}
          >
            {selectRepsOptions.map((option) => (
              <option key={option} value={formatSetOption(option)}>
                {formatSetOption(option)} {ui.quantityUnit}
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
              weight: ui.usesWeight ? parsedWeight : 0,
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
