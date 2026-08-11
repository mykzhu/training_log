import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  createExercise,
  deleteExercise,
  getExerciseProfiles,
  getExercises,
  reorderExercises,
  replaceExerciseWeights,
  updateExercise,
} from "../api/exercises";
import {
  disconnectGarmin,
  getGarminAutoSyncSettings,
  getGarminStatus,
  loginGarmin,
  submitGarminMfa,
  syncGarmin,
  updateGarminAutoSyncSettings,
} from "../api/garmin";
import AnalysisProfilesPanel from "../components/settings/AnalysisProfilesPanel";
import type {
  Exercise,
  ExerciseMeasurementType,
  ExerciseProfile,
  GarminAutoSyncSettings,
  GarminStatus,
} from "../api/types";
import { formatSetOption, uniqueSortedNumbers } from "../utils/setOptions";

type ExerciseOptionSettingsDraft = {
  measurement_type: ExerciseMeasurementType;
  reps_unit: string;
  default_weight: number;
  min_weight: number;
  max_weight: number;
  weight_step: number;
  default_reps: number;
  min_reps: number;
  max_reps: number;
  reps_step: number;
};

type NewExerciseDraft = {
  name: string;
  profile_key: string;
  measurement_type: ExerciseMeasurementType;
  reps_unit: string;
  weights: string;
  default_weight: number;
  min_weight: number;
  max_weight: number;
  weight_step: number;
  default_reps: number;
  min_reps: number;
  max_reps: number;
  reps_step: number;
};

type RehabPreset = {
  label: string;
  name: string;
  profile_key: string;
  measurement_type: ExerciseMeasurementType;
  reps_unit: string;
  default_reps: number;
  min_reps: number;
  max_reps: number;
  reps_step: number;
};

const measurementTypeOptions: Array<{
  value: ExerciseMeasurementType;
  label: string;
  description: string;
}> = [
  { value: "weighted_reps", label: "Weighted reps", description: "Weight + reps" },
  { value: "bodyweight_reps", label: "Bodyweight reps", description: "Reps only" },
  { value: "reps_only", label: "Reps only", description: "Reps only" },
  { value: "duration_only", label: "Duration only", description: "Seconds only" },
  { value: "loaded_carry_time", label: "Loaded carry time", description: "Weight + seconds" },
  { value: "loaded_carry_distance", label: "Loaded carry dist.", description: "Weight + meters" },
];

const defaultUnitByMeasurement: Record<ExerciseMeasurementType, string> = {
  weighted_reps: "reps",
  bodyweight_reps: "reps",
  loaded_carry_time: "sec",
  loaded_carry_distance: "m",
  reps_only: "reps",
  duration_only: "sec",
};

const defaultNewExerciseDraft: NewExerciseDraft = {
  name: "",
  profile_key: "",
  measurement_type: "weighted_reps",
  reps_unit: "reps",
  weights: "",
  default_weight: 0,
  min_weight: 0,
  max_weight: 200,
  weight_step: 2.5,
  default_reps: 10,
  min_reps: 1,
  max_reps: 50,
  reps_step: 1,
};

const rehabPresets: RehabPreset[] = [
  {
    label: "Dead Bug",
    name: "Dead Bug",
    profile_key: "core_stability",
    measurement_type: "reps_only",
    reps_unit: "reps",
    default_reps: 10,
    min_reps: 1,
    max_reps: 30,
    reps_step: 1,
  },
  {
    label: "Cat-Cow",
    name: "Cat-Cow",
    profile_key: "mobility",
    measurement_type: "reps_only",
    reps_unit: "reps",
    default_reps: 10,
    min_reps: 1,
    max_reps: 30,
    reps_step: 1,
  },
  {
    label: "Bird Dog",
    name: "Bird Dog",
    profile_key: "core_stability",
    measurement_type: "reps_only",
    reps_unit: "reps",
    default_reps: 8,
    min_reps: 1,
    max_reps: 30,
    reps_step: 1,
  },
  {
    label: "McGill Curl-up",
    name: "McGill Curl-up",
    profile_key: "back_rehab",
    measurement_type: "reps_only",
    reps_unit: "reps",
    default_reps: 6,
    min_reps: 1,
    max_reps: 20,
    reps_step: 1,
  },
  {
    label: "Side Plank",
    name: "Side Plank",
    profile_key: "core_stability",
    measurement_type: "duration_only",
    reps_unit: "sec",
    default_reps: 20,
    min_reps: 5,
    max_reps: 120,
    reps_step: 5,
  },
  {
    label: "Pelvic Tilt",
    name: "Pelvic Tilt",
    profile_key: "mobility",
    measurement_type: "reps_only",
    reps_unit: "reps",
    default_reps: 10,
    min_reps: 1,
    max_reps: 30,
    reps_step: 1,
  },
  {
    label: "Glute Bridge",
    name: "Glute Bridge",
    profile_key: "core_stability",
    measurement_type: "reps_only",
    reps_unit: "reps",
    default_reps: 10,
    min_reps: 1,
    max_reps: 40,
    reps_step: 1,
  },
];

function measurementRequiresWeight(measurementType: ExerciseMeasurementType) {
  return (
    measurementType === "weighted_reps" ||
    measurementType === "loaded_carry_time" ||
    measurementType === "loaded_carry_distance"
  );
}

function quantityLabels(measurementType: ExerciseMeasurementType) {
  if (measurementType === "duration_only" || measurementType === "loaded_carry_time") {
    return {
      defaultLabel: "Default seconds",
      minLabel: "Min seconds",
      maxLabel: "Max seconds",
      stepLabel: "Seconds step",
    };
  }

  if (measurementType === "loaded_carry_distance") {
    return {
      defaultLabel: "Default meters",
      minLabel: "Min meters",
      maxLabel: "Max meters",
      stepLabel: "Meter step",
    };
  }

  return {
    defaultLabel: "Default reps",
    minLabel: "Min reps",
    maxLabel: "Max reps",
    stepLabel: "Reps step",
  };
}

function parseWeightList(value: string) {
  return normalizeWeights(
    value
      .split(/[,\s]+/)
      .map((item) => Number(item))
      .filter((item) => Number.isFinite(item) && item >= 0),
  );
}

function normalizeWeights(weights: number[]) {
  return uniqueSortedNumbers(
    weights
      .filter((value) => Number.isFinite(value) && value >= 0)
      .map((value) => Math.round(value * 10000) / 10000),
  );
}

function weightsKey(weights: number[]) {
  return JSON.stringify(normalizeWeights(weights));
}

