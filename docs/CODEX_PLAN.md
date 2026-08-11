# Training Log — CODEX_PLAN.md

Created: 2026-08-11  
Current observed app version: 1.7.0  
Repository: mykzhu/training_log

This is the restored active Codex roadmap. It includes the new back-pain / rehab exercise tracking plan and carryover items that were missing, unfinished, insufficiently verified, or lost from previous plans.

---

## Executive summary

The app already has a stronger exercise model than before:

- exercise measurement types exist
- exercise option settings exist
- active draft and finished workout exercises snapshot measurement type and unit
- Exercise Stats can handle non-weighted primary metrics
- backup schema is already newer and contains exercise measurement/settings data

But the app is not yet finished for the real user goal:

> Track back-pain / rehab exercises such as Dead Bug, Cat-Cow, Bird Dog, Side Plank, McGill Curl-up, Pelvic Tilt, Glute Bridge, etc., and understand whether they help or worsen back pain.

Main remaining gaps:

1. Current Workout UI still hardcodes Kg + Reps.
2. Settings exercise creation is still weight-first.
3. Active non-weighted exercises still require fake 0 kg weight options.
4. There are no built-in Back rehab / Mobility / Core stability profiles.
5. There is no per-exercise back-pain response tracking.
6. Some previous plan items were implemented but not cleanly audited.
7. docs/CODEX_PLAN.md was missing/replaced before; this file restores it as the active roadmap.

---

## Mandatory Codex operating rules

Before implementing any phase:

```text
Read AGENTS.md.
Read docs/CODEX_PLAN.md.
Read relevant skill files from docs/codex-skills/.
Inspect current code before editing.
Keep changes phase-scoped.
Do not implement later phases unless explicitly requested.
Do not bump config.yaml version except in release phase.
Do not silently change backup/restore compatibility.
Run tests/builds requested by the phase.
Report changed files and verification results.
```

Recommended skill files:

```text
docs/codex-skills/skills/training-log-phase-executor/SKILL.md
docs/codex-skills/skills/training-log-frontend-ux/SKILL.md
docs/codex-skills/skills/training-log-backend-api/SKILL.md
docs/codex-skills/skills/training-log-stats-training-load/SKILL.md
docs/codex-skills/skills/training-log-backup-restore/SKILL.md
docs/codex-skills/skills/training-log-release-verification/SKILL.md
docs/codex-skills/skills/training-log-code-reviewer/SKILL.md
```

---

## Current relevant architecture

Current measurement types:

```text
weighted_reps
bodyweight_reps
loaded_carry_time
loaded_carry_distance
reps_only
```

Current intended meaning:

```text
weighted_reps         = kg × reps
bodyweight_reps       = reps only, usually bodyweight movement
reps_only             = reps only, no kg volume meaning
loaded_carry_time     = kg × seconds
loaded_carry_distance = kg × meters
```

Missing measurement type:

```text
duration_only         = seconds only, no kg
```

This is needed for Side Plank, Front Plank, McGill hold, breathing holds, and other rehab/mobility holds.

---

# Phase 32 — Rehab exercise measurement model and logging UX

Status: Completed 2026-08-11

## Goal

Make it possible to create, configure, log, finish, restore, and view stats for back-pain / rehab exercises without fake kg fields.

Examples:

```text
Dead Bug       → reps_only
Cat-Cow        → reps_only
Bird Dog       → reps_only or duration_only
Side Plank     → duration_only
McGill Curl-up → reps_only or duration_only
Pelvic Tilt    → reps_only
Glute Bridge   → reps_only
```

---

## 32.1 Add duration_only measurement type

Target files:

```text
app/repositories/exercises.py
app/schemas.py
frontend/src/api/types.ts
frontend/src/api/generated.ts
docs/openapi.json
frontend/src/pages/ExerciseStatsPage.tsx
frontend/src/components/ExerciseCard.tsx
frontend/src/components/SetRow.tsx
tests/test_api_exercises.py
tests/test_api_current_workout.py
tests/test_api_workouts.py
tests/test_api_stats.py
tests/test_backup_service.py
tests/test_migrations.py
```

Backend changes:

```python
VALID_MEASUREMENT_TYPES = {
    "weighted_reps",
    "bodyweight_reps",
    "loaded_carry_time",
    "loaded_carry_distance",
    "reps_only",
    "duration_only",
}
```

```python
REPS_UNIT_DEFAULTS = {
    "weighted_reps": "reps",
    "bodyweight_reps": "reps",
    "loaded_carry_time": "sec",
    "loaded_carry_distance": "m",
    "reps_only": "reps",
    "duration_only": "sec",
}
```

Update `derive_set_metrics()`:

```python
elif measurement_type == "duration_only":
    total_volume_kg = 0.0
    bodyweight_reps = 0
    duration_seconds = total_reps
    distance_m = 0
```

Keep using the underlying `set_entries.reps` column as the generic quantity. For `duration_only`, `reps` stores seconds.

Frontend type update:

```ts
export type ExerciseMeasurementType =
  | "weighted_reps"
  | "bodyweight_reps"
  | "loaded_carry_time"
  | "loaded_carry_distance"
  | "reps_only"
  | "duration_only";
```

Exercise Stats helper update:

