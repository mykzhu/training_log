import type { SetEntry } from "../api/types";

type SetRowProps = {
  disabled: boolean;
  setEntry: SetEntry;
  onDelete: (setId: number) => void;
};

export default function SetRow({ disabled, onDelete, setEntry }: SetRowProps) {
  return (
    <div className="set-row">
      <span>#{setEntry.set_number}</span>
      <strong>{setEntry.weight} kg</strong>
      <strong>{setEntry.reps} reps</strong>
      <button
        className="ghost-button danger-text"
        disabled={disabled}
        onClick={() => onDelete(setEntry.id)}
        type="button"
      >
        Delete
      </button>
    </div>
  );
}
