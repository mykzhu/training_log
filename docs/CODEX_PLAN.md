# Training Log — Codex Plan

Repository: `mykzhu/training_log`  
Reviewed branch: `master`  
Reviewed head: `c1c83f2ce6aa0488fc15248f77c4080919d58f2e`  
Current add-on version: `1.0.1`  
Current backup schema: `3`

## Execution rule for Codex

1. Pull latest `master`.
2. Re-read this file and the changed code before editing.
3. Execute only the first unchecked phase.
4. Keep the branch focused.
5. Do not continue to later phases.
6. Update the completed phase to `[x]`.
7. Report changed files, tests, builds, manual checks, and known gaps.

## Hard constraints

- Preserve atomic workout finalization and empty-workout rejection.
- Preserve chronological/no-future analytics.
- Preserve backup restore compatibility for schema versions 1, 2, and 3.
- Preserve the 1.0.1 legacy-style active, read-only, and edit workout flows.
- Do not modify or commit runtime SQLite databases.
- Do not add multi-user support.
- Do not add Home Assistant route-prefix logic.
- Do not add Garmin scoring before Garmin observational import is validated.
- Do not introduce React Router, TanStack Query, formal migrations, or generated API types unless the current phase explicitly says so.
- Keep SQL in repositories.
- Keep calculations in backend services.
- Avoid unrelated UI redesign.

---

## [x] Phase 1 — Settings, draft, and backup consistency

Completed before the current review.

Key outcomes expected to remain true:

- SQLite is the authoritative active-draft state.
- Settings changes immediately affect active workout data.
- Exercise profiles are explicit and validated.
- Case-insensitive exercise names are rejected.
- Active exercises require configured weights.
- Backup schema 3 preserves exercise settings and weight options.

---

## [x] Phase 2 — CI and repository guardrails

Completed before the current review.

Key outcomes expected to remain true:

- GitHub Actions runs backend tests, frontend typecheck/build, and Docker build.
- Runtime database files are ignored and no longer tracked.
- Node 22 frontend build is used.
- README/changelog/release notes exist.

---

## [x] Phase 3 — SQLite and analytics performance

Completed before the current review.

Key outcomes expected to remain true:

- SQLite busy timeout, WAL, and indexes are present.
- Workout details can be batch-loaded.
- Recovery uses one 42-day query and partitions windows in Python.
- Chronological e1RM baselines are built in one pass.
- Query-count tests protect important paths.

---

## [x] Phase 4 — Recovery quality

Completed before the current review.

Key outcomes expected to remain true:

- Recommendation source honors `recovery_context["as_of"]`.
- Recovery windows expose coverage and active-week fields.
- Baseline confidence depends on history spread, not only count.
- Overall workout interval context exists.
- Short-gap readiness uses previous-session load/back stress.
- Long-layoff caps exist.
- Missing RPE/back feedback returns `needs_feedback`.
- Recommendations expose `suggested_sets` and `target_strategy`.
- UI displays actual suggested sets.

---

## [x] Phase 5 — Release 1.0.1 UI restoration

Completed before the current review.

Key outcomes expected to remain true:

- Add-on version is `1.0.1`.
- Changelog documents 1.0.0 and 1.0.1.
- Read-only workout detail flow exists.
- Legacy-style edit workout flow exists.
- Legacy-style active workout flow exists.
- Current workout supports inline exercise creation.
- History separates read-only and edit flows.
- Mobile layouts for active/history/edit/stats/backup are improved.

---

## [x] Phase 6 — 1.0.1 stabilization and plan cleanup

Branch:

```text
fix/1-0-1-stabilization
```

### Goal

Do not add a new feature yet. Stabilize the large 1.0.1 change set, update the plan so it no longer points to stale legacy release language, and add focused regression coverage around the new legacy-style React flows.

### Required plan cleanup

- Update `docs/CODEX_PLAN.md`:
  - current baseline should be `c1c83f2ce6aa0488fc15248f77c4080919d58f2e` or newer;
  - current add-on version should be `1.0.1`;
  - remove stale legacy release wording;
  - mark the completed recovery/release work accurately;
  - make this stabilization phase the first unchecked phase.
- Keep future phases ordered after this one.

### Backend/API regression checks