function optionSettingsDraft(exercise: Exercise): ExerciseOptionSettingsDraft {
  return {
    measurement_type: exercise.measurement_type,
    reps_unit: exercise.reps_unit,
    default_weight: exercise.default_weight,
    min_weight: exercise.min_weight,
    max_weight: exercise.max_weight,
    weight_step: exercise.weight_step,
    default_reps: exercise.default_reps,
    min_reps: exercise.min_reps,
    max_reps: exercise.max_reps,
    reps_step: exercise.reps_step,
  };
}

function optionSettingsKey(settings: ExerciseOptionSettingsDraft) {
  return JSON.stringify(settings);
}

function replaceExerciseInList(exercises: Exercise[], updated: Exercise) {
  return exercises.map((exercise) =>
    exercise.id === updated.id ? updated : exercise,
  );
}

function formatExerciseUsage(exercise: Exercise) {
  const usage = exercise.usage;
  if (!usage) {
    return "Usage unavailable";
  }

  const parts = [
    `Used by ${usage.workout_count} workout${usage.workout_count === 1 ? "" : "s"}`,
    `${usage.set_count} set${usage.set_count === 1 ? "" : "s"}`,
  ];
  if (usage.draft_count > 0) {
    parts.push("active draft");
  }
  return parts.join(" | ");
}

function parseWeight(value: string) {
  const weight = Number(value);
  return Number.isFinite(weight) && weight >= 0 ? weight : null;
}

