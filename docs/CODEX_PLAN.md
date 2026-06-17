# Training Log — Codex Plan

Repository: `mykzhu/training_log`
Verified baseline: `8696abe8e141cb06538018b273862271851530fc`
Current backup schema: `3`
Current add-on version: `0.2.0`

## Execution rule

1. Pull latest `master` and inspect current code/tests.
2. Execute **only the first unchecked phase** in this file.
3. Use a feature branch and small commits.
4. Do not continue to later phases.
5. Update the completed phase to `[x]`.
6. Report changed files, migrations, tests, builds, and remaining issues.

## Global constraints

- Preserve atomic workout finalization and empty-workout rejection.
- Preserve chronological ordering and no-future-data analytics.
- Preserve backup restore versions 1, 2, and 3.
- SQLite is authoritative.
- Keep API URLs stable unless explicitly listed.
- Keep calculations in backend services.
- Keep SQL in repositories.
- No multi-user work, timestamp migration, Home Assistant prefix, ML, or LLM.
- Do not modify or commit `data/training.db`.
- Do not add a frontend test framework unless a phase explicitly requests it.
- Avoid unrelated refactoring.

---

## [x] Phase 1 — Settings, draft, and backup consistency

Branch:

```text
fix/settings-and-draft-consistency
```

### Draft state

- Remove `ACTIVE_WORKOUT_DRAFT`.
- Keep `DRAFT_LOCK`.
- Load current draft from SQLite for every read/mutation.
- Replace whole-tree `replace_active_draft()` mutations with transactional repository operations:
  - update metadata;
  - insert/delete draft exercise;
  - insert/update/delete draft set;
  - renumber exercises/sets.
- Preserve IDs, API responses, restart persistence, and atomic Finish.
- Exercise rename/profile changes must appear immediately in Current Workout.
- Deactivating an exercise already in the draft must not remove it.

### Exercise profiles

- Define one authoritative supported profile-key set from analysis profiles.
- Make create `profile_key` optional; infer from normalized name when omitted.
- Reject unknown keys with HTTP 400.
- Add:

```text
GET /api/v1/exercise-profiles
```

- Add a friendly Analysis type selector in Settings for create/update.
- Rename must not change the stored profile.
- Profile update must refresh Current Workout metrics.

### Exercise names

- Enforce case-insensitive uniqueness.
- Detect existing case-only conflicts before adding a unique NOCASE index.
- Create/rename conflicts return HTTP 409.
- Allow capitalization-only update of the same row.

### Weight safety

- Active create with no weights: reject.
- Activate exercise with no weights: reject with HTTP 409.
- Replace weights with `[]` for an active exercise: reject with HTTP 409.
- Inactive exercise may have no weights.
- `0` is valid.
- Add Initial weight to the create form.
- Do not alter historical/current set values.

### Settings UI

- Preserve unsaved name/weight/profile drafts during reorder, or block reorder while dirty.
- Add dirty tracking.
- Replace global `pending` with action/exercise-specific pending state.
- Hide raw `profile_key` and `sort_order`.
- Add friendly profile labels, retry/empty states, forms, Enter submit, and remove-weight aria labels.
- Group active/inactive exercises if this does not complicate ordering.

### Backup/migration

- Legacy v1/v2 restore: merge profile defaults with historical unusual weights using `INSERT OR IGNORE`.
- Schema v3 restore: preserve exact configured settings/weights.
- Validate before deleting current data:
  - unique IDs and foreign keys;
  - normalized case-insensitive unique names;
  - valid active/order/profile values;
  - finite non-negative weights;
  - unique `(exercise_id, weight)`;
  - valid workout/set references and basic value ranges.
- Reset seeds profile defaults.
- Keep backup schema at `3`.

### Required tests

- stale draft after rename/profile update;
- draft survives service reload;
- existing inactive draft exercise remains;
- targeted mutation and atomic Finish regressions;
- profile inference/validation/update;
- case-only duplicate create/rename;
- active empty-weight rejection and zero acceptance;
- reorder does not lose drafts;
- exact schema-v3 round trip;
- explicit v2 restore;
- legacy defaults plus unusual historical weights;
- migration idempotency;
- invalid backup validation occurs before destructive restore.