```ts
function primaryMetricKind(measurementType: string): PrimaryMetricKind {
  if (measurementType === "bodyweight_reps" || measurementType === "reps_only") {
    return "bodyweight_reps";
  }

  if (measurementType === "loaded_carry_time" || measurementType === "duration_only") {
    return "duration_seconds";
  }

  if (measurementType === "loaded_carry_distance") {
    return "distance_m";
  }

  return "volume_kg";
}
```

Acceptance criteria:

```text
duration_only is accepted by API.
duration_only is returned by API responses.
duration_only is preserved in active draft snapshots.
duration_only is preserved in finished workout snapshots.
Exercise Stats uses duration as primary metric.
No kg volume is shown for duration-only exercises.
OpenAPI and frontend types include duration_only.
```

Implementation status:

```text
Completed 2026-08-11:
- duration_only backend measurement model and derived duration metrics.
- API/OpenAPI/generated frontend contract refresh.
- Exercise Stats duration-primary handling.
- Current/Edit workout set cards hide kg controls for non-weighted measurements.
- Backup validation/restore accepts duration_only without active weight options.
```

---

## 32.2 Relax active exercise weight requirement for non-weighted exercises

Current problem:

```text
Active exercises still require at least one explicit weight option.
This forces fake 0 kg setup for Dead Bug, Cat-Cow, Side Plank, etc.
```

Required behavior:

Only these require explicit weight options:

```text
weighted_reps
loaded_carry_time
loaded_carry_distance
```

These do not:

```text
bodyweight_reps
reps_only
duration_only
```

Implementation helper:

```python
WEIGHTED_MEASUREMENT_TYPES = {
    "weighted_reps",
    "loaded_carry_time",
    "loaded_carry_distance",
}

def measurement_requires_weight_options(measurement_type: str) -> bool:
    return measurement_type in WEIGHTED_MEASUREMENT_TYPES
```

In `create_exercise()`:

```python
measurement = normalize_measurement_settings(...)
requires_weight = measurement_requires_weight_options(measurement["measurement_type"])

if is_active and requires_weight and not normalized_weights:
    raise ActiveExerciseWeightError("Weighted active exercise must have at least one weight.")
```

For non-weighted active exercises:

```text
do not require exercise_weight_options rows
effective weight_options should be [0]
default_weight/min_weight/max_weight should normalize to 0
weight controls should be hidden in UI
```

In `update_exercise()`:

```text
If changing active exercise from non-weighted to weighted:
  reject unless explicit weight options exist.

If changing weighted to non-weighted:
  allow it.
  hide old weights in non-weighted UI.
```

Tests:

```python
def test_create_active_reps_only_exercise_without_weights_succeeds()
def test_create_active_duration_only_exercise_without_weights_succeeds()
def test_create_weighted_exercise_without_weights_still_rejected()
def test_update_nonweighted_to_weighted_without_weights_is_rejected()
def test_update_weighted_to_reps_only_is_allowed()
```

Acceptance criteria:

```text
Dead Bug can be active with no explicit weights.
Cat-Cow can be active with no explicit weights.
Side Plank duration_only can be active with no explicit weights.
Deadlift without weights is still rejected.
No fake 0 kg field is required from the user.
```

Implementation status:

```text
Completed 2026-08-11:
- Backend active-weight validation now applies only to weighted_reps, loaded_carry_time, and loaded_carry_distance.
- Non-weighted active exercises normalize weight settings to 0 and expose [0] as effective weight options.
- Weighted active exercises without explicit weights remain rejected.
```

---

## 32.3 Add built-in rehab/mobility/core-stability profiles

Target files:

```text
app/services/default_analysis_profiles.py
app/repositories/analysis_profiles.py
tests/test_analysis.py
tests/test_api_exercises.py
tests/test_backup_service.py
```

Add built-in profiles:

```python
"back_rehab": {
    "category": "back rehab",
    "exercise_factor": 0.15,
    "compound_factor": 0.0,
    "back_factor": 0.0,
},
"core_stability": {
    "category": "core stability",
    "exercise_factor": 0.25,
    "compound_factor": 0.1,
    "back_factor": 0.05,
},
"mobility": {
    "category": "mobility",
    "exercise_factor": 0.10,
    "compound_factor": 0.0,
    "back_factor": 0.0,
},
```

Labels:

```python
"back_rehab": "Back rehab"
"core_stability": "Core stability"
"mobility": "Mobility"
```

Name/profile inference:

```python
"dead bug": "core_stability",
"cat cow": "mobility",
"cat-cow": "mobility",
"bird dog": "core_stability",
"mcgill curl-up": "back_rehab",
"mcgill curlup": "back_rehab",
"pelvic tilt": "mobility",
"side plank": "core_stability",
"front plank": "core_stability",
"plank": "core_stability",
"glute bridge": "core_stability",
"child pose": "mobility",
"cobra": "mobility",
"prone press up": "mobility",
```

Important note:

```text
Cobra/prone press-up may aggravate this specific user, so support them as exercises but do not recommend them automatically.
```

Add measurement inference helper:

```python
def default_measurement_settings_for_name(name: str) -> dict[str, str]:
    normalized = normalize_exercise_name(name).lower()

    if "carry" in normalized:
        return {"measurement_type": "loaded_carry_time", "reps_unit": "sec"}

    if "side plank" in normalized or "front plank" in normalized or normalized == "plank":
        return {"measurement_type": "duration_only", "reps_unit": "sec"}

    if any(fragment in normalized for fragment in (
        "dead bug",
        "cat cow",
        "cat-cow",
        "bird dog",
        "mcgill curl",
        "pelvic tilt",
        "glute bridge",
    )):
        return {"measurement_type": "reps_only", "reps_unit": "reps"}

    if "crunch" in normalized:
        return {"measurement_type": "bodyweight_reps", "reps_unit": "reps"}

    return {"measurement_type": "weighted_reps", "reps_unit": "reps"}
```

