import type { ExerciseMeasurementType } from "../api/types";
import { formatDurationSeconds } from "./durationFormat";

export type MeasurementUi = {
  usesWeight: boolean;
  weightLabel: string;
  quantityLabel: string;
  quantityUnit: string;
  addButtonLabel: string;
  setSummaryLabel: string;
  totalSummary: (input: {
    totalSets: number;
    totalReps: number;
    totalVolumeKg: number;
    bodyweightReps: number;
    durationSeconds: number;
    distanceM: number;
  }) => string;
};

export function measurementUi(
  measurementType: ExerciseMeasurementType,
  repsUnit: string,
): MeasurementUi {
  switch (measurementType) {
    case "bodyweight_reps":
    case "reps_only":
      return {
        usesWeight: false,
        weightLabel: "",
        quantityLabel: "Reps",
        quantityUnit: repsUnit || "reps",
        addButtonLabel: "Add reps",
        setSummaryLabel: "reps",
        totalSummary: ({ totalSets, bodyweightReps }) =>
          `${totalSets} sets · ${bodyweightReps} reps`,
      };

    case "duration_only":
      return {
        usesWeight: false,
        weightLabel: "",
        quantityLabel: "Duration",
        quantityUnit: repsUnit || "sec",
        addButtonLabel: "Add time",
        setSummaryLabel: "sec",
        totalSummary: ({ totalSets, durationSeconds }) =>
          `${totalSets} sets · ${formatDurationSeconds(durationSeconds, {
            totalSuffix: true,
          })}`,
      };

    case "loaded_carry_time":
      return {
        usesWeight: true,
        weightLabel: "Kg",
        quantityLabel: "Duration",
        quantityUnit: repsUnit || "sec",
        addButtonLabel: "Add carry",
        setSummaryLabel: "sec",
        totalSummary: ({ totalSets, durationSeconds }) =>
          `${totalSets} sets · ${formatDurationSeconds(durationSeconds, {
            totalSuffix: true,
          })}`,
      };

    case "loaded_carry_distance":
      return {
        usesWeight: true,
        weightLabel: "Kg",
        quantityLabel: "Meters",
        quantityUnit: repsUnit || "m",
        addButtonLabel: "Add distance",
        setSummaryLabel: "m",
        totalSummary: ({ totalSets, distanceM }) =>
          `${totalSets} sets · ${distanceM} m`,
      };

    case "weighted_reps":
    default:
      return {
        usesWeight: true,
        weightLabel: "Kg",
        quantityLabel: "Reps",
        quantityUnit: repsUnit || "reps",
        addButtonLabel: "Add set",
        setSummaryLabel: "reps",
        totalSummary: ({ totalSets, totalReps, totalVolumeKg }) =>
          `${totalSets} sets · ${totalReps} reps · ${totalVolumeKg.toFixed(0)} kg`,
      };
  }
}
