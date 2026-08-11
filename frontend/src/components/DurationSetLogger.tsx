import { useEffect, useMemo, useState } from "react";

import {
  clampDurationSeconds,
  formatDurationSeconds,
  parseDurationInput,
} from "../utils/durationFormat";

type DurationSetLoggerProps = {
  disabled: boolean;
  defaultSeconds: number;
  minSeconds?: number;
  maxSeconds?: number;
  stepSeconds?: number;
  onAddDuration: (seconds: number) => Promise<void> | void;
};

function quickDurationOptions(
  defaultSeconds: number,
  minSeconds?: number,
  maxSeconds?: number,
) {
  const candidates = [defaultSeconds, 30, 60, 75]
    .filter((value) => Number.isFinite(value) && value >= 1)
    .map((value) =>
      clampDurationSeconds(value, { min: minSeconds ?? 1, max: maxSeconds }),
    );

  return Array.from(new Set(candidates))
    .sort((first, second) => first - second)
    .slice(0, 4);
}

function formatTimerDisplay(seconds: number) {
  const rounded = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(rounded / 60);
  const remainingSeconds = rounded % 60;
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

export default function DurationSetLogger({
  defaultSeconds,
  disabled,
  maxSeconds,
  minSeconds = 1,
  onAddDuration,
}: DurationSetLoggerProps) {
  const [manualValue, setManualValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [timerStartedAt, setTimerStartedAt] = useState<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const isRunning = timerStartedAt !== null;
  const elapsedSeconds = Math.max(0, Math.round(elapsedMs / 1000));
  const quickOptions = useMemo(
    () => quickDurationOptions(defaultSeconds, minSeconds, maxSeconds),
    [defaultSeconds, maxSeconds, minSeconds],
  );

  useEffect(() => {
    if (timerStartedAt === null) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setElapsedMs(performance.now() - timerStartedAt);
    }, 250);

    return () => window.clearInterval(intervalId);
  }, [timerStartedAt]);

  function addDuration(seconds: number) {
    const clamped = clampDurationSeconds(seconds, {
      min: minSeconds,
      max: maxSeconds,
    });
    setError(null);
    void onAddDuration(clamped);
  }

  function addManualDuration() {
    const parsed = parseDurationInput(manualValue);
    if (parsed === null) {
      setError("Enter a duration like 30 sec or 1:15.");
      return;
    }

    addDuration(parsed);
    setManualValue("");
  }

  function startTimer() {
    setError(null);
    setElapsedMs(0);
    setTimerStartedAt(performance.now());
  }

  function resetTimer() {
    setTimerStartedAt(null);
    setElapsedMs(0);
    setError(null);
  }

  function stopAndAddTimer() {
    const currentElapsedMs =
      timerStartedAt === null ? elapsedMs : performance.now() - timerStartedAt;
    const seconds = Math.round(currentElapsedMs / 1000);
    if (seconds < 1) {
      setError("Timer duration must be at least 1 second.");
      return;
    }

    addDuration(seconds);
    setTimerStartedAt(null);
    setElapsedMs(0);
  }

  return (
    <section className="duration-set-logger" aria-label="Duration logger">
      <div className="duration-manual-row">
        <label>
          Duration
          <input
            aria-invalid={error ? "true" : "false"}
            disabled={disabled}
            inputMode="numeric"
            onChange={(event) => {
              setManualValue(event.target.value);
              setError(null);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                addManualDuration();
              }
            }}
            placeholder="0:30 or 75"
            value={manualValue}
          />
        </label>
        <button
          className="secondary-button"
          disabled={disabled}
          onClick={addManualDuration}
          type="button"
        >
          Add
        </button>
      </div>

      <div className="duration-quick-buttons" aria-label="Quick durations">
        {quickOptions.map((seconds) => (
          <button
            className="ghost-button compact-button"
            disabled={disabled}
            key={seconds}
            onClick={() => addDuration(seconds)}
            type="button"
          >
            {formatDurationSeconds(seconds)}
          </button>
        ))}
      </div>

      <div className="duration-timer-row">
        <div
          aria-live="polite"
          className="duration-timer-display"
        >
          {formatTimerDisplay(elapsedSeconds)}
        </div>
        <button
          className="primary-button"
          disabled={disabled || isRunning}
          onClick={startTimer}
          type="button"
        >
          Start
        </button>
        <button
          className="secondary-button"
          disabled={disabled || !isRunning}
          onClick={stopAndAddTimer}
          type="button"
        >
          Stop & Add
        </button>
        <button
          className="ghost-button"
          disabled={disabled || (!isRunning && elapsedMs === 0)}
          onClick={resetTimer}
          type="button"
        >
          Reset
        </button>
      </div>

      {isRunning && (
        <p className="duration-timer-note">
          Timer is running. Stop & Add before leaving this page.
        </p>
      )}
      {error && <p className="duration-input-error">{error}</p>}
    </section>
  );
}