Add or strengthen tests for the APIs used by the new legacy-style React pages:

- read-only workout detail still returns workout metadata, exercises/sets, analysis, and recommendation when appropriate;
- edit workout flow can update metadata, add exercise, add/update/duplicate/delete set, delete workout exercise, and preserve ordering;
- active workout flow can create exercise inline, add it to active draft, mutate sets, finish only with at least one set, and reject inactive exercises for new additions unless already present;
- backup restore still works after 1.0.1 UI changes;
- recommendation `needs_feedback` has no exercise targets;
- `suggested_sets` remains consistent with the human-readable `target`.

### Frontend safety pass

Do not redesign UI. Only fix clear bugs.

Check and fix if needed:

- direct navigation to `/`, `/history`, `/workouts/{id}`, `/workouts/{id}/edit`, `/stats`, `/backup`, `/settings`;
- browser Back/Forward behavior;
- Home Assistant ingress navigation;
- mobile layout for active, read-only, edit, history, stats, and backup;
- loading/error/empty states for read-only and edit workout pages;
- no accidental navigation to `/exercises/{id}/stats` until that feature exists.

### Code hygiene

- Keep `StatsPage.tsx` behavior unchanged, but identify pure helper/component split points for a later phase.
- Do not extract the huge stats page in this phase unless required to fix a concrete bug.
- Do not change recommendation thresholds except to fix test-proven contradictions.
- Do not change backup schema.

### Required commands

```bash
python -m unittest discover -s tests
cd frontend
npm ci
npm run typecheck
npm run build
cd ..
docker build -t training-log:stabilization .
```

### Manual smoke matrix

```text
Home Assistant ingress
desktop browser
mobile browser width
active workout start/edit/finish
read-only workout detail
edit completed workout
history navigation
stats dashboard
backup export/restore validation screen
settings page
```

### Acceptance criteria

- The 1.0.1 UI flows are covered by backend/API tests where possible.
- Frontend typecheck/build passes.
- Docker build passes.
- No stale version or release target remains in the Codex plan.
- No new feature work is mixed in.
- The first unchecked phase after completion is Exercise-specific stats.

---

## [x] Phase 7 — Exercise-specific stats

Branch:

```text
feat/exercise-stats
```

### Goal

Implement the route that the app has been preparing for but does not yet have as a dedicated feature.

### Backend

Add:

```text
GET /api/v1/exercises/{exercise_id}/stats?limit=10|30|90|all
```

Response should include exercise identity, profile, active state, totals, best weight/reps/e1RM, latest result, chronological history, per-workout sets, PR flags, trend data, and source workout IDs.

Rules:

- inactive exercises retain historical stats;
- missing exercise returns 404;
- empty exercise history returns a stable empty response;
- no future-workout leakage in historical comparisons;
- reuse existing batch-loading/baseline helpers.

### Frontend

Add a dedicated exercise stats view:

```text
/exercises/{exerciseId}/stats
```

Show summary cards, history, trends, source workout links, inactive label, and 10/30/90/All selector. Avoid duplicating the whole global `StatsPage`.

### Tests

- active exercise with history;
- inactive exercise with history;
- exercise with no history;
- nonexistent exercise;
- PR markers;
- no future-data leakage;
- frontend typecheck/build.

---

## [x] Phase 8 — Formal migrations and typed API contracts

Branch:

```text
refactor/typed-api-and-migrations
```

### Formal migrations

Create:

```text
app/migrations/
  runner.py
  v001_initial.py
  v002_workout_metadata.py
  v003_active_draft.py
  v004_exercise_settings.py
  v005_performance_indexes.py
```

Add:

```sql
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
```

Rules:

- transaction per migration;
- record only after success;
- backup schema version remains separate;
- establish safe baseline for existing databases;
- preserve fresh database creation and existing production database startup.

### API contracts

Add Pydantic response models for exercises, exercise profiles, current workout, workout details, stats, recovery, recommendations, and backup responses. Use `response_model`.

Replace deprecated:

```python
payload.__fields_set__
```

with:

```python
payload.model_fields_set
```

Test omitted fields versus explicit `null`.

### TypeScript types

Generate TypeScript types from a checked-in OpenAPI schema. Do not require a running backend during normal frontend build.

