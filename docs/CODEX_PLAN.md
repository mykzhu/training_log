# Training Log — Codex Plan

Repository: `mykzhu/training_log`  
Reviewed branch: `master`  
Reviewed head: `40bc338ee4a5936ffb7b284443acae41e8da00d2`  
Reviewed head message: `Fixed garmin sync`  
Current add-on version: `1.0.1`  
Current backup schema: `4`  
Plan status: merged replacement for `docs/CODEX_PLAN.md` and `docs/CODEX_PLAN_UPDATED.md`

## Repository cleanup instruction

Keep one plan only:

```text
docs/CODEX_PLAN.md
```

After adding this merged plan, remove:

```text
docs/CODEX_PLAN_UPDATED.md
```

The previous two docs drifted apart. `CODEX_PLAN.md` marked exercise stats and typed API/migrations as complete, while `CODEX_PLAN_UPDATED.md` still showed them as unchecked. This merged file treats the latest code as source of truth.

---

## Execution rule for Codex

1. Pull latest `master`.
2. Re-read this file and the changed code before editing.
3. Execute only the first unchecked phase unless explicitly told otherwise.
4. Keep the branch focused.
5. Do not continue to later phases.
6. Update the completed phase to `[x]`.
7. Report changed files, tests, builds, manual checks, and known gaps.
8. Do not commit runtime databases, Garmin tokens, logs, private Garmin payloads, or local generated artifacts.

---

## Hard constraints

- Preserve atomic workout finalization and empty-workout rejection.
- Preserve chronological/no-future analytics.
- Preserve backup restore compatibility for schema versions `1`, `2`, `3`, and `4`.
- Preserve the `1.0.1` legacy-style active, read-only, and edit workout flows.
- Preserve current manual routing until the React Router phase.
- Do not add multi-user support.
- Do not add Home Assistant route-prefix logic unless explicitly required and tested in ingress.
- Do not introduce Redux.
- Do not add a new charting dependency; the frontend already uses Recharts.
- Keep SQL in repositories.
- Keep calculations in backend services.
- Keep Garmin network access out of read-only recovery/current-workout paths.
- Keep Garmin credentials out of SQLite, backup payloads, logs, frontend storage, and URL parameters.
- Do not expose Garmin `raw_diagnostics` on new chart/stats endpoints.
- Avoid unrelated UI redesign.

---

## Current architecture snapshot

### Backend

Important files:

```text
app/main.py
app/db.py
app/config.py
app/schemas.py

app/migrations/
  runner.py
  v001_initial.py
  v002_workout_metadata.py
  v003_active_draft.py
  v004_exercise_settings.py
  v005_performance_indexes.py
  v006_garmin_daily_metrics.py

app/repositories/
  exercises.py
  workouts.py
  drafts.py
  garmin.py

app/routes/
  api_backup.py
  api_current_workout.py
  api_exercises.py
  api_garmin.py
  api_stats.py
  api_workouts.py

app/services/
  analysis_service.py
  backup_service.py
  draft_service.py
  garmin_client.py
  garmin_readiness_service.py
  garmin_service.py
  recommendation_service.py
  recovery_service.py
  stats_service.py
```

Current registered routers include Garmin, exercise profiles, exercises, current workout, stats, workouts, workout item mutation, and backup.

Current database initialization runs formal migrations, seeds default exercises, initializes exercise settings, normalizes ordering columns, ensures case-insensitive exercise names, and creates performance indexes.

Current Garmin storage is migration `v006_garmin_daily_metrics`:

```sql
CREATE TABLE IF NOT EXISTS garmin_daily_metrics (
    date TEXT PRIMARY KEY,
    resting_heart_rate INTEGER,
    hrv_ms REAL,
    stress_avg INTEGER,
    body_battery_start INTEGER,
    body_battery_end INTEGER,
    steps INTEGER,
    synced_at TEXT NOT NULL,
    raw_diagnostics TEXT NOT NULL DEFAULT '{}'
);
```

Current backup schema is `4`. Garmin metrics are included in backup, while SQLite sequence reset intentionally applies only to the non-Garmin base tables.

### Frontend

Important files:

```text
frontend/src/App.tsx
frontend/src/api/client.ts
frontend/src/api/currentWorkout.ts
frontend/src/api/exercises.ts
frontend/src/api/garmin.ts
frontend/src/api/types.ts
frontend/src/pages/CurrentWorkoutPage.tsx
frontend/src/pages/ExerciseStatsPage.tsx
frontend/src/pages/HistoryPage.tsx
frontend/src/pages/SettingsPage.tsx
frontend/src/pages/StatsPage.tsx
frontend/src/styles.css
```

