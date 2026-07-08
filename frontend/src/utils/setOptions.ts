export function formatSetOption(value: number) {
  return Number.isInteger(value) ? String(value) : String(value);
}

export function uniqueSortedNumbers(values: number[]) {
  return Array.from(new Set(values)).sort((a, b) => a - b);
}

export function buildWeightOptions(currentWeight: number, extraWeights: number[] = []) {
  const values: number[] = [currentWeight, ...extraWeights];

  return uniqueSortedNumbers(values.filter((value) => Number.isFinite(value)));
}

export function buildSteppedRepsOptions(
  minReps: number,
  maxReps: number,
  repsStep: number,
  extraReps: number[] = [],
) {
  const start = Math.max(1, Math.trunc(minReps));
  const end = Math.max(start, Math.trunc(maxReps));
  const step = Math.max(1, Math.trunc(repsStep));
  const values: number[] = [start];
  let firstStepValue = step;

  if (firstStepValue < start) {
    firstStepValue = Math.ceil(start / step) * step;
  }

  for (let value = firstStepValue; value <= end; value += step) {
    values.push(value);
  }
  values.push(end, ...extraReps);

  return uniqueSortedNumbers(
    values.filter((value) => Number.isFinite(value) && value > 0),
  );
}

export function buildRepsOptions(
  currentReps: number,
  extraReps: number[] = [],
  includeFallbackRange = true,
) {
  return uniqueSortedNumbers(
    [
      currentReps,
      ...extraReps,
      ...(includeFallbackRange
        ? Array.from({ length: 50 }, (_, index) => index + 1)
        : []),
    ].filter((value) => Number.isFinite(value) && value > 0),
  );
}