Tests:

```python
def test_create_dead_bug_infers_core_stability_and_reps_only()
def test_create_cat_cow_infers_mobility_and_reps_only()
def test_create_side_plank_infers_core_stability_and_duration_only()
def test_builtin_rehab_profiles_are_seeded_and_active()
def test_rehab_profile_load_factors_are_low()
```

Acceptance criteria:

```text
Dead Bug defaults to core_stability + reps_only.
Cat-Cow defaults to mobility + reps_only.
Side Plank defaults to core_stability + duration_only.
Rehab profiles appear in Settings analysis profile list.
Rehab movements add little/no back stress by default.
```

Implementation status:

```text
Completed 2026-08-11:
- Added built-in back_rehab, core_stability, and mobility profiles.
- Added rehab/mobility/core stability profile inference for common back-pain exercises.
- Added reps_only/duration_only measurement inference for Dead Bug, Cat-Cow, Side Plank, and related rehab movements.
- Backup export/old-schema restore paths include the new built-in profiles.
```

---

## 32.4 Make Settings exercise creation measurement-aware

Target files:

```text
frontend/src/pages/SettingsPage.tsx
frontend/src/styles.css
frontend/src/api/exercises.ts
frontend/src/api/types.ts
```

New add-exercise form:

```text
Name
Profile
Measurement type
Default quantity
Min quantity
Max quantity
Step
Weight options only if measurement requires weight
Create
```

Measurement labels:

```text
Weighted reps      → Weight + reps
Bodyweight reps    → Reps only
Reps only          → Reps only
Duration only      → Seconds only
Loaded carry time  → Weight + seconds
Loaded carry dist. → Weight + meters
```

Dynamic UI:

```text
If measurement requires weight:
  show weight options field
  show default/min/max/step weight fields

If measurement does not require weight:
  hide weight options field
  hide weight settings
  force default/min/max weight to 0 in payload
```

Quantity settings:

```text
reps_only/bodyweight_reps:
  Default reps / Min reps / Max reps / Reps step / unit reps

duration_only:
  Default seconds / Min seconds / Max seconds / Seconds step / unit sec

loaded_carry_distance:
  Default meters / Min meters / Max meters / Meter step / unit m
```

Preset buttons:

```text
Dead Bug
Cat-Cow
Bird Dog
McGill Curl-up
Side Plank
Pelvic Tilt
Glute Bridge
```

Preset values:

```ts
const rehabPresets = [
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
```

Acceptance criteria:

```text
User can create Dead Bug from preset.
User can create Cat-Cow without kg.
User can create Side Plank as seconds-only.
No fake 0 kg input appears for non-weighted exercise creation.
New exercise appears active and selectable in Current Workout.
```

Implementation status:

```text
Completed 2026-08-11:
- Settings add-exercise form now exposes profile, measurement type, quantity defaults/ranges, and unit.
- Weight options and kg defaults are hidden for non-weighted measurements and zeroed in create payloads.
- Added rehab preset buttons for Dead Bug, Cat-Cow, Bird Dog, McGill Curl-up, Side Plank, Pelvic Tilt, and Glute Bridge.
```

---

## 32.5 Make Current Workout and Edit Workout measurement-aware

Current problem:

```text
ExerciseCard and SetRow hardcode Kg/Reps/kg volume.
```

Target files:

```text
frontend/src/components/ExerciseCard.tsx
frontend/src/components/SetRow.tsx
frontend/src/components/LegacyActiveWorkoutView.tsx
frontend/src/pages/CurrentWorkoutPage.tsx
frontend/src/pages/HistoryPage.tsx
frontend/src/pages/ExerciseStatsPage.tsx
frontend/src/utils/setOptions.ts
frontend/src/styles.css
```

Create helper:

```text
frontend/src/utils/measurementUi.ts
```

Suggested API:

```ts
import type { ExerciseMeasurementType } from "../api/types";

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
        quantityLabel: "Seconds",
        quantityUnit: repsUnit || "sec",
        addButtonLabel: "Add time",
        setSummaryLabel: "sec",
        totalSummary: ({ totalSets, durationSeconds }) =>
          `${totalSets} sets · ${durationSeconds} sec`,
      };

    case "loaded_carry_time":
      return {
        usesWeight: true,
        weightLabel: "Kg",
        quantityLabel: "Seconds",
        quantityUnit: repsUnit || "sec",
        addButtonLabel: "Add carry",
        setSummaryLabel: "sec",
        totalSummary: ({ totalSets, durationSeconds }) =>
          `${totalSets} sets · ${durationSeconds} sec`,
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
```

UI behavior:

```text
weighted_reps:
  show Kg + Reps
  summary: 3 sets · 15 reps · 1500 kg

reps_only/bodyweight_reps:
  hide Kg
  show Reps only
  summary: 3 sets · 30 reps

duration_only:
  hide Kg
  show Seconds only
  summary: 3 sets · 60 sec

loaded_carry_time:
  show Kg + Seconds
  summary: 3 sets · 120 sec

loaded_carry_distance:
  show Kg + Meters
  summary: 3 sets · 100 m
```