Current routing is manual `pushState` / `popstate` routing in `App.tsx`.

Current page set:

```text
/                              CurrentWorkoutPage
/history                       HistoryPage
/workouts/{id}                 read-only workout detail
/workouts/{id}/edit            edit workout
/stats                         StatsPage
/exercises/{exerciseId}/stats  ExerciseStatsPage
/backup                        BackupPage
/settings                      SettingsPage
```

Current frontend build commands:

```bash
cd frontend
npm run typecheck
npm run build
```

---

# Completed phases

## [x] Phase 1 — Settings, draft, and backup consistency

Completed before this merged plan.

Key outcomes expected to remain true:

- SQLite is the authoritative active-draft state.
- Settings changes immediately affect active workout data.
- Exercise profiles are explicit and validated.
- Case-insensitive exercise names are rejected.
- Active exercises require configured weights.
- Backup schema 3 preserves exercise settings and weight options.

---

## [x] Phase 2 — CI and repository guardrails

Completed before this merged plan.

Key outcomes expected to remain true:

- GitHub Actions runs backend tests, frontend typecheck/build, and Docker build.
- Runtime database files are ignored and no longer tracked.
- Node 22 frontend build is used.
- README/changelog/release notes exist.

---

## [x] Phase 3 — SQLite and analytics performance

Completed before this merged plan.

Key outcomes expected to remain true:

- SQLite busy timeout, WAL, and indexes are present.
- Workout details can be batch-loaded.
- Recovery uses one 42-day query and partitions windows in Python.
- Chronological e1RM baselines are built in one pass.
- Query-count tests protect important paths.

---

## [x] Phase 4 — Recovery quality

Completed before this merged plan.

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

Completed before this merged plan.

Key outcomes expected to remain true:

- Add-on version is `1.0.1`.
- Changelog documents `1.0.0` and `1.0.1`.
- Read-only workout detail flow exists.
- Legacy-style edit workout flow exists.
- Legacy-style active workout flow exists.
- Current workout supports inline exercise creation.
- History separates read-only and edit flows.
- Mobile layouts for active/history/edit/stats/backup are improved.

---

## [x] Phase 6 — 1.0.1 stabilization and plan cleanup

Completed before this merged plan.

Key outcomes expected to remain true:

- New legacy-style React flows have backend/API regression coverage where practical.
- Frontend typecheck/build passes.
- Docker build passes.
- No stale release target remains in the active plan.
- No new feature work was mixed into stabilization.

---

## [x] Phase 7 — Exercise-specific stats

Completed before this merged plan.

Current expected behavior:

```text
GET /api/v1/exercises/{exercise_id}/stats?limit=10|30|90|all
```

Expected response includes exercise identity, profile, active state, totals, best weight/reps/e1RM, latest result, chronological history, per-workout sets, PR flags, trend data, and source workout IDs.

Frontend route:

```text
/exercises/{exerciseId}/stats
```

Expected UI includes summary cards, history, trends, source workout links, inactive label, and 10/30/90/All selector.

Regression expectations:

- active exercise with history;
- inactive exercise with history;
- exercise with no history;
- nonexistent exercise;
- PR markers;
- no future-data leakage;
- frontend typecheck/build.

---

## [x] Phase 8 — Formal migrations and typed API contracts

Completed before this merged plan.

Expected state:

- Formal migration runner exists.
- `schema_migrations` exists.
- Fresh databases and existing production databases both start safely.
- Backup schema version remains separate from migration version.
- Pydantic response models are used on API routes where implemented.
- Deprecated `payload.__fields_set__` usage is replaced or wrapped through the project compatibility model.
- Omitted fields and explicit `null` are tested where relevant.
- OpenAPI schema is checked in under `docs/openapi.json`.

---

## [x] Phase 9 — Garmin observational integration

Completed before this merged plan.

Expected state:

- `garminconnect==0.3.6` is pinned.
- Only `app/services/garmin_client.py` imports the external Garmin package.
- Garmin Settings section exists.
- Garmin status/login/MFA/disconnect/sync/daily routes exist.
- Garmin metrics are stored in `garmin_daily_metrics`.
- Default sync is 35 days; allowed range is 1..90.
- Partial failures preserve existing valid values.
- No empty row is inserted when every source fails.
- Garmin credentials never persist.
- Tokens live under `/data/garmin_tokens`.
- Database reset clears Garmin metrics but preserves tokens.
- No Garmin network calls happen from current-workout or recovery reads.
- Backup schema is `4`.
- Restore versions `1`, `2`, `3`, and `4` work.
- Version 3 restore preserves exercise settings.

---

