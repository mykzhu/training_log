import { FormEvent, useEffect, useState } from "react";

import {
  createExerciseProfile,
  updateExerciseProfile,
} from "../../api/exercises";
import type { ExerciseProfile } from "../../api/types";

type ProfileDraft = {
  label: string;
  category: string;
  exercise_factor: string;
  compound_factor: string;
  back_factor: string;
  is_active: boolean;
};

type NewProfileDraft = Omit<ProfileDraft, "is_active"> & {
  key: string;
};

const EMPTY_NEW_PROFILE: NewProfileDraft = {
  key: "",
  label: "",
  category: "",
  exercise_factor: "1",
  compound_factor: "0.5",
  back_factor: "0.3",
};

type Props = {
  profiles: ExerciseProfile[];
  onProfilesChange: (profiles: ExerciseProfile[]) => void;
};

function sortProfiles(profiles: ExerciseProfile[]) {
  return [...profiles].sort((left, right) => {
    if (left.is_active !== right.is_active) {
      return left.is_active ? -1 : 1;
    }
    if (left.sort_order !== right.sort_order) {
      return left.sort_order - right.sort_order;
    }
    return left.label.localeCompare(right.label);
  });
}

function parseFactor(value: string) {
  const factor = Number(value);
  return Number.isFinite(factor) && factor >= 0 && factor <= 5 ? factor : null;
}

function profileToDraft(profile: ExerciseProfile): ProfileDraft {
  return {
    label: profile.label,
    category: profile.category,
    exercise_factor: String(profile.exercise_factor),
    compound_factor: String(profile.compound_factor),
    back_factor: String(profile.back_factor),
    is_active: profile.is_active,
  };
}

function isDraftValid(draft: ProfileDraft | NewProfileDraft) {
  return (
    draft.label.trim().length > 0 &&
    draft.category.trim().length > 0 &&
    parseFactor(draft.exercise_factor) !== null &&
    parseFactor(draft.compound_factor) !== null &&
    parseFactor(draft.back_factor) !== null
  );
}

function generatedKeyPreview(label: string, key: string) {
  if (key.trim()) {
    return key.trim().toLowerCase();
  }
  const preview = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return preview || "auto";
}

function replaceProfile(profiles: ExerciseProfile[], updated: ExerciseProfile) {
  return profiles.map((profile) =>
    profile.key === updated.key ? updated : profile,
  );
}