function formatGarminDate(value: string | null | undefined) {
  if (!value) {
    return "-";
  }

  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatGarminDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatGarminAutoSyncResult(result: Record<string, unknown> | null) {
  if (!result) {
    return "-";
  }

  const saved = typeof result.saved === "number" ? result.saved : 0;
  const skipped = typeof result.skipped === "number" ? result.skipped : 0;
  const warnings = typeof result.warnings === "number" ? result.warnings : 0;
  return `Saved ${saved}, skipped ${skipped}, warnings ${warnings}`;
}

function shortText(value: string | null | undefined, maxLength = 80) {
  if (!value) {
    return "-";
  }
  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}...` : value;
}

export default function SettingsPage() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [profiles, setProfiles] = useState<ExerciseProfile[]>([]);
  const [nameDrafts, setNameDrafts] = useState<Record<number, string>>({});
  const [profileDrafts, setProfileDrafts] = useState<Record<number, string>>({});
  const [weightDrafts, setWeightDrafts] = useState<Record<number, number[]>>({});
  const [optionSettingsDrafts, setOptionSettingsDrafts] = useState<
    Record<number, ExerciseOptionSettingsDraft>
  >({});
  const [expandedExerciseIds, setExpandedExerciseIds] = useState<Set<number>>(
    () => new Set(),
  );
  const [confirmDeleteExerciseId, setConfirmDeleteExerciseId] = useState<number | null>(
    null,
  );
  const [newWeightDrafts, setNewWeightDrafts] = useState<Record<number, string>>({});
  const [newExerciseDraft, setNewExerciseDraft] = useState<NewExerciseDraft>(
    defaultNewExerciseDraft,
  );
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [garminStatus, setGarminStatus] = useState<GarminStatus | null>(null);
  const [garminUsername, setGarminUsername] = useState("");
  const [garminPassword, setGarminPassword] = useState("");
  const [garminMfaCode, setGarminMfaCode] = useState("");
  const [garminMfaToken, setGarminMfaToken] = useState<string | null>(null);
  const [garminError, setGarminError] = useState<string | null>(null);
  const [garminMessage, setGarminMessage] = useState<string | null>(null);
  const [garminPendingAction, setGarminPendingAction] = useState<string | null>(null);
  const [garminAutoSync, setGarminAutoSync] =
    useState<GarminAutoSyncSettings | null>(null);
  const [garminAutoSyncDraft, setGarminAutoSyncDraft] = useState({
    enabled: false,
    sync_after_local_time: "07:00",
    sync_days: 35,
  });
  const profileLabels = useMemo(
    () =>
      Object.fromEntries(
        profiles.map((profile) => [profile.key, profile.label]),
      ),
    [profiles],
  );
  const activeProfiles = useMemo(
    () => profiles.filter((profile) => profile.is_active),
    [profiles],
  );

  function profileOptionsForExercise(currentKey?: string) {
    const options = new Map(activeProfiles.map((profile) => [profile.key, profile]));
    const currentProfile = profiles.find((profile) => profile.key === currentKey);
    if (currentProfile && !options.has(currentProfile.key)) {
      options.set(currentProfile.key, currentProfile);
    }
    return Array.from(options.values()).sort((left, right) => {
      if (left.is_active !== right.is_active) {
        return left.is_active ? -1 : 1;
      }
      if (left.sort_order !== right.sort_order) {
        return left.sort_order - right.sort_order;
      }
      return left.label.localeCompare(right.label);
    });
  }

  function hydrate(responseExercises: Exercise[]) {
    setExercises(responseExercises);
    setNameDrafts(
      Object.fromEntries(
        responseExercises.map((exercise) => [exercise.id, exercise.name]),
      ),
    );
    setProfileDrafts(
      Object.fromEntries(
        responseExercises.map((exercise) => [exercise.id, exercise.profile_key]),
      ),
    );
    setWeightDrafts(
      Object.fromEntries(
        responseExercises.map((exercise) => [exercise.id, exercise.weights]),
      ),
    );
    setOptionSettingsDrafts(
      Object.fromEntries(
        responseExercises.map((exercise) => [
          exercise.id,
          optionSettingsDraft(exercise),
        ]),
      ),
    );
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [exerciseResponse, profileResponse] = await Promise.all([
        getExercises({ includeInactive: true }),
        getExerciseProfiles(),
      ]);
      hydrate(exerciseResponse.exercises);
      setProfiles(profileResponse.profiles);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Failed to load.");
    } finally {
      setLoading(false);
    }
  }

  async function loadGarminStatus() {
    setGarminError(null);
    const response = await getGarminStatus();
    setGarminStatus(response);
    return response;
  }

  async function loadGarminAutoSyncSettings() {
    setGarminError(null);
    const response = await getGarminAutoSyncSettings();
    setGarminAutoSync(response);
    setGarminAutoSyncDraft({
      enabled: response.enabled,
      sync_after_local_time: response.sync_after_local_time,
      sync_days: response.sync_days,
    });
    return response;
  }

  useEffect(() => {
    load();
    Promise.all([loadGarminStatus(), loadGarminAutoSyncSettings()]).catch((reason: unknown) => {
      setGarminError(
        reason instanceof Error ? reason.message : "Failed to load Garmin status.",
      );
    });
  }, []);

  function isNameDirty(exercise: Exercise) {
    return (nameDrafts[exercise.id] ?? "") !== exercise.name;
  }

  function isProfileDirty(exercise: Exercise) {
    return (profileDrafts[exercise.id] ?? "") !== exercise.profile_key;
  }

  function isWeightDirty(exercise: Exercise) {
    return (
      weightsKey(weightDrafts[exercise.id] ?? []) !== weightsKey(exercise.weights)
    );
  }

  function isOptionSettingsDirty(exercise: Exercise) {
    return (
      optionSettingsKey(
        optionSettingsDrafts[exercise.id] ?? optionSettingsDraft(exercise),
      ) !== optionSettingsKey(optionSettingsDraft(exercise))
    );
  }

  function isExerciseDirty(exercise: Exercise) {
    return (
      isNameDirty(exercise) ||
      isProfileDirty(exercise) ||
      isWeightDirty(exercise) ||
      isOptionSettingsDirty(exercise)
    );
  }

  const hasDirtyDrafts = exercises.some(isExerciseDirty);
  const isBusy = pendingAction !== null;
  const garminBusy = garminPendingAction !== null;
  const garminAutoSyncDirty =
    garminAutoSync !== null &&
    (garminAutoSyncDraft.enabled !== garminAutoSync.enabled ||
      garminAutoSyncDraft.sync_after_local_time !==
        garminAutoSync.sync_after_local_time ||
      garminAutoSyncDraft.sync_days !== garminAutoSync.sync_days);

  const newExerciseUsesWeight = measurementRequiresWeight(
    newExerciseDraft.measurement_type,
  );
  const newExerciseQuantityLabels = quantityLabels(
    newExerciseDraft.measurement_type,
  );
  const newExerciseWeights = newExerciseUsesWeight
    ? parseWeightList(newExerciseDraft.weights)
    : [];
  const selectedMeasurementOption =
    measurementTypeOptions.find(
      (option) => option.value === newExerciseDraft.measurement_type,
    ) ?? measurementTypeOptions[0];

  async function runAction(
    actionKey: string,
    action: () => Promise<void>,
    successMessage: string,
  ) {
    setPendingAction(actionKey);
    setError(null);
    setMessage(null);
    try {
      await action();
      setMessage(successMessage);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPendingAction(null);
    }
  }

  async function addExercise(event?: FormEvent) {
    event?.preventDefault();
    const name = newExerciseDraft.name.trim();
    if (!name || (newExerciseUsesWeight && newExerciseWeights.length === 0)) {
      return;
    }

    await runAction(
      "create",
      async () => {
        const response = await createExercise({
          name,
          is_active: true,
          profile_key: newExerciseDraft.profile_key || undefined,
          measurement_type: newExerciseDraft.measurement_type,
          reps_unit: newExerciseDraft.reps_unit,
          weights: newExerciseWeights,
          default_weight: newExerciseUsesWeight
            ? newExerciseDraft.default_weight
            : 0,
          min_weight: newExerciseUsesWeight ? newExerciseDraft.min_weight : 0,
          max_weight: newExerciseUsesWeight ? newExerciseDraft.max_weight : 0,
          weight_step: newExerciseUsesWeight ? newExerciseDraft.weight_step : 1,
          default_reps: newExerciseDraft.default_reps,
          min_reps: newExerciseDraft.min_reps,
          max_reps: newExerciseDraft.max_reps,
          reps_step: newExerciseDraft.reps_step,
        });
        setExercises((current) => [...current, response.exercise]);
        setNameDrafts((current) => ({
          ...current,
          [response.exercise.id]: response.exercise.name,
        }));
        setProfileDrafts((current) => ({
          ...current,
          [response.exercise.id]: response.exercise.profile_key,
        }));
        setWeightDrafts((current) => ({
          ...current,
          [response.exercise.id]: response.exercise.weights,
        }));
        setOptionSettingsDrafts((current) => ({
          ...current,
          [response.exercise.id]: optionSettingsDraft(response.exercise),
        }));
        setNewExerciseDraft(defaultNewExerciseDraft);
      },
      "Exercise added",
    );
  }

  function updateNewExerciseDraft<K extends keyof NewExerciseDraft>(
    field: K,
    value: NewExerciseDraft[K],
  ) {
    setNewExerciseDraft((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function updateNewExerciseMeasurementType(nextType: ExerciseMeasurementType) {
    setNewExerciseDraft((current) => {
      const previousDefaultUnit =
        defaultUnitByMeasurement[current.measurement_type] ?? "reps";
      const shouldReplaceUnit =
        !current.reps_unit.trim() || current.reps_unit === previousDefaultUnit;

      return {
        ...current,
        measurement_type: nextType,
        reps_unit: shouldReplaceUnit
          ? defaultUnitByMeasurement[nextType] ?? "reps"
          : current.reps_unit,
      };
    });
  }

  function applyRehabPreset(preset: RehabPreset) {
    setNewExerciseDraft((current) => ({
      ...current,
      name: preset.name,
      profile_key: preset.profile_key,
      measurement_type: preset.measurement_type,
      reps_unit: preset.reps_unit,
      weights: "",
      default_weight: 0,
      min_weight: 0,
      max_weight: 0,
      weight_step: 1,
      default_reps: preset.default_reps,
      min_reps: preset.min_reps,
      max_reps: preset.max_reps,
      reps_step: preset.reps_step,
    }));
  }

  async function saveDetails(exercise: Exercise) {
    const name = (nameDrafts[exercise.id] ?? "").trim();
    const profileKey = profileDrafts[exercise.id] ?? exercise.profile_key;
    if (!name || (!isNameDirty(exercise) && !isProfileDirty(exercise))) {
      return;
    }

    await runAction(
      `details:${exercise.id}`,
      async () => {
        const response = await updateExercise(exercise.id, {
          name,
          profile_key: profileKey,
        });
        setExercises((current) => replaceExerciseInList(current, response.exercise));
        setNameDrafts((current) => ({
          ...current,
          [exercise.id]: response.exercise.name,
        }));
        setProfileDrafts((current) => ({
          ...current,
          [exercise.id]: response.exercise.profile_key,
        }));
        setOptionSettingsDrafts((current) => ({
          ...current,
          [exercise.id]: optionSettingsDraft(response.exercise),
        }));
      },
      "Exercise saved",
    );
  }

  function updateOptionDraft(
    exerciseId: number,
    field: keyof ExerciseOptionSettingsDraft,
    value: ExerciseOptionSettingsDraft[keyof ExerciseOptionSettingsDraft],
  ) {
    const exercise = exercises.find((candidate) => candidate.id === exerciseId);
    if (!exercise) {
      return;
    }

    setOptionSettingsDrafts((current) => ({
      ...current,
      [exerciseId]: {
        ...(current[exerciseId] ?? optionSettingsDraft(exercise)),
        [field]: value,
      },
    }));
  }

  function updateMeasurementTypeDraft(
    exercise: Exercise,
    nextType: ExerciseMeasurementType,
  ) {
    const currentDraft =
      optionSettingsDrafts[exercise.id] ?? optionSettingsDraft(exercise);
    const previousDefaultUnit =
      defaultUnitByMeasurement[currentDraft.measurement_type] ?? "reps";
    const shouldReplaceUnit =
      !currentDraft.reps_unit.trim() ||
      currentDraft.reps_unit === previousDefaultUnit;

    setOptionSettingsDrafts((current) => ({
      ...current,
      [exercise.id]: {
        ...currentDraft,
        measurement_type: nextType,
        reps_unit: shouldReplaceUnit
          ? defaultUnitByMeasurement[nextType] ?? "reps"
          : currentDraft.reps_unit,
      },
    }));
  }

  async function saveOptionSettings(exercise: Exercise) {
    const draft = optionSettingsDrafts[exercise.id] ?? optionSettingsDraft(exercise);

    await runAction(
      `options:${exercise.id}`,
      async () => {
        const response = await updateExercise(exercise.id, draft);
        setExercises((current) => replaceExerciseInList(current, response.exercise));
        setOptionSettingsDrafts((current) => ({
          ...current,
          [exercise.id]: optionSettingsDraft(response.exercise),
        }));
      },
      "Exercise options saved",
    );
  }

  function toggleExerciseExpanded(exerciseId: number) {
    setExpandedExerciseIds((current) => {
      const next = new Set(current);
      if (next.has(exerciseId)) {
        next.delete(exerciseId);
      } else {
        next.add(exerciseId);
      }
      return next;
    });
  }

  async function toggleActive(exercise: Exercise) {
    await runAction(
      `active:${exercise.id}`,
      async () => {
        const response = await updateExercise(exercise.id, {
          is_active: !exercise.is_active,
        });
        setExercises((current) => replaceExerciseInList(current, response.exercise));
      },
      exercise.is_active ? "Exercise deactivated" : "Exercise reactivated",
    );
  }

  async function deleteExerciseFromSettings(exercise: Exercise) {
    await runAction(
      `delete:${exercise.id}`,
      async () => {
        await deleteExercise(exercise.id);

        setNameDrafts((current) => {
          const next = { ...current };
          delete next[exercise.id];
          return next;
        });
        setProfileDrafts((current) => {
          const next = { ...current };
          delete next[exercise.id];
          return next;
        });
        setWeightDrafts((current) => {
          const next = { ...current };
          delete next[exercise.id];
          return next;
        });
        setOptionSettingsDrafts((current) => {
          const next = { ...current };
          delete next[exercise.id];
          return next;
        });
        setNewWeightDrafts((current) => {
          const next = { ...current };
          delete next[exercise.id];
          return next;
        });
        setExpandedExerciseIds((current) => {
          const next = new Set(current);
          next.delete(exercise.id);
          return next;
        });
        setConfirmDeleteExerciseId(null);

        await load();
      },
      "Exercise deleted",
    );
  }

  async function moveExercise(index: number, direction: -1 | 1) {
    const targetIndex = index + direction;
    if (
      targetIndex < 0 ||
      targetIndex >= exercises.length ||
      hasDirtyDrafts
    ) {
      return;
    }

    await runAction(
      "reorder",
      async () => {
        const reordered = [...exercises];
        [reordered[index], reordered[targetIndex]] = [
          reordered[targetIndex],
          reordered[index],
        ];
        const response = await reorderExercises(
          reordered.map((exercise) => exercise.id),
        );
        hydrate(response.exercises);
      },
      "Exercise order updated",
    );
  }

  function addWeightDraft(exerciseId: number) {
    const value = parseWeight(newWeightDrafts[exerciseId] ?? "");
    if (value === null) {
      return;
    }

    setWeightDrafts((current) => ({
      ...current,
      [exerciseId]: normalizeWeights([...(current[exerciseId] ?? []), value]),
    }));
    setNewWeightDrafts((current) => ({
      ...current,
      [exerciseId]: "",
    }));
  }

  function removeWeightDraft(exerciseId: number, weight: number) {
    setWeightDrafts((current) => ({
      ...current,
      [exerciseId]: (current[exerciseId] ?? []).filter((value) => value !== weight),
    }));
  }

  async function saveWeights(exercise: Exercise) {
    const weights = normalizeWeights(weightDrafts[exercise.id] ?? []);

    await runAction(
      `weights:${exercise.id}`,
      async () => {
        const response = await replaceExerciseWeights(exercise.id, weights);
        const updated = {
          ...exercise,
          weights: response.weights,
        };
        setExercises((current) => replaceExerciseInList(current, updated));
        setWeightDrafts((current) => ({
          ...current,
          [exercise.id]: response.weights,
        }));
      },
      "Weights saved",
    );
  }

  async function runGarminAction(
    actionKey: string,
    action: () => Promise<void>,
  ) {
    setGarminPendingAction(actionKey);
    setGarminError(null);
    setGarminMessage(null);
    try {
      await action();
    } catch (reason: unknown) {
      setGarminError(
        reason instanceof Error ? reason.message : "Garmin action failed.",
      );
    } finally {
      setGarminPendingAction(null);
    }
  }

  async function refreshGarminStatus() {
    await runGarminAction("status", async () => {
      await Promise.all([loadGarminStatus(), loadGarminAutoSyncSettings()]);
      setGarminMessage("Garmin status refreshed");
    });
  }

  async function saveGarminAutoSyncSettings() {
    await runGarminAction("auto-sync", async () => {
      const response = await updateGarminAutoSyncSettings({
        enabled: garminAutoSyncDraft.enabled,
        sync_after_local_time: garminAutoSyncDraft.sync_after_local_time,
        sync_days: garminAutoSyncDraft.sync_days,
      });
      setGarminAutoSync(response);
      setGarminAutoSyncDraft({
        enabled: response.enabled,
        sync_after_local_time: response.sync_after_local_time,
        sync_days: response.sync_days,
      });
      setGarminMessage("Garmin auto-sync settings saved");
    });
  }

  async function connectGarmin(event?: FormEvent) {
    event?.preventDefault();

    const username = garminUsername.trim();
    if (!username || !garminPassword) {
      return;
    }

    await runGarminAction("login", async () => {
      const response = await loginGarmin(username, garminPassword);
      setGarminPassword("");

      if (response.mfa_required && response.mfa_token) {
        setGarminMfaToken(response.mfa_token);
        setGarminMessage("Enter Garmin MFA code");
        return;
      }

      setGarminMfaToken(null);
      setGarminMfaCode("");

      const [status] = await Promise.all([
        loadGarminStatus(),
        loadGarminAutoSyncSettings(),
      ]);

      if (status.connected) {
        setGarminMessage("Garmin connected");
      } else {
        setGarminMessage(null);
        setGarminError(
          "Garmin login succeeded, but tokens were not saved. Check /data/garmin_tokens.",
        );
      }
    });
  }

  async function submitGarminCode(event?: FormEvent) {
    event?.preventDefault();

    if (!garminMfaToken || !garminMfaCode.trim()) {
      return;
    }

    await runGarminAction("mfa", async () => {
      await submitGarminMfa(garminMfaToken, garminMfaCode.trim());

      setGarminMfaToken(null);
      setGarminMfaCode("");

      const [status] = await Promise.all([
        loadGarminStatus(),
        loadGarminAutoSyncSettings(),
      ]);

      if (status.connected) {
        setGarminMessage("Garmin connected");
      } else {
        setGarminMessage(null);
        setGarminError(
          "Garmin MFA succeeded, but tokens were not saved. Check /data/garmin_tokens.",
        );
      }
    });
  }

  async function syncGarminMetrics() {
    await runGarminAction("sync", async () => {
      const syncDays = garminAutoSyncDraft.sync_days || 35;
      const response = await syncGarmin(syncDays);
      const warningCount = Object.keys(response.errors).length;
      setGarminStatus(response.status);
      await loadGarminAutoSyncSettings();
      setGarminMessage(
        `Saved ${response.saved_dates.length} date${
          response.saved_dates.length === 1 ? "" : "s"
        }, skipped ${response.skipped_dates.length}${
          warningCount ? `, ${warningCount} source warning${warningCount === 1 ? "" : "s"}` : ""
        }`,
      );
    });
  }

  async function disconnectGarminAccount() {
    await runGarminAction("disconnect", async () => {
      const response = await disconnectGarmin();
      setGarminStatus(response);
      await loadGarminAutoSyncSettings();
      setGarminPassword("");
      setGarminMfaCode("");
      setGarminMfaToken(null);
      setGarminMessage("Garmin disconnected");
    });
  }
  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p className="muted">Exercises and weights</p>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      <details className="settings-fold-panel garmin-panel">
        <summary>
          <div>
            <span>Garmin</span>
            <div className="muted small">
              {garminStatus === null
                ? "Loading status"
                : garminStatus.connected
                  ? "Connected"
                  : "Disconnected"}
              {`, auto-sync ${garminAutoSyncDraft.enabled ? "enabled" : "disabled"}, ${garminAutoSyncDraft.sync_days} days`}
            </div>
          </div>
          <button
            className="ghost-button compact-action"
            disabled={garminBusy}
            onClick={(event) => {
              event.stopPropagation();
              refreshGarminStatus();
            }}
            type="button"
          >
            Refresh
          </button>
        </summary>

        {garminError && <div className="error-banner">{garminError}</div>}
        {garminMessage && (
          <div className="success-banner">{garminMessage}</div>
        )}

        <div className="garmin-status-grid">
          <div>
            <strong>{garminStatus === null ? "Loading" : garminStatus.connected ? "Connected" : "Not connected"}</strong>
            <span className="muted">status</span>
          </div>
          <div>
            <strong>{formatGarminDateTime(garminStatus?.last_synced_at)}</strong>
            <span className="muted">last sync</span>
          </div>
          <div>
            <strong>{formatGarminDate(garminStatus?.latest_metric?.date)}</strong>
            <span className="muted">latest date</span>
          </div>
        </div>

        <section className="garmin-auto-sync-card">
          <div className="settings-card-header">
            <div>
              <h3>Auto-sync</h3>
              <p className="muted small">
                Runs once per day after {garminAutoSyncDraft.sync_after_local_time}{" "}
                {garminAutoSync?.timezone || "local time"}. No Garmin request is
                made while pages render. Automatic sync runs at most once per
                day; use manual sync for retries.
              </p>
            </div>
            <label className="garmin-auto-sync-toggle">
              <input
                checked={garminAutoSyncDraft.enabled}
                disabled={garminPendingAction === "auto-sync"}
                onChange={(event) =>
                  setGarminAutoSyncDraft((current) => ({
                    ...current,
                    enabled: event.target.checked,
                  }))
                }
                type="checkbox"
              />
              Auto-sync Garmin daily
            </label>
          </div>

          {garminAutoSyncDraft.enabled && garminStatus?.connected === false && (
            <div className="error-banner">
              Auto-sync is enabled, but Garmin is not connected. Connect Garmin
              for automatic sync to run.
            </div>
          )}

          <div className="garmin-auto-sync-controls">
            <label>
              Sync after
              <input
                disabled={garminPendingAction === "auto-sync"}
                onChange={(event) =>
                  setGarminAutoSyncDraft((current) => ({
                    ...current,
                    sync_after_local_time: event.target.value,
                  }))
                }
                type="time"
                value={garminAutoSyncDraft.sync_after_local_time}
              />
            </label>
            <label>
              Sync range
              <input
                disabled={garminPendingAction === "auto-sync"}
                max="90"
                min="1"
                onChange={(event) =>
                  setGarminAutoSyncDraft((current) => ({
                    ...current,
                    sync_days: Number(event.target.value),
                  }))
                }
                type="number"
                value={garminAutoSyncDraft.sync_days}
              />
            </label>
            <button
              className="secondary-button"
              disabled={
                garminPendingAction === "auto-sync" ||
                !garminAutoSyncDirty ||
                garminAutoSyncDraft.sync_days < 1 ||
                garminAutoSyncDraft.sync_days > 90 ||
                !garminAutoSyncDraft.sync_after_local_time
              }
              onClick={saveGarminAutoSyncSettings}
              type="button"
            >
              Save auto-sync settings
            </button>
          </div>

          <div className="garmin-auto-sync-status">
            <div>
              <strong>
                {garminAutoSyncDraft.enabled ? "Enabled" : "Disabled"}
              </strong>
              <span className="muted">auto-sync</span>
            </div>
            <div>
              <strong>{formatGarminDateTime(garminAutoSync?.next_eligible_at)}</strong>
              <span className="muted">next eligible run</span>
            </div>
            <div>
              <strong>{formatGarminDateTime(garminAutoSync?.last_attempt_at)}</strong>
              <span className="muted">last automatic attempt</span>
            </div>
            <div>
              <strong>{formatGarminDateTime(garminAutoSync?.last_success_at)}</strong>
              <span className="muted">last automatic success</span>
            </div>
            <div>
              <strong>{formatGarminAutoSyncResult(garminAutoSync?.last_result ?? null)}</strong>
              <span className="muted">last result</span>
            </div>
            <div>
              <strong title={garminAutoSync?.last_error || undefined}>
                {shortText(garminAutoSync?.last_error)}
              </strong>
              <span className="muted">last error</span>
            </div>
          </div>
        </section>

        {garminMfaToken ? (
          <form className="garmin-form" onSubmit={submitGarminCode}>
            <label>
              MFA code
              <input
                autoComplete="one-time-code"
                disabled={garminPendingAction === "mfa"}
                onChange={(event) => setGarminMfaCode(event.target.value)}
                value={garminMfaCode}
              />
            </label>
            <button
              className="primary-button"
              disabled={garminPendingAction === "mfa" || !garminMfaCode.trim()}
              type="submit"
            >
              Verify
            </button>
          </form>
        ) : garminStatus?.connected ? (
          <div className="garmin-actions">
            <button
              className="secondary-button"
              disabled={garminPendingAction === "sync"}
              onClick={syncGarminMetrics}
              type="button"
            >
              Sync {garminAutoSyncDraft.sync_days || 35} days now
            </button>
            <button
              className="ghost-button"
              disabled={garminPendingAction === "disconnect"}
              onClick={disconnectGarminAccount}
              type="button"
            >
              Disconnect
            </button>
          </div>
        ) : (
          <form className="garmin-login" onSubmit={connectGarmin}>
            <label>
              Email
              <input
                autoComplete="username"
                disabled={garminPendingAction === "login"}
                onChange={(event) => setGarminUsername(event.target.value)}
                value={garminUsername}
              />
            </label>
            <label>
              Password
              <input
                autoComplete="current-password"
                disabled={garminPendingAction === "login"}
                onChange={(event) => setGarminPassword(event.target.value)}
                type="password"
                value={garminPassword}
              />
            </label>
            <button
              className="primary-button"
              disabled={
                garminPendingAction === "login" ||
                !garminUsername.trim() ||
                !garminPassword
              }
              type="submit"
            >
              Connect
            </button>
          </form>
        )}
      </details>

      <AnalysisProfilesPanel profiles={profiles} onProfilesChange={setProfiles} />
      <details className="settings-fold-panel settings-exercises-panel">
        <summary>
          <div>
            <span>Exercises and weights</span>
            <div className="muted small">
              {loading
                ? "Loading exercises"
                : `${exercises.length} exercises configured`}
            </div>
          </div>
        </summary>

        <form className="panel settings-add settings-add-detailed" onSubmit={addExercise}>
          <div className="settings-preset-row" aria-label="Rehab presets">
            {rehabPresets.map((preset) => (
              <button
                className="ghost-button compact-button"
                disabled={pendingAction === "create"}
                key={preset.label}
                onClick={() => applyRehabPreset(preset)}
                type="button"
              >
                {preset.label}
              </button>
            ))}
          </div>

          <div className="settings-options-grid">
            <label>
              Name
              <input
                disabled={pendingAction === "create"}
                onChange={(event) =>
                  updateNewExerciseDraft("name", event.target.value)
                }
                placeholder="Exercise name"
                value={newExerciseDraft.name}
              />
            </label>
            <label>
              Profile
              <select
                disabled={pendingAction === "create"}
                onChange={(event) =>
                  updateNewExerciseDraft("profile_key", event.target.value)
                }
                value={newExerciseDraft.profile_key}
              >
                <option value="">Infer from name</option>
                {activeProfiles.map((profile) => (
                  <option key={profile.key} value={profile.key}>
                    {profile.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Measurement type
              <select
                disabled={pendingAction === "create"}
                onChange={(event) =>
                  updateNewExerciseMeasurementType(
                    event.target.value as ExerciseMeasurementType,
                  )
                }
                value={newExerciseDraft.measurement_type}
              >
                {measurementTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label} - {option.description}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Unit
              <input
                disabled={pendingAction === "create"}
                maxLength={16}
                onChange={(event) =>
                  updateNewExerciseDraft("reps_unit", event.target.value)
                }
                value={newExerciseDraft.reps_unit}
              />
            </label>
            <label>
              {newExerciseQuantityLabels.defaultLabel}
              <input
                disabled={pendingAction === "create"}
                min="1"
                onChange={(event) =>
                  updateNewExerciseDraft("default_reps", Number(event.target.value))
                }
                step="1"
                type="number"
                value={newExerciseDraft.default_reps}
              />
            </label>
            <label>
              {newExerciseQuantityLabels.minLabel}
              <input
                disabled={pendingAction === "create"}
                min="1"
                onChange={(event) =>
                  updateNewExerciseDraft("min_reps", Number(event.target.value))
                }
                step="1"
                type="number"
                value={newExerciseDraft.min_reps}
              />
            </label>
            <label>
              {newExerciseQuantityLabels.maxLabel}
              <input
                disabled={pendingAction === "create"}
                min="1"
                onChange={(event) =>
                  updateNewExerciseDraft("max_reps", Number(event.target.value))
                }
                step="1"
                type="number"
                value={newExerciseDraft.max_reps}
              />
            </label>
            <label>
              {newExerciseQuantityLabels.stepLabel}
              <input
                disabled={pendingAction === "create"}
                min="1"
                onChange={(event) =>
                  updateNewExerciseDraft("reps_step", Number(event.target.value))
                }
                step="1"
                type="number"
                value={newExerciseDraft.reps_step}
              />
            </label>
          </div>

          {newExerciseUsesWeight && (
            <div className="settings-options-grid">
              <label>
                Weight options
                <input
                  disabled={pendingAction === "create"}
                  onChange={(event) =>
                    updateNewExerciseDraft("weights", event.target.value)
                  }
                  placeholder="20, 22.5, 25"
                  value={newExerciseDraft.weights}
                />
              </label>
              <label>
                Default kg
                <input
                  disabled={pendingAction === "create"}
                  min="0"
                  onChange={(event) =>
                    updateNewExerciseDraft(
                      "default_weight",
                      Number(event.target.value),
                    )
                  }
                  step="0.25"
                  type="number"
                  value={newExerciseDraft.default_weight}
                />
              </label>
              <label>
                Min kg
                <input
                  disabled={pendingAction === "create"}
                  min="0"
                  onChange={(event) =>
                    updateNewExerciseDraft("min_weight", Number(event.target.value))
                  }
                  step="0.25"
                  type="number"
                  value={newExerciseDraft.min_weight}
                />
              </label>
              <label>
                Max kg
                <input
                  disabled={pendingAction === "create"}
                  min="0"
                  onChange={(event) =>
                    updateNewExerciseDraft("max_weight", Number(event.target.value))
                  }
                  step="0.25"
                  type="number"
                  value={newExerciseDraft.max_weight}
                />
              </label>
              <label>
                Kg step
                <input
                  disabled={pendingAction === "create"}
                  min="0.25"
                  onChange={(event) =>
                    updateNewExerciseDraft("weight_step", Number(event.target.value))
                  }
                  step="0.25"
                  type="number"
                  value={newExerciseDraft.weight_step}
                />
              </label>
            </div>
          )}

          <div className="settings-create-footer">
            <span className="muted small">{selectedMeasurementOption.description}</span>
            <button
              className="primary-button"
              disabled={
                pendingAction === "create" ||
                !newExerciseDraft.name.trim() ||
                (newExerciseUsesWeight && newExerciseWeights.length === 0)
              }
              type="submit"
            >
              Create
            </button>
          </div>
        </form>

        {loading && <section className="panel muted">Loading settings...</section>}
        {!loading && exercises.length === 0 && (
          <section className="panel">
            <p>No exercises configured.</p>
            <button className="ghost-button" onClick={load} type="button">
              Retry
            </button>
          </section>
        )}
        {hasDirtyDrafts && (
          <div className="success-banner">
            Save exercise changes before reordering.
          </div>
        )}

        <div className="settings-list">
          {exercises.map((exercise, index) => {
            const weights = weightDrafts[exercise.id] ?? [];
            const optionSettings =
              optionSettingsDrafts[exercise.id] ?? optionSettingsDraft(exercise);
            const detailsChanged =
              isNameDirty(exercise) || isProfileDirty(exercise);
            const weightChanged = isWeightDirty(exercise);
            const optionSettingsChanged = isOptionSettingsDirty(exercise);
            const activeToggleRequiresWeight = measurementRequiresWeight(
              optionSettings.measurement_type,
            );
            const detailsPending = pendingAction === `details:${exercise.id}`;
            const activePending = pendingAction === `active:${exercise.id}`;
            const deletePending = pendingAction === `delete:${exercise.id}`;
            const weightsPending = pendingAction === `weights:${exercise.id}`;
            const optionsPending = pendingAction === `options:${exercise.id}`;
            const profileLabel =
              profileLabels[profileDrafts[exercise.id] ?? exercise.profile_key] ??
              "Accessory";
            const isExpanded = expandedExerciseIds.has(exercise.id);
            const bodyId = `exercise-settings-details-${exercise.id}`;

            return (
              <article
                className={`settings-card collapsible-settings-card ${isExpanded ? "is-expanded" : ""}`}
                key={exercise.id}
              >
                <div className="settings-card-header">
                  <div>
                    <h2>{exercise.name}</h2>
                    <p className="muted">{profileLabel}</p>
                  </div>
                  <div className="collapsible-settings-meta">
                    <button
                      className={
                        exercise.is_active
                          ? "secondary-button compact-action"
                          : "ghost-button compact-action"
                      }
                      disabled={
                        activePending ||
                        isBusy ||
                        (!exercise.is_active &&
                          activeToggleRequiresWeight &&
                          weights.length === 0)
                      }
                      onClick={() => toggleActive(exercise)}
                      type="button"
                    >
                      {exercise.is_active ? "Active" : "Inactive"}
                    </button>
                    <button
                      aria-controls={bodyId}
                      aria-expanded={isExpanded}
                      aria-label={`${isExpanded ? "Collapse" : "Expand"} ${exercise.name} settings`}
                      className="collapsible-settings-toggle"
                      onClick={() => toggleExerciseExpanded(exercise.id)}
                      type="button"
                    >
                      <span className="collapsible-settings-toggle-text">
                        {isExpanded ? "Hide" : "Show"}
                      </span>
                      <span aria-hidden="true" className="collapsible-settings-toggle-icon">
                        {isExpanded ? "^" : "v"}
                      </span>
                    </button>
                  </div>
                </div>

                <div
                  className="collapsible-settings-body exercise-settings-body"
                  hidden={!isExpanded}
                  id={bodyId}
                >
                <div className="settings-row">
                  <label>
                    Name
                    <input
                      disabled={detailsPending}
                      onChange={(event) =>
                        setNameDrafts((current) => ({
                          ...current,
                          [exercise.id]: event.target.value,
                        }))
                      }
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          saveDetails(exercise);
                        }
                      }}
                      value={nameDrafts[exercise.id] ?? ""}
                    />
                  </label>
                  <label>
                    Analysis type
                    <select
                      disabled={detailsPending}
                      onChange={(event) =>
                        setProfileDrafts((current) => ({
                          ...current,
                          [exercise.id]: event.target.value,
                        }))
                      }
                      value={profileDrafts[exercise.id] ?? exercise.profile_key}
                    >
                      {profileOptionsForExercise(
                        profileDrafts[exercise.id] ?? exercise.profile_key,
                      ).map((profile) => (
                        <option key={profile.key} value={profile.key}>
                          {profile.label}{profile.is_active ? "" : " (inactive)"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="secondary-button"
                    disabled={
                      detailsPending ||
                      !detailsChanged ||
                      !nameDrafts[exercise.id]?.trim()
                    }
                    onClick={() => saveDetails(exercise)}
                    type="button"
                  >
                    Save
                  </button>
                </div>

                <div className="settings-order">
                  <button
                    className="ghost-button compact-button"
                    disabled={isBusy || hasDirtyDrafts || index === 0}
                    onClick={() => moveExercise(index, -1)}
                    type="button"
                  >
                    Up
                  </button>
                  <button
                    className="ghost-button compact-button"
                    disabled={
                      isBusy || hasDirtyDrafts || index === exercises.length - 1
                    }
                    onClick={() => moveExercise(index, 1)}
                    type="button"
                  >
                    Down
                  </button>
                </div>

                <section className="settings-weights">
                  <h3>Weights</h3>
                  <div className="weight-chip-list">
                    {weights.length === 0 && (
                      <span className="muted small">No presets configured.</span>
                    )}
                    {weights.map((weight) => (
                      <button
                        aria-label={`Remove ${formatSetOption(weight)} kg`}
                        className="weight-chip"
                        disabled={weightsPending}
                        key={weight}
                        onClick={() => removeWeightDraft(exercise.id, weight)}
                        type="button"
                      >
                        {formatSetOption(weight)} kg
                      </button>
                    ))}
                  </div>

                  <div className="settings-row">
                    <label>
                      New weight
                      <input
                        disabled={weightsPending}
                        inputMode="decimal"
                        min="0"
                        onChange={(event) =>
                          setNewWeightDrafts((current) => ({
                            ...current,
                            [exercise.id]: event.target.value,
                          }))
                        }
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            addWeightDraft(exercise.id);
                          }
                        }}
                        placeholder="0"
                        step="0.25"
                        type="number"
                        value={newWeightDrafts[exercise.id] ?? ""}
                      />
                    </label>
                    <button
                      className="ghost-button"
                      disabled={
                        weightsPending ||
                        parseWeight(newWeightDrafts[exercise.id] ?? "") === null
                      }
                      onClick={() => addWeightDraft(exercise.id)}
                      type="button"
                    >
                      Add
                    </button>
                    <button
                      className="secondary-button"
                      disabled={
                        weightsPending ||
                        !weightChanged ||
                        (exercise.is_active && normalizeWeights(weights).length === 0)
                      }
                      onClick={() => saveWeights(exercise)}
                      type="button"
                    >
                      Save weights
                    </button>
                  </div>
                </section>

                <section className="settings-weights">
                  <h3>Set defaults and ranges</h3>
                  <div className="settings-options-grid">
                    <label>
                      Measurement
                      <select
                        disabled={optionsPending}
                        onChange={(event) =>
                          updateMeasurementTypeDraft(
                            exercise,
                            event.target.value as ExerciseMeasurementType,
                          )
                        }
                        value={optionSettings.measurement_type}
                      >
                        {measurementTypeOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Reps unit
                      <input
                        disabled={optionsPending}
                        maxLength={16}
                        onChange={(event) =>
                          updateOptionDraft(
                            exercise.id,
                            "reps_unit",
                            event.target.value,
                          )
                        }
                        type="text"
                        value={optionSettings.reps_unit}
                      />
                    </label>
                    <label>
                      Default kg
                      <input
                        disabled={optionsPending}
                        min="0"
                        onChange={(event) =>
                          updateOptionDraft(
                            exercise.id,
                            "default_weight",
                            Number(event.target.value),
                          )
                        }
                        step="0.25"
                        type="number"
                        value={optionSettings.default_weight}
                      />
                    </label>
                    <label>
                      Min kg
                      <input
                        disabled={optionsPending}
                        min="0"
                        onChange={(event) =>
                          updateOptionDraft(
                            exercise.id,
                            "min_weight",
                            Number(event.target.value),
                          )
                        }
                        step="0.25"
                        type="number"
                        value={optionSettings.min_weight}
                      />
                    </label>
                    <label>
                      Max kg
                      <input
                        disabled={optionsPending}
                        min="0"
                        onChange={(event) =>
                          updateOptionDraft(
                            exercise.id,
                            "max_weight",
                            Number(event.target.value),
                          )
                        }
                        step="0.25"
                        type="number"
                        value={optionSettings.max_weight}
                      />
                    </label>
                    <label>
                      Kg step
                      <input
                        disabled={optionsPending}
                        min="0.25"
                        onChange={(event) =>
                          updateOptionDraft(
                            exercise.id,
                            "weight_step",
                            Number(event.target.value),
                          )
                        }
                        step="0.25"
                        type="number"
                        value={optionSettings.weight_step}
                      />
                    </label>
                    <label>
                      Default reps
                      <input
                        disabled={optionsPending}
                        min="1"
                        onChange={(event) =>
                          updateOptionDraft(
                            exercise.id,
                            "default_reps",
                            Number(event.target.value),
                          )
                        }
                        step="1"
                        type="number"
                        value={optionSettings.default_reps}
                      />
                    </label>
                    <label>
                      Min reps
                      <input
                        disabled={optionsPending}
                        min="1"
                        onChange={(event) =>
                          updateOptionDraft(
                            exercise.id,
                            "min_reps",
                            Number(event.target.value),
                          )
                        }
                        step="1"
                        type="number"
                        value={optionSettings.min_reps}
                      />
                    </label>
                    <label>
                      Max reps
                      <input
                        disabled={optionsPending}
                        min="1"
                        onChange={(event) =>
                          updateOptionDraft(
                            exercise.id,
                            "max_reps",
                            Number(event.target.value),
                          )
                        }
                        step="1"
                        type="number"
                        value={optionSettings.max_reps}
                      />
                    </label>
                    <label>
                      Reps step
                      <input
                        disabled={optionsPending}
                        min="1"
                        onChange={(event) =>
                          updateOptionDraft(
                            exercise.id,
                            "reps_step",
                            Number(event.target.value),
                          )
                        }
                        step="1"
                        type="number"
                        value={optionSettings.reps_step}
                      />
                    </label>
                  </div>
                  <button
                    className="secondary-button"
                    disabled={optionsPending || !optionSettingsChanged}
                    onClick={() => saveOptionSettings(exercise)}
                    type="button"
                  >
                    Save set options
                  </button>
                </section>

                <section className="settings-danger-zone">
                  {(() => {
                    const usage = exercise.usage;
                    const canDelete = exercise.can_delete !== false;

                    return (
                      <>
                  <div>
                    <h3>Danger zone</h3>
                    <p className="muted small">
                      Delete only exercises that have no workout history. Use
                      Inactive to hide exercises that already have logs.
                    </p>
                    <p className="muted small">
                      {formatExerciseUsage(exercise)}
                    </p>
                    {!canDelete ? (
                      <p className="muted small">
                        Cannot delete: used by {usage?.workout_count ?? 0} workout
                        {(usage?.workout_count ?? 0) === 1 ? "" : "s"}
                        {usage?.draft_count
                          ? " and active draft"
                          : ""}
                        . Deactivate it instead.
                      </p>
                    ) : null}
                  </div>

                  {!canDelete ? (
                    <button
                      className="danger-button compact-action"
                      disabled
                      type="button"
                    >
                      Delete
                    </button>
                  ) : confirmDeleteExerciseId === exercise.id ? (
                    <div className="danger-confirm-row">
                      <span>
                        Delete "{exercise.name}"? This removes its weight presets
                        and cannot be undone.
                      </span>
                      <button
                        className="ghost-button compact-action"
                        onClick={() => setConfirmDeleteExerciseId(null)}
                        type="button"
                      >
                        Cancel
                      </button>
                      <button
                        className="danger-button compact-action"
                        disabled={deletePending}
                        onClick={() => deleteExerciseFromSettings(exercise)}
                        type="button"
                      >
                        Delete permanently
                      </button>
                    </div>
                  ) : (
                    <button
                      className="danger-button compact-action"
                      disabled={isBusy}
                      onClick={() => setConfirmDeleteExerciseId(exercise.id)}
                      type="button"
                    >
                      Delete
                    </button>
                  )}
                      </>
                    );
                  })()}
                </section>
                </div>
              </article>
            );
          })}
        </div>
      </details>
    </section>
  );
}