### Cleanup

- Remove or redirect unused `/stats2` remnants if any remain.
- Remove unused server-generated chart payload only after confirming React has no consumer.

---

## [ ] Phase 9 — React routing and server-state management

Branch:

```text
refactor/react-router-query
```

### React Router

Replace manual `pushState`, `popstate`, and pathname parsing.

Routes:

```text
/                              CurrentWorkoutPage
/history                       HistoryPage
/workouts/:workoutId           ReadonlyWorkoutDetail
/workouts/:workoutId/edit      EditWorkout
/stats                         StatsPage
/exercises/:exerciseId/stats   ExerciseStatsPage
/settings                      SettingsPage
/backup                        BackupPage
*                              NotFoundPage
```

### TanStack Query

Suggested query keys:

```text
["current-workout"]
["exercises", includeInactive]
["exercise-profiles"]
["workouts", limit]
["workout", workoutId]
["stats", limit]
["exercise-stats", exerciseId, limit]
["backup"]
```

Rules:

- do not add Redux;
- migrate one page family at a time;
- preserve Home Assistant ingress behavior;
- preserve mobile navigation;
- keep mutation-specific pending state.

---

## [ ] Phase 10 — Stats page componentization

Branch:

```text
refactor/stats-page-components
```

### Goal

The stats page has grown large. Split it without changing behavior.

### Scope

Extract pure helpers/components for range selector, summary cards, trend charts, heatmaps, workload sections, normalized benchmark chart, strength-versus-workload, and empty/loading/error states.

Rules:

- no algorithm changes;
- no chart redesign;
- no new data endpoints;
- keep current API response shape;
- preserve mobile behavior.

---

## [x] Phase 11 — Garmin observational integration

Branch sequence:

```text
feat/garmin-adapter-spike
feat/garmin-persistence-api
feat/garmin-ui
```

### Adapter spike

- Add and verify `garminconnect==0.3.6`.
- Only `app/services/garmin_client.py` may import it.
- Verify Docker build, token storage, MFA, logout, timezone, and Fenix 7X payload shapes.
- Add sanitized fixtures.
- Do not commit identifying Garmin payloads.

### Persistence/API

Add `garmin_daily_metrics` storing only date, RHR, HRV, stress, Body Battery start/end, steps, synced timestamp, and sanitized raw diagnostics.

Rules:

- local Garmin calendar date, not UTC-converted date;
- default sync 35 days, allowed 1..90;
- partial failures preserve existing valid values;
- no empty row if every source fails;
- status/login/MFA/disconnect/sync/daily routes;
- no Garmin network calls from current-workout or recovery reads;
- tokens live under `/data/garmin_tokens`; credentials never persist;
- reset clears metrics but preserves tokens.

Backup:

- upgrade backup schema `3 -> 4`;
- restore versions 1, 2, 3, and 4;
- v3 restore preserves exercise settings exactly.

### UI

- Garmin section in Settings.
- Garmin Recovery card before Next Workout.
- Separate Garmin pending/error state.
- Sync refreshes Current Workout recovery only.
- Phase 1 is observational: no readiness score/status/target changes.

### Validation

Compare at least seven dates against Garmin Connect before starting scoring.

---

## [ ] Phase 12 — Garmin readiness adjustment

Branch:

```text
feat/garmin-readiness-adjustment
```

Rules:

- use 28 prior calendar days;
- median baseline;
- minimum 7 samples per metric;
- only fresh current-date data scores;
- current partial stress is display-only;
- previous-day completed stress can score;
- apply Garmin after existing gap/RPE/pain/load/back rules and before safety caps;
- clamp Garmin total to `+10/-20`; expose structured `garmin_adjustment`;
- do not pass Garmin metrics into exercise target logic;
- no-Garmin behavior remains unchanged.

---

## [ ] Phase 13 — Next release

Branch:

```text
chore/release-next
```

- Run full backend tests.
- Run frontend typecheck/build.
- Run Docker build.
- Browser smoke test.
- Home Assistant ingress smoke test.
- Update README/changelog/docs.
- Update add-on version according to actual delivered scope.
- Scan repository, fixtures, logs, DB exports, backups, and docs for secrets.