export default function AnalysisProfilesPanel({
  profiles,
  onProfilesChange,
}: Props) {
  const [drafts, setDrafts] = useState<Record<string, ProfileDraft>>({});
  const [newDraft, setNewDraft] = useState<NewProfileDraft>(EMPTY_NEW_PROFILE);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [expandedProfileKeys, setExpandedProfileKeys] = useState<Set<string>>(
    () => new Set(),
  );

  useEffect(() => {
    setDrafts(
      Object.fromEntries(
        profiles.map((profile) => [profile.key, profileToDraft(profile)]),
      ),
    );
  }, [profiles]);

  function profileChanged(profile: ExerciseProfile) {
    const draft = drafts[profile.key];
    if (!draft) {
      return false;
    }
    return (
      draft.label.trim() !== profile.label ||
      draft.category.trim() !== profile.category ||
      parseFactor(draft.exercise_factor) !== profile.exercise_factor ||
      parseFactor(draft.compound_factor) !== profile.compound_factor ||
      parseFactor(draft.back_factor) !== profile.back_factor ||
      draft.is_active !== profile.is_active
    );
  }

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

  async function addProfile(event?: FormEvent) {
    event?.preventDefault();
    if (!isDraftValid(newDraft)) {
      return;
    }

    const exerciseFactor = parseFactor(newDraft.exercise_factor);
    const compoundFactor = parseFactor(newDraft.compound_factor);
    const backFactor = parseFactor(newDraft.back_factor);
    if (exerciseFactor === null || compoundFactor === null || backFactor === null) {
      return;
    }

    await runAction(
      "profile:create",
      async () => {
        const response = await createExerciseProfile({
          key: newDraft.key.trim() || undefined,
          label: newDraft.label.trim(),
          category: newDraft.category.trim(),
          exercise_factor: exerciseFactor,
          compound_factor: compoundFactor,
          back_factor: backFactor,
        });
        onProfilesChange(sortProfiles([...profiles, response.profile]));
        setNewDraft(EMPTY_NEW_PROFILE);
      },
      "Analysis type added",
    );
  }

  async function saveProfile(profile: ExerciseProfile) {
    const draft = drafts[profile.key];
    if (!draft || !isDraftValid(draft) || !profileChanged(profile)) {
      return;
    }

    const exerciseFactor = parseFactor(draft.exercise_factor);
    const compoundFactor = parseFactor(draft.compound_factor);
    const backFactor = parseFactor(draft.back_factor);
    if (exerciseFactor === null || compoundFactor === null || backFactor === null) {
      return;
    }

    await runAction(
      `profile:${profile.key}`,
      async () => {
        const response = await updateExerciseProfile(profile.key, {
          label: draft.label.trim(),
          category: draft.category.trim(),
          exercise_factor: exerciseFactor,
          compound_factor: compoundFactor,
          back_factor: backFactor,
          is_active: draft.is_active,
        });
        onProfilesChange(sortProfiles(replaceProfile(profiles, response.profile)));
      },
      "Analysis type saved",
    );
  }

  function toggleProfileExpanded(profileKey: string) {
    setExpandedProfileKeys((current) => {
      const next = new Set(current);
      if (next.has(profileKey)) {
        next.delete(profileKey);
      } else {
        next.add(profileKey);
      }
      return next;
    });
  }

  const customProfileCount = profiles.filter(
    (profile) => !profile.is_builtin,
  ).length;

  return (
    <details className="settings-fold-panel analysis-profile-panel">
      <summary>
        <div>
          <span>Analysis types</span>
          <div className="muted small">
            {profiles.length} types, {customProfileCount} custom
          </div>
        </div>
      </summary>

      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      <form className="analysis-profile-form" onSubmit={addProfile}>
        <label>
          Label
          <input
            disabled={pendingAction === "profile:create"}
            onChange={(event) => setNewDraft((current) => ({ ...current, label: event.target.value }))}
            placeholder="Cable row"
            value={newDraft.label}
          />
        </label>
        <label>
          Key
          <input
            disabled={pendingAction === "profile:create"}
            onChange={(event) => setNewDraft((current) => ({ ...current, key: event.target.value }))}
            placeholder={generatedKeyPreview(newDraft.label, newDraft.key)}
            value={newDraft.key}
          />
        </label>
        <label>
          Category
          <input
            disabled={pendingAction === "profile:create"}
            onChange={(event) => setNewDraft((current) => ({ ...current, category: event.target.value }))}
            placeholder="upper pull"
            value={newDraft.category}
          />
        </label>
        <div className="profile-factor-grid">
          <label>
            Load
            <input
              disabled={pendingAction === "profile:create"}
              inputMode="decimal"
              max="5"
              min="0"
              onChange={(event) => setNewDraft((current) => ({ ...current, exercise_factor: event.target.value }))}
              step="0.05"
              type="number"
              value={newDraft.exercise_factor}
            />
          </label>
          <label>
            Compound
            <input
              disabled={pendingAction === "profile:create"}
              inputMode="decimal"
              max="5"
              min="0"
              onChange={(event) => setNewDraft((current) => ({ ...current, compound_factor: event.target.value }))}
              step="0.05"
              type="number"
              value={newDraft.compound_factor}
            />
          </label>
          <label>
            Back
            <input
              disabled={pendingAction === "profile:create"}
              inputMode="decimal"
              max="5"
              min="0"
              onChange={(event) => setNewDraft((current) => ({ ...current, back_factor: event.target.value }))}
              step="0.05"
              type="number"
              value={newDraft.back_factor}
            />
          </label>
        </div>
        <button
          className="primary-button"
          disabled={pendingAction === "profile:create" || !isDraftValid(newDraft)}
          type="submit"
        >
          Add
        </button>
      </form>

      <div className="analysis-profile-grid">
        {profiles.map((profile) => {
          const draft = drafts[profile.key] ?? profileToDraft(profile);
          const profilePending = pendingAction === `profile:${profile.key}`;
          const deactivateDisabled = profile.key === "accessory" || profile.exercise_count > 0;
          const isExpanded = expandedProfileKeys.has(profile.key);
          const bodyId = `analysis-profile-details-${profile.key}`;

          return (
            <article
              className={`analysis-profile-card collapsible-settings-card ${isExpanded ? "is-expanded" : ""}`}
              key={profile.key}
            >
              <div className="analysis-profile-card-header">
                <div>
                  <h3>{profile.label}</h3>
                  <div className="profile-meta">
                    <span>{profile.key}</span>
                    <span>{profile.is_builtin ? "built-in" : "custom"}</span>
                    <span>{profile.is_active ? "active" : "inactive"}</span>
                  </div>
                </div>
                <div className="collapsible-settings-meta">
                  <span className="status-badge">Used by {profile.exercise_count}</span>
                  <button
                    aria-controls={bodyId}
                    aria-expanded={isExpanded}
                    aria-label={`${isExpanded ? "Collapse" : "Expand"} ${profile.label} analysis type`}
                    className="collapsible-settings-toggle"
                    onClick={() => toggleProfileExpanded(profile.key)}
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
                className="collapsible-settings-body analysis-profile-card-body"
                hidden={!isExpanded}
                id={bodyId}
              >
                <label>
                  Label
                  <input
                    disabled={profilePending}
                    onChange={(event) => setDrafts((current) => ({
                      ...current,
                      [profile.key]: { ...draft, label: event.target.value },
                    }))}
                    value={draft.label}
                  />
                </label>
                <label>
                  Category
                  <input
                    disabled={profilePending}
                    onChange={(event) => setDrafts((current) => ({
                      ...current,
                      [profile.key]: { ...draft, category: event.target.value },
                    }))}
                    value={draft.category}
                  />
                </label>
                <div className="profile-factor-grid">
                  <label>
                    Load
                    <input
                      disabled={profilePending}
                      inputMode="decimal"
                      max="5"
                      min="0"
                      onChange={(event) => setDrafts((current) => ({
                        ...current,
                        [profile.key]: { ...draft, exercise_factor: event.target.value },
                      }))}
                      step="0.05"
                      type="number"
                      value={draft.exercise_factor}
                    />
                  </label>
                  <label>
                    Compound
                    <input
                      disabled={profilePending}
                      inputMode="decimal"
                      max="5"
                      min="0"
                      onChange={(event) => setDrafts((current) => ({
                        ...current,
                        [profile.key]: { ...draft, compound_factor: event.target.value },
                      }))}
                      step="0.05"
                      type="number"
                      value={draft.compound_factor}
                    />
                  </label>
                  <label>
                    Back
                    <input
                      disabled={profilePending}
                      inputMode="decimal"
                      max="5"
                      min="0"
                      onChange={(event) => setDrafts((current) => ({
                        ...current,
                        [profile.key]: { ...draft, back_factor: event.target.value },
                      }))}
                      step="0.05"
                      type="number"
                      value={draft.back_factor}
                    />
                  </label>
                </div>
                <label className="profile-active-toggle">
                  <input
                    checked={draft.is_active}
                    disabled={profilePending || deactivateDisabled}
                    onChange={(event) => setDrafts((current) => ({
                      ...current,
                      [profile.key]: { ...draft, is_active: event.target.checked },
                    }))}
                    type="checkbox"
                  />
                  Active
                </label>
                <button
                  className="secondary-button"
                  disabled={profilePending || !profileChanged(profile) || !isDraftValid(draft)}
                  onClick={() => saveProfile(profile)}
                  type="button"
                >
                  Save
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </details>
  );
}