## [x] Phase 10 — Garmin readiness adjustment

Completed before this merged plan.

Expected state:

- Garmin readiness uses 28 prior calendar days.
- Baseline is median-based.
- Minimum is 7 samples per metric.
- Only fresh current-date RHR, HRV, and Body Battery start can score.
- Current-day stress is display-only.
- Previous-day completed stress can score.
- Garmin adjustment is applied after existing gap/RPE/pain/load/back rules and before safety caps.
- Garmin total is clamped to `+10/-20`.
- Structured `garmin_adjustment` is exposed in recommendation responses.
- Garmin metrics are not passed into exercise target logic.
- No-Garmin behavior remains unchanged.

---

## [x] Phase 11 — Garmin sync token persistence fix

Completed at reviewed head `40bc338ee4a5936ffb7b284443acae41e8da00d2`.

Expected state:

- `has_tokens()` checks for `/data/garmin_tokens/garmin_tokens.json` and falls back to nested token files.
- Token directory is created before Garmin login/tokenstore loading.
- Token persistence uses the internal Garmin auth client dump when available.
- Login raises an error if Garmin accepts credentials but token files are not written.
- Settings UI confirms connection from `/api/v1/garmin/status`, not just the login response.
- MFA success also refreshes status before showing “Garmin connected”.

Regression tests to add or keep:

- fake login that does not persist tokens must not return `connected: true`;
- status returns connected only after token files exist;
- UI message uses refreshed status.

---

# Future phases

## [ ] Phase 12 — Garmin stats charts page

Branch:

```text
feat/garmin-stats-page
```

### Goal

Add a separate page for synced Garmin daily metrics with charts and range controls.

This is a read-only analytics page over already-synced local Garmin data. It must not contact Garmin while rendering. Network access remains limited to explicit login/sync actions.

### Route and navigation

Add a top-level page:

```text
/garmin
```

Suggested tab label:

```text
Garmin
```

Current manual routing should be extended consistently with existing `App.tsx` route parsing. Do not introduce React Router in this phase.

After the later React Router phase, this page should become:

```text
/garmin                       GarminStatsPage
```

### Backend API

Keep the existing raw-ish endpoint for debugging/backward compatibility:

```text
GET /api/v1/garmin/daily?days=35
```

Add a chart-friendly endpoint that does not expose `raw_diagnostics`:

```text
GET /api/v1/garmin/stats?range=35|90|180|365|all
```

Suggested response:

```json
{
  "range": "90",
  "date_from": "2026-03-29",
  "date_to": "2026-06-26",
  "metric_count": 90,
  "coverage": {
    "expected_days": 90,
    "available_days": 88,
    "missing_days": 2
  },
  "latest_metric": {
    "date": "2026-06-26",
    "synced_at": "2026-06-26T20:30:00"
  },
  "series": [
    {
      "date": "2026-06-01",
      "resting_heart_rate": 60,
      "hrv_ms": 38.0,
      "stress_avg": 31,
      "body_battery_start": 72,
      "body_battery_end": 18,
      "steps": 8430
    }
  ],
  "baselines": {
    "resting_heart_rate": 59.0,
    "hrv_ms": 41.0,
    "stress_avg": 29.0,
    "steps": 7200.0
  }
}
```

Rules:

- return rows sorted ascending by date;
- accept only supported ranges;
- `all` returns all local rows, not remote Garmin data;
- never include `raw_diagnostics`;
- never contact Garmin;
- work when disconnected but historical rows exist;
- show empty stable response when there are no metrics;
- null metric values remain null and chart gaps are handled in the frontend.

### Backend implementation

Add to `app/repositories/garmin.py`:

```python
def list_daily_metrics_chronological(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    ...
```

Add to `app/services/garmin_service.py` or a new focused service:

```python
def stats(self, range_value: str = "90", *, today: date | None = None) -> dict[str, Any]:
    ...
```

Add route:

```text
GET /api/v1/garmin/stats
```

Add Pydantic response models in `app/schemas.py`.

### Frontend API and types

Add to `frontend/src/api/garmin.ts`:

```typescript
getGarminStats(range: "35" | "90" | "180" | "365" | "all")
```

Add types:

```typescript
export type GarminStatsRange = "35" | "90" | "180" | "365" | "all";

export type GarminStatsPoint = {
  date: string;
  resting_heart_rate: number | null;
  hrv_ms: number | null;
  stress_avg: number | null;
  body_battery_start: number | null;
  body_battery_end: number | null;
  steps: number | null;
};

export type GarminStatsResponse = {
  range: GarminStatsRange;
  date_from: string | null;
  date_to: string | null;
  metric_count: number;
  coverage: {
    expected_days: number | null;
    available_days: number;
    missing_days: number | null;
  };
  latest_metric: {
    date: string;
    synced_at: string;
  } | null;
  series: GarminStatsPoint[];
  baselines: {
    resting_heart_rate: number | null;
    hrv_ms: number | null;
    stress_avg: number | null;
    steps: number | null;
  };
};
```