Acceptance criteria:

```text
Dead Bug logging shows reps only.
Cat-Cow logging shows reps only.
Side Plank logging shows seconds only.
Deadlift still shows kg + reps.
Edit Workout uses the same measurement-aware UI.
No non-weighted exercise shows kg controls.
```

Implementation status:

```text
Completed 2026-08-11:
- Added shared measurementUi helper for weight visibility, quantity labels, units, and summaries.
- Current Workout and legacy active logging hide kg controls for reps-only/bodyweight/duration-only exercises.
- Edit Workout set rows and add-set controls use the same measurement-aware UI.
- Edit Workout local recalculation preserves duration-only seconds and zero kg volume for non-weighted measurements.
```

---

## 32.6 Ensure analysis does not over-score rehab exercises

Target files:

```text
app/services/analysis_service.py
app/services/stats_service.py
app/services/training_load_service.py
tests/test_analysis.py
tests/test_api_stats.py
```

Rules:

```text
back_rehab and mobility should contribute very low general load.
back_rehab and mobility should not add back_stress_score by default.
core_stability can add small load and tiny back factor.
duration_only and reps_only can be scored by profile factors, but low-factor profiles keep effect small.
```

Tests:

```python
def test_back_rehab_profile_adds_minimal_load_and_zero_back_stress()
def test_mobility_profile_adds_minimal_load_and_zero_back_stress()
def test_core_stability_adds_small_load()
def test_duration_only_side_plank_does_not_compute_e1rm()
def test_rehab_only_workout_has_light_load_label()
```

Acceptance criteria:

```text
Dead Bug does not inflate Strength Intensity/e1RM.
Cat-Cow does not inflate kg volume.
Rehab-only workout has low load.
Rehab-only workout does not create heavy back stress.
Stats page remains stable with rehab-only history.
```

Implementation status:

```text
Completed 2026-08-11:
- Made e1RM/intensity calculations measurement-aware so only weighted_reps sets can produce e1RM.
- Preserved low load and zero/default-low back stress for back_rehab, mobility, and core_stability profiles.
- Added regression coverage for rehab-only workouts, duration-only Side Plank stats, and non-strength intensity exclusion.
```

---

## 32.7 Backup/restore compatibility for rehab measurement type

Target files:

```text
app/services/backup_service.py
tests/test_backup_service.py
tests/test_api_backup.py
```

Required behavior:

```text
Current backup exports duration_only exercises.
Current restore accepts duration_only.
Old backups without measurement_type default safely.
Old backups restore and can later use new rehab profiles.
No credentials/raw diagnostics leak.
```

Tests:

```python
def test_backup_restore_preserves_duration_only_exercise()
def test_backup_restore_preserves_rehab_profiles()
def test_old_backup_defaults_missing_measurement_fields()
def test_current_backup_contains_no_garmin_raw_diagnostics()
```

Implementation status:

```text
Completed 2026-08-11:
- Confirmed current backup exports duration_only exercise/workout snapshots and rehab analysis profiles.
- Confirmed restore preserves duration_only measurement settings and rehab profile assignments.
- Confirmed older backup schemas default missing measurement fields safely.
- Added explicit regression coverage that current Garmin backup exports omit raw_diagnostics.
```

---

## 32.8 Phase 32 verification

Run:

```bash
python -m unittest discover -s tests
cd frontend
npm run typecheck
npm run build
cd ..
```

Manual checks:

```text
Create Dead Bug preset.
Create Cat-Cow preset.
Create Side Plank preset.
Start workout.
Add each exercise.
Verify Dead Bug/Cat-Cow show quantity only, no kg.
Verify Side Plank shows seconds only.
Finish workout.
Open History.
Open Edit Workout.
Open Exercise Stats for each.
Export backup.
Restore into empty DB.
Verify exercises and history survive.
```

Implementation status:

```text
Completed 2026-08-11:
- python3 -m unittest discover -s tests passed.
- frontend npm run typecheck passed.
- frontend npm run build passed.
- Manual browser checklist remains to be performed in the running app.
```

Suggested commit:

```text
Phase 32: support rehab exercise measurement and logging UX
```

---

# Phase 33 — Per-exercise back-pain response tracking

Status: Planned

## Goal

Let the app answer:

```text
Which exercises help my back pain?
Which exercises make it worse?
Which exercises are neutral?
```

Current session-level `lower_back_pain` is useful, but it does not tell whether a specific exercise helped or worsened.

---

## 33.1 Add workout exercise feedback tables

Migration:

```text
app/migrations/<next>_workout_exercise_feedback.py
```

Finished workout feedback table:

```sql
CREATE TABLE IF NOT EXISTS workout_exercise_feedback (
    workout_exercise_id INTEGER PRIMARY KEY,
    back_pain_before INTEGER CHECK(back_pain_before BETWEEN 0 AND 10),
    back_pain_after INTEGER CHECK(back_pain_after BETWEEN 0 AND 10),
    response TEXT CHECK(response IN ('helped', 'same', 'worse', 'unknown')),
    notes TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(workout_exercise_id) REFERENCES workout_exercises(id) ON DELETE CASCADE
);
```

Active draft feedback table:

```sql
CREATE TABLE IF NOT EXISTS active_draft_exercise_feedback (
    draft_exercise_id INTEGER PRIMARY KEY,
    back_pain_before INTEGER CHECK(back_pain_before BETWEEN 0 AND 10),
    back_pain_after INTEGER CHECK(back_pain_after BETWEEN 0 AND 10),
    response TEXT CHECK(response IN ('helped', 'same', 'worse', 'unknown')),
    notes TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(draft_exercise_id) REFERENCES active_draft_exercises(id) ON DELETE CASCADE
);
```

When finishing workout, copy active draft feedback to finished workout feedback.

Acceptance criteria:

```text
Migration is idempotent.
Draft feedback is cleared with active draft.
Finished workout feedback cascades with workout exercise delete.
Existing DB upgrades safely.
```

Implementation status:

```text
Completed 2026-08-11:
- Added v012 workout_exercise_feedback migration for finished workout and active draft feedback tables.
- Registered migration in the runner and verified fresh/legacy DBs record schema version 12.
- Finalizing an active draft now copies active draft exercise feedback to finished workout exercise feedback.
- Added migration and draft repository tests for idempotency, cascade deletes, draft clearing, and finalize copy.
```

---

## 33.2 Backend schemas and APIs

Add schemas:

```python
class ExerciseFeedbackUpdate(AppBaseModel):
    back_pain_before: int | None = Field(default=None, ge=0, le=10)
    back_pain_after: int | None = Field(default=None, ge=0, le=10)
    response: str | None = Field(default=None, pattern="^(helped|same|worse|unknown)$")
    notes: str | None = Field(default=None, max_length=1000)

class ExerciseFeedbackResponse(AppBaseModel):
    back_pain_before: int | None
    back_pain_after: int | None
    response: str
    notes: str | None
    updated_at: str | None
```

Add optional `feedback` field to:

```text
CurrentWorkoutExerciseResponse
WorkoutExerciseResponse
```

Current workout endpoint:

```text
PATCH /api/v1/current-workout/exercises/{draft_exercise_id}/feedback
```

Finished workout endpoint:

```text
PATCH /api/v1/workouts/{workout_id}/exercises/{workout_exercise_id}/feedback
```

Response derivation:

```python
if response is omitted and before/after exist:
    after < before  -> helped
    after > before  -> worse
    after == before -> same
else:
    unknown
```

Tests:

```python
def test_patch_current_exercise_feedback_records_before_after()
def test_patch_current_exercise_feedback_derives_helped()
def test_patch_current_exercise_feedback_derives_worse()
def test_patch_current_exercise_feedback_rejects_invalid_response()
def test_finish_workout_copies_draft_feedback()
def test_patch_finished_workout_exercise_feedback()
def test_feedback_deleted_when_workout_exercise_deleted()
```

Implementation status:

```text
Completed 2026-08-11:
- Added exercise feedback request/response schemas and optional feedback fields on current and finished workout exercises.
- Added PATCH APIs for active draft exercise feedback and finished workout exercise feedback.
- Added response derivation for helped/same/worse/unknown, with partial PATCH updates preserving omitted values.
- Regenerated OpenAPI and generated frontend API types, and synced local frontend response types.
- Added backend API tests for current feedback updates, response derivation, invalid response validation, finalize copy, finished workout feedback updates, and cascade delete behavior.
```

---

## 33.3 Frontend feedback UI

Show expanded feedback UI by default only for these profile keys:

```text
back_rehab
core_stability
mobility
```

For normal strength exercises, keep feedback optional/collapsed.

Current Workout behavior:

```text
Back response
Before: 0..10
After: 0..10
Response: Helped / Same / Worse / Unknown
Notes
Saving / Saved / Error
```

Edit Workout behavior:

Preferred:

```text
Feedback changes are part of page-level unsaved changes and saved by the one Save workout button.
```

Active Workout behavior:

```text
Feedback auto-saves.
```

Acceptance criteria:

```text
In active workout, Dead Bug shows Back response.
User can record before=3, after=2, response=helped.
Saving state is visible.
After finishing workout, feedback appears in History/Edit.
Normal strength exercises are not cluttered.
```

Implementation status:

```text
Completed 2026-08-11:
- Added a reusable exercise feedback editor with before/after scores, derived response, notes, and save status display.
- Active workout exercise feedback now auto-saves through the current-workout feedback API.
- History edit exercise feedback is stored in the page draft and saved through the existing Save workout action.
- Back rehab, core stability, and mobility exercises show feedback expanded by default; other profiles stay collapsed unless feedback exists.
- Added frontend API wrappers and local types for current and finished exercise feedback updates.
```

---

## 33.4 Back rehab stats

Add to Stats response:

```python
back_rehab: {
    "window_days": 30,
    "session_count": int,
    "exercise_count": int,
    "total_sets": int,
    "total_quantity": int,
    "feedback_count": int,
    "average_before_pain": float | None,
    "average_after_pain": float | None,
    "average_pain_delta": float | None,
    "helped_count": int,
    "same_count": int,
    "worse_count": int,
    "top_helpful_exercises": [
        {
            "exercise_id": int,
            "exercise_name": str,
            "feedback_count": int,
            "average_delta": float,
            "helped_count": int,
            "worse_count": int,
        }
    ],
}
```

Pain delta convention:

```text
after - before
negative = improved/helped
positive = worsened
```

Stats card:

```text
Back rehab
7 sessions
Avg pain change: -1.2
Helped: 8 / Same: 3 / Worse: 1
Most helpful: Dead Bug, Cat-Cow
```

