# Training Log — Duration-Only Manual Logging + Live Timer

Created: 2026-08-11
Current observed app version: 1.7.0

This is the active Codex roadmap for duration-only exercise logging polish.

Roadmap history before the short Phase 36 plan is archived at:

```text
docs/archive/CODEX_PLAN_REHAB_ROADMAP_PRE_PHASE36_2026-08-11.md
```

---

## Current Context

Latest master already contains the rehab foundation:

```text
duration_only measurement type
non-weighted active exercises without fake explicit weights
Back rehab / Core stability / Mobility profiles
Dead Bug / Cat-Cow / Bird Dog / Side Plank / McGill Curl-up presets
measurement-aware ExerciseCard and SetRow
per-exercise Back response editor
Back rehab stats card
```

The remaining gap for duration-only exercises was:

```text
1. Manual duration entry for sets already done.
2. Live local timer for sets performed in real time.
```

Duration-only sets continue to store seconds in:

```text
set_entries.reps
```

No backend schema change is required.

---

# Phase 36 — Duration-Only Manual Entry and Live Timer

## Status

```text
Completed 2026-08-11
```

## Goal

Improve `duration_only` exercise logging so exercises like Side Plank can be logged in two ways:

```text
1. Manual duration entry
   User enters values such as 30 sec, 0:30, 1:00, or 1:15.

2. Live timer
   User presses Start, performs the exercise, presses Stop & Add, and elapsed seconds are saved.
```

Examples:

```text
Side Plank
set 1: manual 30 sec -> reps = 30
set 2: timer 1:00    -> reps = 60
set 3: manual 1:15   -> reps = 75
summary: 3 sets · 2:45 total
```

## Implementation Status

Completed 2026-08-11:

```text
- Added duration formatting, parsing, and clamping helpers.
- Added manual duration input accepting 30, 30 sec, 0:30, 1:00, 1:15, 1m15s, and similar values.
- Added a local live timer with Start, Stop & Add, Reset, large display, nearest-second rounding, and minimum saved duration of 1 second.
- Integrated duration-only logging into ExerciseCard and the active workout exercise card.
- Kept kg controls hidden for duration_only exercises.
- Saved duration-only seconds into AddSetRequest.reps.
- Updated SetRow to display duration-only sets as 30 sec, 1:00, 1:15 and parse duration edits.
- Updated measurementUi summaries so duration totals read like 30 sec total or 2:45 total.
- Updated ExerciseStatsPage duration formatting for summary cards, best sets, latest values, set chips, and chart tooltips.
- Updated the Back rehab stats card to avoid labeling mixed duration/reps quantity as reps.
- Added responsive CSS for manual duration entry and timer controls.
```

## Verification

Completed 2026-08-11:

```text
cd frontend && npm run typecheck
cd frontend && npm run build
```

Backend tests were not run for Phase 36 because no backend, generated API, DB schema, or training-load files were changed.

## Manual Checks Still Needed

```text
Duration parser rejects invalid minute-second inputs such as 1:99, 1m99s, and 1 min 99 sec.
Side Plank manual 30 sec saves and displays 30 sec.
Side Plank manual 1:15 saves and displays 1:15.
Side Plank timer Stop & Add saves elapsed seconds.
Failed duration saves keep the typed manual value or running timer state and show an inline error.
Reset timer returns display to 0:00.
History/Edit still shows Side Plank duration rows readably.
Exercise Stats for Side Plank shows duration instead of kg.
Dead Bug still logs reps only.
Deadlift still logs kg + reps.
```

Suggested commit:

```text
Phase 36: add duration-only manual entry and live timer
```

---

# Phase 37 — Optional Duration/Laterality Polish

## Status

```text
Future / optional
```

## Notes

Avoid overcomplicating Phase 36. If unilateral side tracking becomes necessary, prefer explicit exercise names first:

```text
Side Plank Left
Side Plank Right
```

Do not add a side/laterality field unless the user explicitly requests that later phase.

---

# Phase 38 — Release Verification for Duration Timer

## Status

```text
Planned after Phase 36
```

## Notes

Release verification should happen separately. Do not bump `config.yaml` or prepare release metadata as part of Phase 36.
