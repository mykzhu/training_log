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

export function buildRepsOptions(currentReps: number, extraReps: number[] = []) {
  return uniqueSortedNumbers(
    [
      currentReps,
      ...extraReps,
      ...Array.from({ length: 50 }, (_, index) => index + 1),
    ].filter((value) => Number.isFinite(value) && value > 0),
  );
}