Acceptance criteria:

```text
Stats page can show whether rehab is helping.
Dead Bug/Cat-Cow feedback aggregates correctly.
No crash when no feedback exists.
```

---

## 33.5 Backup/restore feedback

If feedback tables are included in backup, increment backup schema version.

Export:

```text
workout_exercise_feedback
```

Do not export active draft feedback unless backup policy intentionally includes active drafts.

Tests:

```python
def test_backup_exports_workout_exercise_feedback()
def test_restore_imports_workout_exercise_feedback()
def test_old_backup_without_feedback_restores()
```

---

## 33.6 Phase 33 verification

Run:

```bash
python -m unittest discover -s tests
cd frontend
npm run typecheck
npm run build
cd ..
```

Manual:

```text
Create Dead Bug.
Start workout.
Add Dead Bug.
Add feedback before=3 after=2.
Finish workout.
Open History/Edit.
Feedback is present.
Open Stats.
Back rehab card shows helped/improvement.
Export and restore backup.
Feedback survives.
```

Suggested commit:

```text
Phase 33: add back-pain response tracking for rehab exercises
```

---

# Phase 34 — Previous plan carryover audit and polish

Status: Planned

## Goal

Verify and finish missed items from earlier plans and user-reported UI issues. This phase should not introduce large new features.

---

## 34.1 Restore and preserve Codex docs

Required structure:

```text
docs/CODEX_PLAN.md
docs/archive/
docs/codex-skills/
AGENTS.md
```

If old plans are recoverable, archive them:

```text
docs/archive/CODEX_PLAN_1.3.0_PHASES_23_29.md
docs/archive/CODEX_PLAN_STATS_UI_POLISH_1.3.1.md
```

Acceptance criteria:

```text
docs/CODEX_PLAN.md exists and contains current active roadmap.
docs/archive/ contains previous/completed plan summaries.
Codex skills remain in docs/codex-skills/.
AGENTS.md points to active plan and skills.
```

---

## 34.2 Settings foldable sections default folded

Check:

```text
frontend/src/pages/SettingsPage.tsx
frontend/src/components/settings/AnalysisProfilesPanel.tsx
```

No unwanted:

```tsx
<details open>
```

Acceptance:

```text
Settings page opens with foldable sections collapsed.
Collapsed rows still show useful summaries.
```

---

## 34.3 Garmin stats redundant Settings link removed

Check:

```text
frontend/src/pages/GarminStatsPage.tsx
```

Acceptance:

```text
Garmin stats top row shows range buttons and Sync button.
No duplicate inline Settings link.
Global Settings nav remains.
```

---

## 34.4 Current Workout first-exercise mobile scroll jump

Check:

```text
frontend/src/pages/CurrentWorkoutPage.tsx
frontend/src/components/LegacyActiveWorkoutView.tsx
```

If still present, preserve scroll around add-first-exercise:

```ts
const previousScrollY = window.scrollY;

if (document.activeElement instanceof HTMLElement) {
  document.activeElement.blur();
}

await addCurrentWorkoutExercise(...);

requestAnimationFrame(() => {
  window.scrollTo({ top: previousScrollY, behavior: "auto" });
});
```

Acceptance:

```text
Adding first exercise on 360-430px mobile viewport does not jump unexpectedly.
```

---

## 34.5 Active Workout RPE/back pain auto-save

Decision:

```text
No separate Save button in active workout Session stats.
RPE and Back pain auto-save.
Show Saved/Saving/Error.
```

Check:

```text
frontend/src/pages/CurrentWorkoutPage.tsx
app/routes/api_current_workout.py
```

Acceptance:

```text
Changing RPE auto-saves.
Changing Back pain auto-saves.
No extra Save button in session stats.
Clear status appears.
```

---

## 34.6 Active Workout should not create exercises inline

Decision:

```text
Active Workout only adds existing exercises.
Exercise creation/configuration belongs in Settings.
```

Check:

```text
frontend/src/pages/CurrentWorkoutPage.tsx
frontend/src/components/LegacyActiveWorkoutView.tsx
```

Acceptance:

```text
No inline new exercise creation on active workout.
Missing exercise helper links to Settings.
```

---

## 34.7 Top navigation keeps active page visible

Decision:

```text
Keep all top nav buttons visible.
Highlight active page.
Do not remove active page button.
```

Check:

```text
frontend/src/App.tsx
frontend/src/styles.css
```

Acceptance:

```text
Current | History | Stats | Garmin | Backup | Settings remain visible.
Active route is highlighted.
```

---

## 34.8 Edit Workout UX alignment

Required behavior:

```text
One page-level Save workout button.
No separate "Save workout info" button.
Consistent delete icon/button style.
Unsaved changes indicator appears.
Navigation/reload warning if unsaved changes would be lost.
```

Check:

```text
frontend/src/pages/HistoryPage.tsx
frontend/src/components/ExerciseCard.tsx
frontend/src/components/SetRow.tsx
```

Acceptance:

```text
Changing date/RPE/back pain/set/exercise marks dirty.
One Save persists all changes.
Dirty warning clears after save.
Delete controls are consistent.
```

---

## 34.9 Stats chart X-axis date formatting and mobile layout

Required:

```text
Desktop axis: 03 Jul
Mobile axis: 03.07
Tooltip: 03 Jul 2026
No raw ISO dates on axes.
```

Check:

```text
frontend/src/components/stats/StatsOverview.tsx
frontend/src/pages/StatsPage.tsx
frontend/src/pages/ExerciseStatsPage.tsx
```

Acceptance:

```text
All chart X-axis date formats are consistent.
No overlapping labels on 360px mobile.
```

---

## 34.10 Stats metric card and calculation UI polish

Check known fallback CSS:

```css
.metric-zone-info {
  left: 0;
  width: 100%;
  background: rgba(10, 132, 255, 0.45);
}
```

Acceptance:

```text
Default progress bar zone is visible.
Status labels show Good/Watch/Risk/Info/No data.
Training Load chart and Calculations do not duplicate full ATL/CTL/TSB rows.
```

---

## 34.11 Training load calculations audit

Required formulas:

```text
daily_load[date] = sum workout load_score for that local date
zero-load rest days are included
ATL = 7-day EWMA of daily load
CTL = 42-day EWMA of daily load
TSB = CTL - ATL
AC ratio = ATL / CTL if CTL > 0 else null
weekly_load = sum last 7 daily loads
monotony = mean(last 7 daily loads) / stddev(last 7 daily loads) if stddev > 0 else null
training_strain = weekly_load * monotony if monotony is not null
```

ATL percent:

```text
Use historical 95th percentile ATL as reference if enough data.
Fallback to max ATL if insufficient data.
Null if no data.
```

Tests:

```python
def test_training_load_includes_zero_load_days()
def test_atl_uses_7_day_ewma()
def test_ctl_uses_42_day_ewma()
def test_tsb_is_ctl_minus_atl()
def test_ac_ratio_null_when_ctl_zero()
def test_monotony_null_when_std_zero()
def test_training_strain_null_when_monotony_null()
def test_no_data_stats_does_not_crash()
```

---

## 34.12 Logs page access and safety check

Latest code appears to include LogPage / log service. Check:

```text
frontend/src/pages/LogPage.tsx
app/routes/api_logs.py
app/services/log_service.py
```

Acceptance:

```text
Logs page is intentionally linked or intentionally hidden.
Logs do not expose Garmin credentials/tokens/passwords.
Log API has sane limit caps.
Auto-refresh is not too aggressive.
Large exception logs do not break mobile layout.
```

---

## 34.13 CI/build status

Run:

```bash
python -m unittest discover -s tests
cd frontend
npm run typecheck
npm run build
cd ..
docker build -t training-log:dev .
```

Acceptance:

```text
Codex reports actual command output.
No assumed-passed verification.
```

Suggested commit:

```text
Phase 34: audit and finish previous UX and stats carryover items
```

---

# Phase 35 — Rehab exercise release verification

Status: Planned

## Goal

Prepare a clean release after Phases 32-34.

Recommended version:

```text
1.8.0 if Phase 33 feedback tracking is included
1.7.1 if only Phase 34 cleanup is included
```

Because Phase 32 and 33 are real product features, prefer:

```text
1.8.0
```

---

## 35.1 Version and changelog

Update only after verification passes:

```text
config.yaml
CHANGELOG.md
docs/CODEX_PLAN.md
```

Suggested changelog for 1.8.0:

```markdown
## 1.8.0 - YYYY-MM-DD

### Added
- Added clean support for rehab and mobility exercises such as Dead Bug, Cat-Cow, Bird Dog, Side Plank, and McGill Curl-up.
- Added `duration_only` exercise measurement type for time-based holds.
- Added built-in Back rehab, Core stability, and Mobility analysis profiles.
- Added measurement-aware exercise logging UI that hides kg controls for non-weighted exercises.
- Added per-exercise back-pain response tracking for rehab/mobility exercises.
- Added Back rehab stats showing pain response trends and most helpful exercises.

### Changed
- Improved Settings exercise creation for non-weighted and rehab exercises.
- Improved Current Workout and Edit Workout exercise cards to use measurement-specific labels.
- Improved Exercise Stats for reps-only and duration-only exercises.

### Fixed
- Fixed fake `0 kg` requirement for active non-weighted exercises.
- Fixed hardcoded Kg/Reps labels for non-weighted movements.
- Fixed remaining previous-plan UI carryover items.
```

If Phase 33 is not implemented, remove feedback/stat items and release as `1.7.1` or `1.8.0` depending on semantic preference.

---

## 35.2 Full verification

Run:

```bash
python -m unittest discover -s tests
cd frontend
npm run typecheck
npm run build
cd ..
docker build -t training-log:1.8.0 .
```

Manual smoke:

```text
Install/update add-on.
Open through Home Assistant ingress.
Refresh deep link.
Top navigation works.
Settings sections default collapsed.
Create Dead Bug from preset.
Create Cat-Cow from preset.
Create Side Plank from preset.
Start active workout.
Add Dead Bug.
Log 10 reps without kg field.
Add Side Plank.
Log 30 sec without kg field.
Add Deadlift.
Verify Deadlift still shows kg + reps.
Finish workout.
Open History.
Open Edit Workout.
Verify measurement-aware UI persists.
Open Exercise Stats for Dead Bug.
Verify reps chart.
Open Exercise Stats for Side Plank.
Verify duration chart.
Open Stats dashboard.
Verify training load and rehab stats.
Export backup.
Restore backup into empty DB.
Verify rehab exercises/history/feedback survive.
```

Acceptance:

```text
All tests pass.
Frontend typecheck/build pass.
Docker build passes.
Manual smoke passes.
config.yaml version is correct.
CHANGELOG contains release section.
docs/CODEX_PLAN.md marks completed phases.
```