### Verify

```bash
python -m unittest discover -s tests
cd frontend
npm ci
npm run typecheck
npm run build
cd ..
docker build -t training-log:phase1 .
```

---

## [x] Phase 2 — CI and repository guardrails

Branch:

```text
chore/ci-repository-guardrails
```

- Add `.github/workflows/ci.yml`:
  - Python 3.12 tests;
  - `npm ci`;
  - typecheck;
  - frontend build;
  - Docker build.
- Stop tracking runtime SQLite DB.
- Ensure `.gitignore` covers DB/WAL/SHM/token files.
- Update Docker frontend stage to Node 22 LTS.
- Add concise README development/test/Docker/Home Assistant instructions.
- Add `Unreleased` changelog section.
- Do not bump release version yet.

Verify the same full test/build commands.

---

## [ ] Phase 3 — SQLite and analytics performance

Branch:

```text
perf/batch-analytics-and-sqlite
```

- Add busy timeout, WAL, and synchronous NORMAL.
- Normalize data, then add indexes for:
  - workouts `(created_at, id)`;
  - workout exercises by workout/position and exercise/workout;
  - sets by exercise/set number;
  - active draft positions/set numbers.
- Add unique position/set-number indexes where safe.
- Implement:

```python
get_workout_details_batch(workout_ids)
```

- Batch-load configured weights.
- Use batch loading in history, stats, recovery, and recommendations.
- Calculate chronological e1RM baselines in one pass.
- Query 42-day recovery history once; calculate each workout once; partition windows in Python.
- Add query-count tests, not timing tests.
- Preserve all numeric/API behavior.

---

## [ ] Phase 4 — Recovery quality

Branch:

```text
feat/recovery-quality-pass
```

### Temporal correctness

- Recommendation source must use the same `recovery_context["as_of"]`.
- Ignore workouts at or after `as_of`.
- Calculate `recommendation_as_of` once.

### Baseline reliability

Add to recovery windows:

```text
first_workout_at
last_workout_at
coverage_days
active_week_count
avg_load_per_workout
avg_back_stress_per_workout
```

Confidence:

```text
high:   >=12 workouts, >=5 baseline workouts, >=5 active weeks, >=28 coverage days
medium: >=6 workouts,  >=3 baseline workouts, >=3 active weeks, >=14 coverage days
low:    otherwise
```

### Overall workout interval

Add median overall interval, sample count, confidence, ratio, and status.

Use personal interval when confidence is sufficient; retain fixed safety fallback.

### Readiness

- Use `last_load_metrics`.
- Short-gap penalty depends on previous-session load/back stress versus baseline.
- Apply only one time-gap penalty.
- Add long-layoff caps:
  - personal ratio `>2.5x`: maximum `repeat`;
  - low-confidence fallback `>10d`: maximum careful progress;
  - low-confidence fallback `>21d`: maximum repeat.
- Existing back-pain and `<24h` safety caps remain last.

### Recommendations

Add:

```text
suggested_sets
target_strategy
```

Rules:

- progress: add one rep to lowest-rep set;
- careful progress: add one rep to last set;
- repeat: copy set structure;
- deload: preserve set count/reps, reduce weight;
- reps-only: bounded total-rep increase.
- Keep existing `target` field.

Add exercise interval sample count/confidence. Add rolling three-session trend only after the above is stable.

### Tests

Cover future `as_of`, clustered/distributed history, personal interval, light/heavy previous session, long layoff, full-set targets, sparse interval confidence, and all existing safety regressions.

Verify full backend/typecheck/build/Docker.

---

## [ ] Phase 5 — Exercise-specific stats

Branch:

```text
feat/exercise-stats
```

Add:

```text
GET /api/v1/exercises/{exercise_id}/stats?limit=10|30|90|all
/exercises/:exerciseId/stats
```

Return/render:

- exercise/profile identity;
- totals;
- best weight/reps/e1RM;
- latest result;
- chronological per-workout history/sets;
- volume, e1RM, top-weight and same-weight-rep trends;
- PR markers;
- source workout links.

Inactive exercises retain stats. Missing exercise returns 404.

Fix the dashboard Workouts sparkbar: use weekly frequency or rename it to Load trend.

---

## [ ] Phase 6 — Formal migrations and typed API

Branch:

```text
refactor/typed-api-and-migrations
```

- Add formal ordered DB migrations with transaction-per-migration.
- Keep DB migration version separate from backup schema version.
- Establish safe baseline for existing databases.
- Add Pydantic response models for main APIs.
- Use `response_model`.
- Replace `__fields_set__` with `model_fields_set`.
- Test omitted versus explicit null.
- Generate TypeScript API types from a checked-in OpenAPI schema.
- Remove unused server chart payload/builders after confirming no consumers.
- Remove or redirect `/stats2`.

---

## [ ] Phase 7 — React routing and server state

Branch:

```text
refactor/react-router-query
```

- Add React Router routes for Current, History, Workout, Stats, Exercise Stats, Settings, Backup, Not Found.
- Add TanStack Query.
- Migrate one page family at a time.
- Use mutation-specific pending state.
- Do not add Redux.
- Preserve direct browser and Home Assistant ingress navigation.

---

## [ ] Phase 8 — Garmin observational integration

Branch sequence:

```text
feat/garmin-adapter-spike
feat/garmin-persistence-api
feat/garmin-ui
```

### Adapter spike

- Add and verify `garminconnect==0.3.6`.
- Only `garmin_client.py` imports it.
- Verify Docker, tokens, MFA resume, logout, timezone, and exact Fenix 7X payload fields.
- Add sanitized fixtures; no identifying payloads.

### Persistence/API

- Add timezone config `Europe/Uzhgorod`.
- Persist tokens under `/data/garmin_tokens`; never credentials.
- Add `garmin_daily_metrics`.
- Store only RHR, HRV, stress, Body Battery start/end, steps, synced timestamp, sanitized raw diagnostics.
- Manual sync: default 35 days, range 1..90.
- Partial failures preserve existing normalized values and existing raw source fragments.
- No empty row when all sources fail.
- Add status/login/MFA/disconnect/sync/daily APIs.
- All external calls stay in adapter/sync service.
- Current-workout/recovery reads are local-only.
- Upgrade backup schema `3 -> 4`; restore versions 1–4; v3 preserves Settings exactly.
- Reset clears metrics but preserves tokens.

### UI

- Add Garmin section to Settings.
- Add Garmin Recovery card before Next Workout.
- Separate Garmin pending/error state.
- Sync refreshes Current Workout recovery only.
- Missing/stale values display safely.
- Phase 1 must not change readiness score/status/reasons/targets.

### Validation

Compare at least seven dates with Garmin Connect before scoring.

Verify backend tests, typecheck, build, Docker, browser, and Home Assistant ingress.

---

## [ ] Phase 9 — Garmin readiness scoring

Branch:

```text
feat/garmin-readiness-adjustment
```

- Use 28 prior calendar days, median, minimum 7 samples per metric.
- Only fresh current-date data is eligible.
- Current partial stress is display-only; score previous completed stress.
- Apply Garmin after current gap/RPE/pain/load/back rules and before existing safety caps.
- Clamp Garmin total to `+10/-20`.
- Expose structured `garmin_adjustment`.
- Do not pass Garmin metrics into exercise target logic.
- No-Garmin/unavailable/stale behavior must remain byte-for-byte equivalent where practical.

---

## [ ] Phase 10 — Release

Branch:

```text
chore/release-0.3.0
```

- Run full tests, frontend checks, Docker build, browser smoke test, Home Assistant smoke test.
- Update README/changelog/docs.
- Document backup schema and Garmin token location.
- Bump add-on version from `0.2.0` according to actual delivered scope.
- Scan repository, fixtures, logs, DB exports, and backups for secrets.
