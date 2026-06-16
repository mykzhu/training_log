import { useEffect, useState } from "react";

import type { SetEntry } from "../api/types";

type SetRowProps = {
  disabled: boolean;
  setEntry: SetEntry;
  onDelete: (setId: number) => void;
  onUpdate?: (setId: number, payload: { weight?: number; reps?: number }) => void;
};

export default function SetRow({
  disabled,
  onDelete,
  onUpdate,
  setEntry,
}: SetRowProps) {
  const [weight, setWeight] = useState(String(setEntry.weight));
  const [reps, setReps] = useState(String(setEntry.reps));

  useEffect(() => {
    setWeight(String(setEntry.weight));
    setReps(String(setEntry.reps));
  }, [setEntry.weight, setEntry.reps]);

  const parsedWeight = Number(weight);
  const parsedReps = Number(reps);
  const canSave =
    onUpdate !== undefined &&
    Number.isFinite(parsedWeight) &&
    Number.isInteger(parsedReps) &&
    parsedWeight >= 0 &&
    parsedReps >= 1 &&
    (parsedWeight !== setEntry.weight || parsedReps !== setEntry.reps);

  return (
    <div className="set-row">
      <span>#{setEntry.set_number}</span>
      <label>
        Kg
        <input
          disabled={disabled || !onUpdate}
          inputMode="decimal"
          min="0"
          onChange={(event) => setWeight(event.target.value)}
          step="0.25"
          type="number"
          value={weight}
        />
      </label>
      <label>
        Reps
        <input
          disabled={disabled || !onUpdate}
          inputMode="numeric"
          min="1"
          onChange={(event) => setReps(event.target.value)}
          step="1"
          type="number"
          value={reps}
        />
      </label>
      {onUpdate && (
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
        className="ghost-button compact-button danger-text"
        disabled={disabled}
        onClick={() => onDelete(setEntry.id)}
        type="button"
      >
        Delete
      </button>
    </div>
  );
}