Suggested commit:

```text
Phase 35: release rehab exercise tracking
```

---

# Suggested Codex prompts

## Implement Phase 32 only

```text
Read AGENTS.md.
Read docs/CODEX_PLAN.md.
Use:
- docs/codex-skills/skills/training-log-phase-executor/SKILL.md
- docs/codex-skills/skills/training-log-backend-api/SKILL.md
- docs/codex-skills/skills/training-log-frontend-ux/SKILL.md
- docs/codex-skills/skills/training-log-backup-restore/SKILL.md

Implement Phase 32 only: Rehab exercise measurement model and logging UX.

Important:
- Add duration_only measurement type.
- Let active non-weighted exercises exist without explicit weight options.
- Add built-in back_rehab, core_stability, and mobility profiles.
- Add Dead Bug, Cat-Cow, Bird Dog, McGill Curl-up, Side Plank, Pelvic Tilt, and Glute Bridge presets/inference.
- Make Settings creation and Current/Edit Workout UI measurement-aware.
- Do not implement Phase 33 feedback tracking.
- Do not bump config.yaml version.
- Do not remove existing backup compatibility.
- Preserve old workout measurement snapshots.

Run:
python -m unittest discover -s tests
cd frontend && npm run typecheck && npm run build

Return:
- changed files
- implemented behavior
- test/build results
- manual checks still needed
```

## Implement Phase 33 only

```text
Read AGENTS.md.
Read docs/CODEX_PLAN.md.
Use:
- docs/codex-skills/skills/training-log-phase-executor/SKILL.md
- docs/codex-skills/skills/training-log-backend-api/SKILL.md
- docs/codex-skills/skills/training-log-frontend-ux/SKILL.md
- docs/codex-skills/skills/training-log-stats-training-load/SKILL.md
- docs/codex-skills/skills/training-log-backup-restore/SKILL.md

Implement Phase 33 only: Per-exercise back-pain response tracking.

Important:
- Add draft and finished workout exercise feedback tables.
- Add APIs to save feedback for active draft exercises and finished workout exercises.
- Add optional feedback UI for rehab/mobility/core-stability exercises.
- Add Back rehab stats aggregation.
- Include backup/restore for finished workout feedback.
- Do not change Phase 32 measurement behavior unless needed for integration.
- Do not bump config.yaml version.

Run:
python -m unittest discover -s tests
cd frontend && npm run typecheck && npm run build

Return:
- changed files
- implemented behavior
- test/build results
- manual checks still needed
```

## Implement Phase 34 only

```text
Read AGENTS.md.
Read docs/CODEX_PLAN.md.
Use:
- docs/codex-skills/skills/training-log-phase-executor/SKILL.md
- docs/codex-skills/skills/training-log-code-reviewer/SKILL.md
- docs/codex-skills/skills/training-log-frontend-ux/SKILL.md
- docs/codex-skills/skills/training-log-stats-training-load/SKILL.md

Implement Phase 34 only: Previous plan carryover audit and polish.

Important:
- Do not add new product features.
- Restore/preserve docs/CODEX_PLAN.md and archive previous plan summaries.
- Verify/fix settings collapsed by default.
- Verify/fix Garmin redundant settings link.
- Verify/fix first exercise mobile scroll jump.
- Verify/fix active workout RPE/back pain auto-save.
- Verify no inline exercise creation on active workout.
- Verify top navigation keeps active page visible.
- Verify edit workout has one page-level save and unsaved changes.
- Verify stats X-axis formatting and mobile layout.
- Verify stats metric card/range bar polish including .metric-zone-info fallback.
- Verify training load formulas/tests.
- Verify logs page safety.
- Do not bump config.yaml version.

Run:
python -m unittest discover -s tests
cd frontend && npm run typecheck && npm run build

Return:
- checklist with pass/fix for every carryover item
- changed files
- test/build results
```

## Implement Phase 35 only

```text
Read AGENTS.md.
Read docs/CODEX_PLAN.md.
Use:
- docs/codex-skills/skills/training-log-release-verification/SKILL.md
- docs/codex-skills/skills/training-log-home-assistant-addon/SKILL.md
- docs/codex-skills/skills/training-log-code-reviewer/SKILL.md

Implement Phase 35 only: Rehab exercise release verification.

Important:
- Do not change runtime logic unless verification exposes a release blocker.
- Run full backend tests.
- Run frontend typecheck/build.
- Run Docker build.
- Update config.yaml version only after verification passes.
- Update CHANGELOG.md.
- Mark completed phases in docs/CODEX_PLAN.md.
- Report manual smoke checklist.

Target version:
- 1.8.0 if Phases 32 and 33 are included.
- 1.7.1 if only carryover cleanup is included.
```

---

# Current priority recommendation

Implement in this order:

```text
1. Phase 32 — mandatory foundation for clean rehab exercise logging.
2. Phase 34 — carryover audit/polish from previous plans.
3. Phase 33 — deeper per-exercise back-pain response tracking.
4. Phase 35 — release verification.
```

Fastest useful improvement:

```text
Do Phase 32 first.
```

That alone lets the user properly log Dead Bug, Cat-Cow, Side Plank, etc., without fake kg fields.

To answer the deeper question:

```text
Which exercises actually help my back pain?
```

do Phase 33 after Phase 32.