### Frontend page

Create:

```text
frontend/src/pages/GarminStatsPage.tsx
```

Use existing Recharts dependency. Do not add a new chart library.

Suggested layout:

```text
Header:
  Garmin stats
  range selector: 35 / 90 / 180 / 365 / all
  Sync 35 days button
  link to Settings

Summary cards:
  latest date
  last sync
  available days
  missing days
  current HRV
  current resting HR
  current Body Battery

Charts:
  HRV over time with 28-day median/baseline
  Resting HR over time with 28-day median/baseline
  Body Battery start/end over time
  Stress average over time
  Steps over time
```

Chart rules:

- line charts for HRV, RHR, Body Battery, and stress;
- bar or line chart for steps;
- use concise date labels;
- show missing values as gaps, not zeros;
- mobile layout must stack charts cleanly;
- if fewer than 7 rows exist, show an explanatory empty/low-data state;
- Sync button must refresh only Garmin stats and status, not unrelated workout state;
- do not display `raw_diagnostics`.

### Tests

Backend tests:

- status with no Garmin rows;
- stats endpoint with no rows;
- 35/90/180/365/all ranges;
- chronological sorting;
- null values preserved;
- coverage counts;
- baselines with enough samples;
- baselines with insufficient samples;
- disconnected but local historical data exists;
- no `raw_diagnostics` in response;
- no Garmin client/network method called.

Frontend checks:

```bash
cd frontend
npm run typecheck
npm run build
```

Manual smoke:

```text
/garmin direct navigation
/garmin through Home Assistant ingress
desktop layout
mobile layout
range selector
sync button
empty state
partial-data state
disconnected-with-history state
```

Acceptance criteria:

- New Garmin page renders from local synced data.
- New endpoint never exposes raw diagnostics.
- Existing Settings Garmin panel still works.
- Existing Current page Garmin recovery still works.
- Existing readiness scoring is unchanged.
- Existing backup/export/restore behavior is unchanged.
- Frontend typecheck/build passes.
- Backend tests pass.

---

## [ ] Phase 13 — React routing and server-state management

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
/garmin                        GarminStatsPage
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
["garmin-status"]
["garmin-daily", days]
["garmin-stats", range]
["backup"]
```

Rules:

- do not add Redux;
- migrate one page family at a time;
- preserve Home Assistant ingress behavior;
- preserve mobile navigation;
- keep mutation-specific pending state;
- use explicit query invalidation after workout, exercise, backup, and Garmin mutations.

---

## [ ] Phase 14 — Stats page componentization

Branch:

```text
refactor/stats-page-components
```

### Goal

Split the large stats page without changing behavior.

### Scope

Extract pure helpers/components for:

- range selector;
- summary cards;
- trend charts;
- heatmaps;
- workload sections;
- normalized benchmark chart;
- strength-versus-workload;
- empty/loading/error states.

Rules:

- no algorithm changes;
- no chart redesign;
- no new data endpoints;
- keep current API response shape;
- preserve mobile behavior;
- do not mix global Stats refactor with Garmin Stats feature work unless the Garmin page phase explicitly extracted a reusable chart primitive.

---

## [ ] Phase 15 — Next release

Branch:

```text
chore/release-next
```

### Required checks

```bash
python -m unittest discover -s tests
cd frontend
npm ci
npm run typecheck
npm run build
cd ..
docker build -t training-log:release-candidate .
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
global stats dashboard
exercise stats page
Garmin Settings panel
Garmin Current page recovery
Garmin Stats page
backup export
backup restore validation screen
settings page
```

### Release tasks

- Update README.
- Update changelog.
- Update docs.
- Update add-on version according to actual delivered scope.
- Delete duplicate stale plan files.
- Confirm `docs/openapi.json` is current.
- Scan repository, fixtures, logs, DB exports, backups, and docs for secrets.
- Confirm no runtime SQLite database or Garmin token file is tracked.

---

## Always-run commands for feature branches

```bash
python -m unittest discover -s tests
cd frontend
npm ci
npm run typecheck
npm run build
cd ..
docker build -t training-log:local .
```

For documentation-only branches, run at least:

```bash
python -m unittest discover -s tests
cd frontend
npm run typecheck
npm run build
```

If dependencies changed, run `npm ci` and a Docker build.
