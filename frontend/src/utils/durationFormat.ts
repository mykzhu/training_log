export function formatDurationSeconds(
  seconds: number | null | undefined,
  options: {
    zeroLabel?: string;
    totalSuffix?: boolean;
  } = {},
): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
    return "—";
  }

  const rounded = Math.max(0, Math.round(seconds));
  let formatted: string;

  if (rounded === 0) {
    formatted = options.zeroLabel ?? "0 sec";
  } else if (rounded < 60) {
    formatted = `${rounded} sec`;
  } else {
    const minutes = Math.floor(rounded / 60);
    const remainingSeconds = rounded % 60;
    formatted = `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
  }

  return options.totalSuffix ? `${formatted} total` : formatted;
}

export function parseDurationInput(value: string): number | null {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return null;
  }

  const colonMatch = normalized.match(/^(\d+):(\d{2})$/);
  if (colonMatch) {
    const minutes = Number(colonMatch[1]);
    const seconds = Number(colonMatch[2]);
    if (seconds > 59) {
      return null;
    }
    const totalSeconds = minutes * 60 + seconds;
    return totalSeconds >= 1 ? totalSeconds : null;
  }

  const compactMinuteSecondMatch = normalized.match(/^(\d+)\s*m(?:in)?\s*(\d+)\s*s(?:ec)?(?:onds?)?$/);
  if (compactMinuteSecondMatch) {
    const seconds = Number(compactMinuteSecondMatch[2]);
    if (seconds > 59) {
      return null;
    }
    const totalSeconds =
      Number(compactMinuteSecondMatch[1]) * 60 +
      seconds;
    return totalSeconds >= 1 ? totalSeconds : null;
  }

  const wordMinuteSecondMatch = normalized.match(
    /^(\d+)\s*min(?:ute)?s?\s+(\d+)\s*sec(?:ond)?s?$/,
  );
  if (wordMinuteSecondMatch) {
    const seconds = Number(wordMinuteSecondMatch[2]);
    if (seconds > 59) {
      return null;
    }
    const totalSeconds =
      Number(wordMinuteSecondMatch[1]) * 60 +
      seconds;
    return totalSeconds >= 1 ? totalSeconds : null;
  }

  const secondsMatch = normalized.match(/^(\d+)\s*(?:s|sec|secs|second|seconds)?$/);
  if (secondsMatch) {
    const seconds = Number(secondsMatch[1]);
    return seconds >= 1 ? seconds : null;
  }

  return null;
}

export function clampDurationSeconds(
  seconds: number,
  options: {
    min?: number;
    max?: number;
  } = {},
): number {
  const min = options.min ?? 1;
  const max = options.max ?? Number.POSITIVE_INFINITY;
  if (!Number.isFinite(seconds)) {
    return min;
  }

  return Math.min(max, Math.max(min, Math.round(seconds)));
}
