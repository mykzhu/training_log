import { useEffect, useState } from "react";

import type { ExerciseFeedback, ExerciseFeedbackUpdate } from "../api/types";

type SaveStatus = "idle" | "saving" | "saved" | "error";

type ExerciseFeedbackEditorProps = {
  disabled: boolean;
  feedback: ExerciseFeedback | null;
  profileKey: string;
  saveStatus?: SaveStatus;
  onChange: (payload: ExerciseFeedbackUpdate) => void;
};

const expandedProfileKeys = new Set([
  "back_rehab",
  "core_stability",
  "mobility",
]);

const scoreOptions = Array.from({ length: 11 }, (_, index) => index);

function scoreToInput(value: number | null | undefined) {
  return value === null || value === undefined ? "" : String(value);
}

function inputToScore(value: string) {
  return value === "" ? null : Number(value);
}

function deriveResponse(
  before: string,
  after: string,
): ExerciseFeedback["response"] {
  const beforeScore = inputToScore(before);
  const afterScore = inputToScore(after);

  if (beforeScore === null || afterScore === null) {
    return "unknown";
  }
  if (afterScore < beforeScore) {
    return "helped";
  }
  if (afterScore > beforeScore) {
    return "worse";
  }
  return "same";
}

function defaultResponse(value: ExerciseFeedback | null) {
  return value?.response ?? "unknown";
}

function statusLabel(status: SaveStatus) {
  if (status === "saving") {
    return "Saving";
  }
  if (status === "saved") {
    return "Saved";
  }
  if (status === "error") {
    return "Error";
  }
  return "";
}

export default function ExerciseFeedbackEditor({
  disabled,
  feedback,
  onChange,
  profileKey,
  saveStatus = "idle",
}: ExerciseFeedbackEditorProps) {
  const shouldExpandByDefault = expandedProfileKeys.has(profileKey);
  const [expanded, setExpanded] = useState(
    shouldExpandByDefault || feedback !== null,
  );
  const [before, setBefore] = useState(scoreToInput(feedback?.back_pain_before));
  const [after, setAfter] = useState(scoreToInput(feedback?.back_pain_after));
  const [response, setResponse] = useState<ExerciseFeedback["response"]>(
    defaultResponse(feedback),
  );
  const [notes, setNotes] = useState(feedback?.notes ?? "");

  useEffect(() => {
    setBefore(scoreToInput(feedback?.back_pain_before));
    setAfter(scoreToInput(feedback?.back_pain_after));
    setResponse(defaultResponse(feedback));
    setNotes(feedback?.notes ?? "");
  }, [feedback]);

  function emit(next: {
    before?: string;
    after?: string;
    response?: ExerciseFeedback["response"];
    notes?: string;
  }) {
    const nextBefore = next.before ?? before;
    const nextAfter = next.after ?? after;
    const nextResponse =
      next.response ??
      (next.before !== undefined || next.after !== undefined
        ? deriveResponse(nextBefore, nextAfter)
        : response);
    const nextNotes = next.notes ?? notes;

    setResponse(nextResponse);
    onChange({
      back_pain_before: inputToScore(nextBefore),
      back_pain_after: inputToScore(nextAfter),
      response: nextResponse,
      notes: nextNotes.trim() ? nextNotes : null,
    });
  }

  return (
    <section className={`exercise-feedback ${expanded ? "is-expanded" : ""}`.trim()}>
      <div className="exercise-feedback-header">
        <button
          aria-expanded={expanded}
          className="exercise-feedback-toggle"
          disabled={disabled}
          onClick={() => setExpanded((current) => !current)}
          type="button"
        >
          Back response
        </button>
        <span className={`exercise-feedback-status ${saveStatus}`.trim()}>
          {statusLabel(saveStatus)}
        </span>
      </div>

      {expanded && (
        <div className="exercise-feedback-body">
          <label>
            Before
            <select
              disabled={disabled}
              onChange={(event) => {
                const value = event.target.value;
                setBefore(value);
                emit({ before: value });
              }}
              value={before}
            >
              <option value="">-</option>
              {scoreOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label>
            After
            <select
              disabled={disabled}
              onChange={(event) => {
                const value = event.target.value;
                setAfter(value);
                emit({ after: value });
              }}
              value={after}
            >
              <option value="">-</option>
              {scoreOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label>
            Response
            <select
              disabled={disabled}
              onChange={(event) => {
                const value = event.target.value as ExerciseFeedback["response"];
                setResponse(value);
                emit({ response: value });
              }}
              value={response}
            >
              <option value="helped">Helped</option>
              <option value="same">Same</option>
              <option value="worse">Worse</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label className="exercise-feedback-notes">
            Notes
            <textarea
              disabled={disabled}
              maxLength={1000}
              onBlur={() => emit({ notes })}
              onChange={(event) => setNotes(event.target.value)}
              value={notes}
            />
          </label>
        </div>
      )}
    </section>
  );
}
