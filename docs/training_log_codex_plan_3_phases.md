# Training Log Codex Roadmap - 3 Phases

Prepared for: `mykzhu/training_log`

Purpose: provide Codex with a precise, low-risk implementation roadmap that separates correctness fixes from UI work and analytics work.

Current product assumptions:

- Single dark theme only.
- Home Assistant add-on context must remain supported.
- `master` is the production branch.
- Current release baseline is `1.5.0`.
- The active Codex plan should live in `docs/CODEX_PLAN.md`.

## Phase overview

| Phase | Target version | Theme | Main goal | Risk level |
|---|---:|---|---|---|
| Phase 32 | 1.3.2 | Correctness patch | Fix real bugs without broad UI/API changes | Low |
| Phase 33 | 1.4.0 | Active workout UX | Make live workout logging faster and easier, especially on mobile | Medium |
| Phase 34 | 1.5.0 | Stats and visualization UX | Make analytics clearer, more actionable, and easier to interpret | Medium |

## Global Codex rules

Codex must follow these rules for all phases:

- Keep diffs focused.
- Do not mix bugfix and redesign work in the same release.
- Do not add light theme support.
- Do not add theme switching.
- Do not refactor chart colors into CSS variables.
- Do not change Home Assistant ingress behavior.
- Do not change database schema unless the phase explicitly requires it.
- Do not introduce unrelated formatting-only changes across large files.
- Run the verification commands listed in each phase.
- Update `config.yaml`, `CHANGELOG.md`, and `docs/CODEX_PLAN.md` at the end of each phase.

---

# Phase 32 - Correctness Patch 1.3.2

## Phase name

Phase 32: Correctness Patch 1.3.2

## Target release

Version: `1.3.2`

## Depends on

Base: latest `master` after `1.3.1`.

## Main objective

Fix small but real correctness bugs without starting another UI redesign or theme refactor.

This phase must be a focused bugfix release. Avoid broad frontend rewrites, API shape changes, styling refactors, and new feature work.

## Scope

Implement only these items:

1. Fix Stats sparkline parsing bug.
2. Fix current workout metadata partial update behavior.
3. Harden completed workout add-exercise and add-set numbering against duplicate position/set-number failures.
4. Renumber completed workout exercise positions after deleting an exercise.
5. Add focused tests for the above.
6. Bump release metadata to `1.3.2`.
7. Update changelog with the exact fixes.

## Explicit non-goals

Do not implement these in this phase:

- Do not change backend `build_sparkbar()` output.
- Do not change Stats API response shape.
- Do not replace sparkbar strings with typed arrays.
- Do not add a new chart data model.
- Do not refactor chart colors.
- Do not move hardcoded chart colors to CSS variables.
- Do not add light theme support.
- Do not add theme switching.
- Do not redesign `ActiveWorkoutPage`.
- Do not remove `LegacyActiveWorkoutView`.
- Do not change Home Assistant ingress logic.
- Do not change DB schema unless absolutely required.
- Do not introduce a new frontend test framework unless one is already configured.
- Do not perform unrelated formatting-only changes across large files.

Reason: this is a small correctness patch. Keep the diff easy to review.

## Files likely to change

```text
frontend/src/components/stats/StatsOverview.tsx
app/routes/api_current_workout.py
app/services/draft_service.py
app/repositories/drafts.py
app/repositories/workouts.py
tests/test_api_current_workout.py
tests/test_main_db_behavior.py
tests/test_draft_repository.py
tests/test_draft_service.py
config.yaml
CHANGELOG.md
docs/CODEX_PLAN.md
```

Only touch additional files when there is a clear technical need.

## Task 32.1 - Fix Stats sparkline parsing

### Problem

Backend `build_sparkbar()` emits these characters:

```python
SPARK_CHARS_INC = " ⢀⣀⣠⣤⣴⣶⣾⣿"
SPARK_CHARS_DEC = "⣿⣷⣶⣦⣤⣄⣀⡀ "
```

Frontend currently parses sparkbars using this unrelated character set:

```ts
"▁▂▃▄▅▆▇█"
```

Result: most backend sparkbar characters are unknown to the frontend parser, so mini trend lines become flat or misleading.

### Required approach

Keep backend unchanged.

Fix frontend parser only.

Do not change API shape.

Do not create typed series.

Do not touch `MetricSparkline` unless absolutely necessary.

### File

```text
frontend/src/components/stats/StatsOverview.tsx
```

### Implementation

Find the current helper:

```ts
function sparkbarToPoints(value: string | undefined): MetricSparklinePoint[] {
  ...
}
```

Replace it with a parser that understands the exact backend glyphs.

Use this implementation:

```ts
const SPARK_CHARS_INC = " ⢀⣀⣠⣤⣴⣶⣾⣿";
const SPARK_CHARS_DEC = "⣿⣷⣶⣦⣤⣄⣀⡀ ";

function sparkbarToPoints(value: string | undefined): MetricSparklinePoint[] {
  if (!value || value === "—") {
    return [];
  }

  return Array.from(value).map((char, index) => {
    const incIndex = SPARK_CHARS_INC.indexOf(char);

    if (incIndex >= 0) {
      return {
        date: String(index),
        value: incIndex + 1,
      };
    }

    const decIndex = SPARK_CHARS_DEC.indexOf(char);

    if (decIndex >= 0) {
      return {
        date: String(index),
        value: SPARK_CHARS_DEC.length - decIndex,
      };
    }

    if (char === "·") {
      return {
        date: String(index),
        value: 0,
      };
    }

    return {
      date: String(index),
      value: 1,
    };
  });
}
```

### Important details

Do not call `.trim()` on sparkbar strings.

The space character is meaningful because the backend uses space as the lowest bucket.

`Array.from(value)` is correct because these glyphs must be handled as user-visible characters.

The increasing set should map to:

```text
" " => 1
"⢀" => 2
"⣀" => 3
"⣠" => 4
"⣤" => 5
"⣴" => 6
"⣶" => 7
"⣾" => 8
"⣿" => 9
```

The decreasing set should map to:

```text
"⣿" => 9
"⣷" => 8
"⣶" => 7
"⣦" => 6
"⣤" => 5
"⣄" => 4
"⣀" => 3
"⡀" => 2
" " => 1
```

Note that some glyphs exist in both sets. That is acceptable because their visual magnitude is similar. Check the increasing set first.

### Manual frontend acceptance

On the Stats page:

- Metric cards should no longer show flat trend lines when sparkbar data exists.
- Increasing backend sparkbar strings should produce upward SVG sparkline trends.
- Decreasing backend sparkbar strings should produce downward SVG sparkline trends.
- Empty value or `"—"` should still show the empty state.

### Optional frontend test

If a frontend unit test framework already exists, add tests for:

```ts
expect(sparkbarToPoints(" ⢀⣀⣠⣤⣴⣶⣾⣿").map((p) => p.value))
  .toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9]);

expect(sparkbarToPoints("⣿⣷⣶⣦⣤⣄⣀⡀ ").map((p) => p.value))
  .toEqual([9, 8, 7, 6, 5, 4, 3, 2, 1]);

expect(sparkbarToPoints("—")).toEqual([]);
```

If no frontend test framework exists, do not add a framework just for this patch. Rely on `npm run typecheck`, `npm run build`, and manual visual verification.

## Task 32.2 - Fix current workout metadata partial update

### Problem

The completed workout update route already supports partial metadata update behavior using field-set detection.

The current workout metadata update route currently passes both fields:

```python
session_rpe=payload.session_rpe
lower_back_pain=payload.lower_back_pain
```

This means a PATCH payload containing only one field can accidentally clear the other field because omitted optional fields become `None`.

### Required behavior

PATCH must distinguish between:

1. Field omitted: leave unchanged.
2. Field present with value: update to value.
3. Field present with `null`: clear the field.
4. Empty object `{}`: no-op.

### File

```text
app/routes/api_current_workout.py
```

### Related files

```text
app/services/draft_service.py
app/repositories/drafts.py
tests/test_api_current_workout.py
tests/test_draft_service.py
tests/test_draft_repository.py
```

### Implementation design

Use `payload.model_fields_set` in the route, same concept as completed workout update.

Recommended route logic:

```python
updates: dict[str, int | None] = {}

if "session_rpe" in payload.model_fields_set:
    updates["session_rpe"] = payload.session_rpe

if "lower_back_pain" in payload.model_fields_set:
    updates["lower_back_pain"] = payload.lower_back_pain

if updates:
    draft_service.update_active_draft_metadata(updates)

return draft_service.get_current_workout()
```

Adapt naming to the existing service interface.

### Service/repository design

Prefer changing the service and repository metadata update methods to accept an explicit update dictionary:

```python
def update_active_draft_metadata(updates: dict[str, int | None]) -> None:
    ...
```

This avoids ambiguity between omitted fields and fields intentionally set to `None`.

Validate keys defensively:

```python
allowed = {"session_rpe", "lower_back_pain"}
unexpected = set(updates) - allowed
if unexpected:
    raise ValueError(...)
```

In the repository, build SQL dynamically only for provided keys.

Example SQL shape:

```python
columns = []
values = []

if "session_rpe" in updates:
    columns.append("session_rpe = ?")
    values.append(updates["session_rpe"])

if "lower_back_pain" in updates:
    columns.append("lower_back_pain = ?")
    values.append(updates["lower_back_pain"])

if not columns:
    return

values.append(draft_id)

conn.execute(
    f"""
    UPDATE active_draft_workouts
    SET {", ".join(columns)}
    WHERE id = ?
    """,
    values,
)
```

Use the actual table and column names already present in the repository.

### Edge cases to preserve

- No active workout should keep returning the existing current-workout response behavior.
- Validation ranges must remain:
  - `session_rpe`: 1-10 when present and not null.
  - `lower_back_pain`: 0-10 when present and not null.
- Clearing metadata with `null` must work.
- Omitting metadata must not clear it.

### Tests

Add or update tests in:

```text
tests/test_api_current_workout.py
```

Test cases:

#### Case 1 - session RPE only

1. Start current workout.
2. Set both metadata fields:
   - `session_rpe = 7`
   - `lower_back_pain = 3`
3. PATCH only:
   ```json
   {"session_rpe": 8}
   ```
4. Assert:
   - `session_rpe == 8`
   - `lower_back_pain == 3`

#### Case 2 - lower back pain only

1. Existing:
   - `session_rpe = 7`
   - `lower_back_pain = 3`
2. PATCH only:
   ```json
   {"lower_back_pain": 4}
   ```
3. Assert:
   - `session_rpe == 7`
   - `lower_back_pain == 4`

#### Case 3 - clear one field only

1. Existing:
   - `session_rpe = 7`
   - `lower_back_pain = 3`
2. PATCH:
   ```json
   {"session_rpe": null}
   ```
3. Assert:
   - `session_rpe is None`
   - `lower_back_pain == 3`

#### Case 4 - empty object no-op

1. Existing:
   - `session_rpe = 7`
   - `lower_back_pain = 3`
2. PATCH:
   ```json
   {}
   ```
3. Assert:
   - `session_rpe == 7`
   - `lower_back_pain == 3`

#### Case 5 - validation remains active

Invalid payloads must still fail:

```json
{"session_rpe": 11}
{"session_rpe": 0}
{"lower_back_pain": -1}
{"lower_back_pain": 11}
```

Expected: validation error.

## Task 32.3 - Harden add exercise / add set numbering

### Problem

Completed workout edit operations calculate next position/set number using:

```sql
MAX(position) + 1
MAX(set_number) + 1
```

The database also has unique indexes:

```text
(workout_id, position)
(workout_exercise_id, set_number)
```

In normal single-user usage this is usually fine, but quick repeated requests or duplicate browser actions can race:

1. Request A reads max position as `2`.
2. Request B reads max position as `2`.
3. Both try to insert position `3`.
4. One request fails with a unique constraint error.

### Required behavior

Completed workout editing should not produce unhandled 500 errors from position/set-number races.

Use transaction locking and/or bounded retry.

### Files

```text
app/repositories/workouts.py
app/routes/api_workouts.py
tests/test_main_db_behavior.py
```

### Preferred implementation

Use `BEGIN IMMEDIATE` around the read-max-and-insert sequence for these functions:

```python
add_workout_exercise(...)
add_set_to_workout_exercise(...)
```

This should acquire the SQLite write lock before calculating the next number, preventing two writers from calculating the same next value at the same time.

Current DB configuration already uses WAL and busy timeout, so this is compatible with the current SQLite setup.

### Recommended helper

Add a small local helper in `app/repositories/workouts.py` if it keeps the code clean:

```python
def _begin_immediate(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")
```

Use it only in operations that do read-max-then-insert numbering.

### Add exercise flow

Inside `add_workout_exercise(...)`:

1. Open connection.
2. Start immediate transaction.
3. Verify workout exists if this function currently does that.
4. Calculate:
   ```sql
   SELECT COALESCE(MAX(position), 0) + 1
   FROM workout_exercises
   WHERE workout_id = ?
   ```
5. Insert with that position.
6. Commit.
7. Return inserted row/model.

If an `sqlite3.IntegrityError` still occurs due to the unique position index, retry once or twice.

Recommended retry count:

```python
MAX_NUMBERING_RETRIES = 2
```

After retries are exhausted, raise a clean application-level error or return `None` so the route can respond with a controlled `409 Conflict`.

Avoid exposing raw SQLite error text in API response.

### Add set flow

Inside `add_set_to_workout_exercise(...)`:

1. Open connection.
2. Start immediate transaction.
3. Verify workout exercise exists if this function currently does that.
4. Calculate:
   ```sql
   SELECT COALESCE(MAX(set_number), 0) + 1
   FROM set_entries
   WHERE workout_exercise_id = ?
   ```
5. Insert with that set number.
6. Commit.
7. Return inserted row/model.

If `sqlite3.IntegrityError` occurs due to the unique set-number index, retry once or twice.

After retries are exhausted, return controlled failure.

### Route behavior

In `app/routes/api_workouts.py`, make sure failures are converted to predictable HTTP responses.

Recommended behavior:

- Missing workout: existing 404 behavior.
- Missing exercise: existing 404 behavior.
- Inactive exercise: existing 409 behavior.
- Numbering collision after retries: `409 Conflict` with a clear message:

```json
{"detail": "Could not assign a unique position. Please retry."}
```

Do not return 500 for expected unique collision failures.

### Do not over-engineer

- Do not create a global queue.
- Do not add async locks.
- Do not add a new DB table.
- Do not change unique indexes.
- Do not switch away from SQLite.
- Do not change active draft workout add-set behavior unless a test proves it is affected. Active draft operations already use in-process locking and are a different path.

### Tests

Add deterministic tests.

#### Add exercise after gap

1. Create workout.
2. Add three exercises.
3. Delete the middle exercise.
4. Add another exercise.
5. Assert positions are unique and sequential:

```text
1, 2, 3
```

This also depends on Task 32.4.

#### Add set after delete

If not already covered:

1. Create workout exercise.
2. Add three sets.
3. Delete set 2.
4. Add another set.
5. Assert set numbers are unique and sequential:

```text
1, 2, 3
```

#### Collision behavior

Avoid flaky thread-based tests unless the existing test suite already has a reliable pattern.

Preferred deterministic test options:

- Monkeypatch the repository insert to simulate one `sqlite3.IntegrityError`, then assert retry succeeds.
- Or add a small internal helper for retryable numbering operations and unit-test that helper.

Do not add fragile sleeps or timing-dependent concurrency tests.

## Task 32.4 - Renumber completed workout exercise positions after delete

### Problem

Set deletion already renumbers set numbers after a set is deleted.

Workout exercise deletion currently deletes the exercise but does not renumber remaining exercise positions.

This can leave gaps:

```text
1, 3, 4
```

Gaps are not necessarily fatal, but they make ordering less predictable and increase the chance of future numbering edge cases.

### Required behavior

After deleting a workout exercise, remaining exercises in that workout must be renumbered sequentially:

```text
1, 2, 3, ...
```

### File

```text
app/repositories/workouts.py
```

### Implementation

Update `delete_workout_exercise(...)`.

New conceptual flow:

1. Find the parent `workout_id` for the exercise being deleted.
2. Delete the exercise.
3. Renumber remaining exercises for that workout ordered by current position, id.
4. Commit.

Recommended SQL/logic:

```python
rows = conn.execute(
    """
    SELECT id
    FROM workout_exercises
    WHERE workout_id = ?
    ORDER BY position, id
    """,
    (workout_id,),
).fetchall()

for index, row in enumerate(rows, start=1):
    conn.execute(
        """
        UPDATE workout_exercises
        SET position = ?
        WHERE id = ?
        """,
        (index, row["id"]),
    )
```

Because of the unique index on `(workout_id, position)`, the most robust strategy is two-pass temporary negative positions:

```python
for index, row in enumerate(rows, start=1):
    conn.execute(
        "UPDATE workout_exercises SET position = ? WHERE id = ?",
        (-index, row["id"]),
    )

for index, row in enumerate(rows, start=1):
    conn.execute(
        "UPDATE workout_exercises SET position = ? WHERE id = ?",
        (index, row["id"]),
    )
```

This avoids unique-index collisions even in unusual ordering cases.

### Return behavior

Preserve existing route behavior.

If the workout exercise does not exist:

- Keep existing false/404 behavior.

If deletion succeeds:

- Return updated workout details as current route already does.

### Tests

Add or update tests in:

```text
tests/test_main_db_behavior.py
```

Test cases:

#### Delete middle exercise

1. Create completed workout.
2. Add three exercises.
3. Delete exercise at position 2.
4. Fetch workout details.
5. Assert remaining positions:

```text
1, 2
```

6. Assert exercise order is the previous first and previous third.

#### Delete first exercise

1. Create completed workout.
2. Add three exercises.
3. Delete exercise at position 1.
4. Assert remaining positions:

```text
1, 2
```

#### Delete last exercise

1. Create completed workout.
2. Add three exercises.
3. Delete exercise at position 3.
4. Assert remaining positions:

```text
1, 2
```

#### Add after delete

1. Create completed workout.
2. Add three exercises.
3. Delete one exercise.
4. Add another exercise.
5. Assert positions:

```text
1, 2, 3
```

6. Assert there are no duplicate positions.

## Phase 32 verification

### Backend tests

Run:

```bash
python -m unittest
```

All existing tests must pass.

### Frontend checks

Run:

```bash
cd frontend
npm run typecheck
npm run build
```

Do not skip frontend build because the sparkbar parser is TypeScript/React code.

### Manual checks

Stats page:

- Overview cards render.
- Sparkline lines are not flat when sparkbar values exist.
- No console errors.
- Empty sparkbar values still render empty state.

Current workout:

- Start a workout.
- Set both RPE and lower back pain.
- Update only RPE.
- Confirm lower back pain is preserved.
- Update only lower back pain.
- Confirm RPE is preserved.
- Clear RPE.
- Confirm lower back pain is preserved.
- Send empty metadata update if UI allows it.
- Confirm both values are preserved.

Completed workout editing:

- Open a completed workout.
- Add exercises.
- Delete middle exercise.
- Confirm visible order remains clean.
- Add another exercise.
- Confirm it appears at the end.
- Add sets.
- Delete middle set.
- Add another set.
- Confirm set numbering/order remains clean.

## Phase 32 release metadata

### config.yaml

Bump:

```yaml
version: "1.3.1"
```

to:

```yaml
version: "1.3.2"
```

Do not change unrelated add-on metadata.

### CHANGELOG.md

Add a new top entry:

```markdown
## 1.3.2

### Fixed

- Fixed Stats overview sparklines by parsing the exact glyph set emitted by the backend sparkbar builder.
- Fixed current workout metadata PATCH behavior so omitted fields no longer clear existing RPE or lower back pain values.
- Hardened completed workout exercise and set numbering against duplicate position/set-number collisions.
- Renumbered completed workout exercise positions after deleting an exercise to keep ordering sequential.
```

## Phase 32 acceptance criteria

The phase is complete only when all conditions below are true.

Functional acceptance:

- Stats overview sparklines correctly reflect backend sparkbar strings.
- Current workout metadata PATCH no longer clears omitted fields.
- Explicit `null` still clears metadata fields.
- Empty metadata PATCH is a no-op.
- Deleting a completed workout exercise leaves sequential positions.
- Adding an exercise after delete uses the next correct position.
- Adding a set after delete uses the next correct set number.
- Duplicate position/set-number races do not produce raw 500 errors.

Technical acceptance:

- Backend tests pass: `python -m unittest`.
- Frontend typecheck passes: `cd frontend && npm run typecheck`.
- Frontend build passes: `cd frontend && npm run build`.
- `config.yaml` version is `1.3.2`.
- `CHANGELOG.md` has a `1.3.2` entry.
- No broad UI redesign was included.
- No chart theme/color refactor was included.
- No backend sparkbar API change was included.

## Phase 32 suggested commit and PR

Suggested commit message:

```text
Phase 32: fix stats sparklines and workout metadata
```

Suggested PR title:

```text
Phase 32: Correctness patch 1.3.2
```

Suggested PR description:

```markdown
## Summary

This PR ships a focused 1.3.2 correctness patch.

Fixed:
- Stats overview sparkline parsing now matches the backend sparkbar glyphs.
- Current workout metadata PATCH now preserves omitted fields.
- Completed workout exercise positions are renumbered after delete.
- Completed workout add-exercise/add-set numbering is hardened against duplicate position/set-number collisions.

Intentionally skipped:
- No backend sparkbar API change.
- No typed sparkline series migration.
- No chart color/theme refactor.
- No Active Workout UI redesign.

## Verification

- [ ] python -m unittest
- [ ] cd frontend && npm run typecheck
- [ ] cd frontend && npm run build
- [ ] Manual Stats page sparkline check
- [ ] Manual current workout metadata PATCH check
- [ ] Manual completed workout delete/add ordering check
```

Status: completed on 2026-07-06.

Implementation notes:

- Fixed Stats sparkbar parsing to use the backend `build_sparkbar()` glyph sets without trimming meaningful spaces.
- Changed current workout metadata PATCH handling to update only fields present in the request body; explicit `null` still clears a field and `{}` is a no-op.
- Hardened completed workout add-exercise and add-set numbering with `BEGIN IMMEDIATE`, bounded retry, and controlled `409 Conflict` route responses for numbering collisions.
- Renumbered completed workout exercise positions after deleting an exercise using a two-pass temporary negative-position update.
- Added focused tests for metadata partial updates, validation, exercise position renumbering, add-after-delete numbering, set add-after-delete numbering, and conflict response handling.
- Bumped `config.yaml` to `1.3.2` and added the `1.3.2` changelog entry.
- Verification passed with `python3 -m unittest discover -s tests`, `npm run typecheck`, and `npm run build`.
- `python3 -m unittest` ran zero tests in this repository, so discovery was used for the backend suite.

---

# Phase 33 - Active Workout UX Upgrade 1.4.0

## Phase name

Phase 33: Active Workout UX Upgrade 1.4.0

## Target release

Version: `1.4.0`

## Depends on

Phase 32 / `1.3.2` must be completed first.

Do not start this phase until the correctness patch is merged and verified.

## Main objective

Make the app feel better and faster during real training.

This phase focuses on the live workout flow: starting a workout, adding exercises, logging sets, editing recent sets, and finishing safely.

This is a UI/UX phase, not a backend correctness patch.

## Product goal

The active workout screen should answer these questions quickly:

```text
What am I doing now?
What did I just log?
What should I log next?
Can I finish safely?
```

## Scope

Implement these UI improvements:

1. Redesign Active Workout screen into a practical training cockpit.
2. Improve set logging speed and touch ergonomics.
3. Improve exercise cards and workout structure.
4. Add faster set actions: `+ Same`, `+ Previous`, `+ Warm-up`, `Delete last`.
5. Add mobile bottom action bar.
6. Improve exercise picker.
7. Improve workout finish confirmation and post-finish summary.
8. Improve active workout loading/error/empty states.
9. Add frontend safety checks where reasonable.
10. Keep the existing dark visual direction.

## Explicit non-goals

Do not implement these in this phase:

- Do not redesign the full Stats dashboard. That is Phase 34.
- Do not add light theme support.
- Do not add theme switching.
- Do not refactor chart colors into CSS variables.
- Do not change backend sparkbar output.
- Do not change Stats API shape.
- Do not add Garmin sync changes.
- Do not add new training science formulas.
- Do not change DB schema unless required for a specific active workout UI feature.
- Do not break Home Assistant ingress.
- Do not remove existing features without replacement.

Reason: this phase should improve the core workout logging experience without becoming a broad analytics rewrite.

## Files likely to change

Expected frontend files:

```text
frontend/src/pages/CurrentWorkoutPage.tsx
frontend/src/components/current-workout/*
frontend/src/components/layout/*
frontend/src/api/client.ts
frontend/src/styles/*
```

Possible backend files only if needed:

```text
app/routes/api_current_workout.py
app/schemas.py
```

Release/docs:

```text
config.yaml
CHANGELOG.md
docs/CODEX_PLAN.md
README.md
```

Only touch backend files if UI needs a small additional field that cannot be safely derived on frontend.

## UX principle

The active workout screen is the daily driver. Optimize for real training conditions:

- Sweaty hands.
- Small mobile screen.
- User is tired.
- User wants to log quickly.
- User does not want to think about app mechanics.

Every primary action should be reachable and understandable.

## Task 33.1 - Redesign Active Workout screen shell

### Problem

The current Active Workout screen still uses legacy UI structure. It works, but it is not optimized for fast logging during training.

During a workout the user needs large controls, fast set entry, minimal scrolling, and clear context.

### Goal

Create an Active Workout training cockpit.

The screen should feel like the main daily-use surface of the app.

### Required layout

Add a sticky header at the top of the active workout screen.

It should show:

```text
Active Workout
Elapsed time
Total volume
Total sets
Exercise count
Current recovery / readiness hint if available
Finish button
```

Recommended desktop visual structure:

```text
[Active Workout]                          [Finish]
42 min                                    6,420 kg · 18 sets · 5 exercises
Recovery: Balanced                       Back pain risk: Low
```

Recommended mobile compact structure:

```text
42 min · 18 sets · 6.4t
[Finish]
```

### Requirements

- Header remains visible while scrolling.
- Header must not cover content.
- On mobile, keep it compact.
- On desktop, allow richer summary.
- Finish button must be visible but not dangerously easy to tap by accident.

## Task 33.2 - Finish confirmation

### Problem

Finishing a workout is a destructive transition from active draft to completed workout. It should be safe.

### Required behavior

If workout has logged sets, ask for confirmation.

Confirmation text:

```text
Finish this workout?
You logged 18 sets across 5 exercises.
```

Actions:

```text
Cancel
Finish workout
```

If workout has no sets, keep existing empty workout behavior.

### Safety requirements

- Disable Finish while request is pending.
- Prevent double-submit.
- Show error if finish fails.
- Keep current draft intact if finish fails.

## Task 33.3 - Improve exercise cards

### Problem

Exercise cards need to be faster to read and easier to operate.

### Required exercise card structure

Each exercise card should show:

```text
Exercise name
Exercise category / movement type if available
Last used weight hint
Previous best / recent working weight if available
Set table or mobile set rows
Fast action buttons
```

Recommended layout:

```text
Goblet Squat
Lower body · Last: 24 kg x 10

Set   Weight   Reps   Done
1     20 kg    10     ✓
2     24 kg    8      ✓
3     [24]     [8]    Save

[+ Same] [+ Previous] [+ Warm-up] [Delete last]
```

### Required actions per exercise

Each exercise card should support:

```text
+ Same
+ Previous
+ Warm-up
Delete last set
Collapse / expand exercise
```

### + Same behavior

Adds a new set using the previous set from the same exercise in the current workout.

Example:

```text
Previous current set: 24 kg x 8
+ Same creates: 24 kg x 8
```

If current exercise has no set, use previous workout value if already available. If no value exists, create empty editable set.

### + Previous behavior

Adds a set using the latest known previous workout value for this exercise.

Example:

```text
Last workout: 22 kg x 10
+ Previous creates: 22 kg x 10
```

If previous workout data is missing, create empty editable set and show a small hint:

```text
No previous set found yet.
```

### + Warm-up behavior

Adds a lighter set.

Simple frontend rule is acceptable:

```text
warmup_weight = round(main_weight * 0.6)
warmup_reps = 8
```

If no weight is known, create empty editable set.

### Delete last behavior

Deletes the last set in that exercise.

This action should be easier than opening a menu but should ask for confirmation if the set has non-empty weight/reps.

## Task 33.4 - Improve set rows

### Problem

Set editing should be easy on mobile.

Inputs must be large enough and should not cause accidental mistakes.

### Required set row improvements

Each set row should include:

```text
Set number
Weight input
Reps input
Estimated volume
Save/update status
Delete action
```

### Mobile requirements

On mobile:

- Inputs must be large touch targets.
- Numeric keyboard should open for weight and reps.
- Buttons must be comfortable finger size.
- Avoid tiny inline icons as the only action.
- Avoid horizontal overflow where possible.
- If a table does not fit, use stacked rows instead of a cramped table.

Recommended mobile row:

```text
Set 3
[Weight kg] [Reps]
Volume: 240 kg
[Save] [Delete]
```

### Desktop requirements

On desktop:

- Dense table layout is acceptable.
- Use clear columns.
- Keep actions aligned.

## Task 33.5 - Add mobile bottom action bar

### Goal

Make common actions reachable with one thumb.

On mobile active workout screen, add a bottom sticky action bar:

```text
[+ Exercise] [+ Set] [Finish]
```

### Behavior

- `+ Exercise` opens exercise picker.
- `+ Set` adds a set to the currently focused or last exercise.
- `Finish` opens finish confirmation.

### Requirements

- Do not show this bar on desktop unless it looks natural.
- Bottom bar must not cover important content.
- Add bottom padding to scroll area if needed.
- Use safe-area padding if appropriate.

## Task 33.6 - Improve exercise picker

### Problem

Adding an exercise should be faster.

### Required picker improvements

Exercise picker should support:

```text
Search
Recent exercises
Favorites or frequently used exercises if already derivable
Category grouping
Inactive exercise protection
```

Suggested layout:

```text
Search exercises...

Recent
- Goblet Squat
- Bench Press
- Suitcase Carry

Core
- Crunch
- Dead Bug

Lower Body
- Goblet Squat
- Split Squat
```

### Important constraints

Do not add a new favorites DB feature in this phase unless it is already supported.

A frontend-only recent exercises list derived from workout history is enough.

Inactive exercises should not be easy to add accidentally.

## Task 33.7 - Improve workout summary after finish

### Goal

After finishing a workout, show a useful summary instead of only returning to history.

Summary should include:

```text
Duration
Total sets
Total volume
Exercises trained
Session RPE
Lower back pain
Estimated load
PRs or improvements if already available
Back stress warning if relevant
```

Recommended summary card:

```text
Workout Complete

52 min
22 sets
8.4 t total volume

Highlights
- Bench Press: best estimated 1RM in last 30 days
- Suitcase Carry: volume up 18%
- Back pain stayed low
```

Actions:

```text
View workout
Start another
Go to Stats
```

If this is too large, implement as a completed workout detail improvement instead of a separate finish modal.

## Task 33.8 - Improve active workout empty/loading/error states

### Required states

The Active Workout page should have:

```text
Loading state
No active workout state
Active workout state
Mutation pending state
Error state
```

### Error state example

```text
Could not update set.
Your workout is still saved. Try again.

[Retry]
```

Do not show raw stack traces.

## Task 33.9 - Mobile UX requirements

On small screens:

- One-column layout.
- Large buttons.
- No cramped set tables.
- Avoid tiny tap targets.
- Keep primary action visible.
- Do not require horizontal scrolling for normal workout logging.
- Bottom action bar must not cover controls.

Test browser widths:

```text
360px
390px
430px
768px
```

## Task 33.10 - Accessibility basics

Implement basic accessibility improvements:

```text
Buttons have readable labels
Icon-only buttons have aria-label
Inputs have labels
Form errors are visible
Touch targets are large enough
Keyboard navigation is not broken
Color is not the only signal
```

Do not over-engineer accessibility in this phase, but avoid obvious issues.

## Task 33.11 - Frontend safety

### Optimistic updates

Use optimistic updates only where safe.

Good candidates:

```text
Adding a set
Updating a set
Deleting latest set
```

If optimistic update fails:

- Roll back or refetch.
- Show clear error.
- Do not leave UI inconsistent.

### Request locking

Avoid duplicate mutations caused by double clicks.

For critical actions:

```text
Finish workout
Delete exercise
Delete set
Cancel workout
```

Disable button while request is pending.

## Phase 33 verification

### Frontend checks

Run:

```bash
cd frontend
npm run typecheck
npm run build
```

If frontend tests exist, run them.

Do not add a new test framework unless already present.

### Backend checks

If backend was touched, run:

```bash
python -m unittest
```

### Manual active workout check

Verify:

```text
Start workout
Add exercise
Add set
Edit set
Delete set
Add same set
Add previous set
Add warm-up set
Cancel finish confirmation
Finish after confirmation
```

### Manual mobile check

Use browser responsive mode.

Check:

```text
360px width
390px width
430px width
768px width
```

Verify:

```text
No broken layout
No unreadable set rows
Primary actions reachable
Sticky header does not cover content
Bottom action bar does not cover final controls
```

## Phase 33 release metadata

### config.yaml

Bump:

```yaml
version: "1.3.2"
```

to:

```yaml
version: "1.4.0"
```

### CHANGELOG.md

Add:

```markdown
## 1.4.0

### Improved

- Redesigned the active workout screen for faster set logging and better mobile use.
- Added clearer workout summary information while training.
- Improved exercise cards, set rows, and common workout actions.
- Improved active workout mobile layout and touch ergonomics.
- Improved workout finish confirmation and post-workout summary.

### Notes

- This release keeps the single dark theme.
- No light theme or theme switching was added.
- Stats dashboard redesign is planned separately for 1.5.0.
```

## Phase 33 acceptance criteria

Active Workout UX:

- Active workout page has a clearer cockpit-style layout.
- Current workout summary is visible while training.
- Add set is faster than before.
- Set inputs are mobile-friendly.
- Common actions are easy to reach on mobile.
- Finish workout has safe confirmation.
- Double-clicking critical actions does not create obvious duplicate/broken state.

Technical acceptance:

- Frontend typecheck passes.
- Frontend build passes.
- Backend tests pass if backend was touched.
- No theme system was added.
- No light mode was added.
- No chart color refactor was added.
- No broad Stats redesign was included.
- Home Assistant ingress still works.
- Version bumped to `1.4.0`.
- Changelog updated.

## Phase 33 suggested commit and PR

Suggested commit message:

```text
Phase 33: improve active workout UX
```

Suggested PR title:

```text
Phase 33: Active Workout UX upgrade
```

Suggested PR description:

```markdown
## Summary

This PR improves the main live workout logging experience.

Included:
- Redesigned Active Workout screen for faster real-world logging.
- Improved exercise cards and set row ergonomics.
- Added fast set actions: + Same, + Previous, + Warm-up, Delete last.
- Added better mobile layout and common action access.
- Improved finish confirmation and workout summary.

Intentionally not included:
- No light theme.
- No theme switcher.
- No chart color/theme refactor.
- No Stats dashboard redesign.
- No backend sparkbar API changes.

## Verification

- [ ] cd frontend && npm run typecheck
- [ ] cd frontend && npm run build
- [ ] python -m unittest, if backend touched
- [ ] Manual active workout logging check
- [ ] Manual mobile layout check
```

---

# Phase 34 - Stats and Data Visualization UX 1.5.0

## Phase name

Phase 34: Stats and Data Visualization UX 1.5.0

## Target release

Version: `1.5.0`

## Depends on

Phase 32 / `1.3.2` and Phase 33 / `1.4.0` must be completed first.

Do not start this phase until the active workout UI upgrade is merged and verified.

Implementation note: Phase 33 was reverted after user review, and Phase 34 was
implemented directly from the restored `1.3.2` baseline by explicit user
direction. This phase intentionally does not include an Active Workout redesign.

## Main objective

Make analytics easier to understand and more useful for training decisions.

The Stats page should not just show charts. It should help the user understand what changed, what is improving, what might need attention, and what data is missing.

## Product goal

The Stats dashboard should answer these questions quickly:

```text
Am I training consistently?
Is my strength improving?
Is my workload increasing too quickly?
Does lower-back pain correlate with training load?
Which exercises are progressing or missing?
What should I pay attention to next?
```

## Scope

Implement these UI and visualization improvements:

1. Improve Stats dashboard hierarchy.
2. Add "What changed?" insight cards.
3. Improve volume trend chart.
4. Improve strength progression chart.
5. Add or improve weekly workload heatmap.
6. Improve back pain vs load scatter chart.
7. Make training load metrics understandable.
8. Improve completed workout review analytics if needed.
9. Improve empty/loading/error states for analytics.
10. Improve mobile layout for Stats.

## Explicit non-goals

Do not implement these in this phase:

- Do not add light theme support.
- Do not add theme switching.
- Do not refactor chart colors into CSS variables.
- Do not change chart colors just for architecture purity.
- Do not change backend sparkbar output.
- Do not replace sparkbar strings with typed series unless required by a specific new visualization.
- Do not add complex medical claims.
- Do not add Garmin sync changes.
- Do not change training formulas unless there is a clear bug.
- Do not add AI-generated advice.
- Do not add DB schema changes unless clearly needed.
- Do not redesign the active workout screen again.

Reason: this phase should improve analytics UX, not create a theme system or rewrite the app architecture.

## Files likely to change

Expected frontend files:

```text
frontend/src/pages/StatsPage.tsx
frontend/src/components/stats/*
frontend/src/styles/*
```

Possible backend files if new derived values are needed:

```text
app/routes/api_stats.py
app/services/stats_service.py
app/schemas.py
tests/test_main_db_behavior.py
```

Release/docs:

```text
config.yaml
CHANGELOG.md
docs/CODEX_PLAN.md
README.md
```

## UX principle

Stats should be interpreted, not just displayed.

Good analytics UI uses:

- Plain labels.
- Clear hierarchy.
- Helpful empty states.
- Tooltips that explain values.
- Visualizations that answer a specific question.
- Cautious language when interpreting pain/recovery data.

Avoid making the dashboard feel like a wall of charts.

## Task 34.1 - Improve Stats dashboard hierarchy

### Problem

Stats page can become visually noisy.

The dashboard should show the most important information first.

### Required structure

Stats page should be organized as:

```text
1. Health / readiness overview
2. Training load overview
3. Strength progress
4. Volume and consistency
5. Back pain / risk
6. Detailed charts
```

### Top dashboard section

Top section should show 4-5 key cards:

```text
Recovery status
7-day load
Strength trend
Back pain risk
Consistency
```

Each card should include:

```text
Main value
Short label
Tiny trend visualization
Plain-language interpretation
```

Example:

```text
Back Pain Risk
Low
Average 1.2 / 10 over recent sessions
```

Avoid raw unexplained abbreviations in top cards.

## Task 34.2 - Add "What changed?" insight cards

### Goal

Make stats actionable, not just visual.

Add an insight section near the top:

```text
What changed recently?
```

Possible insights:

```text
Volume increased 18% vs previous period.
Back pain stayed low despite higher load.
Bench Press estimated strength is trending up.
Consistency dropped this week.
No lower-back pain data logged recently.
```

### Rules

Use only data already available from the current stats response where possible.

Do not invent medical advice.

Do not overstate conclusions.

Use cautious language:

```text
may suggest
looks like
based on logged workouts
```

Avoid:

```text
you are overtraining
this will prevent injury
your recovery is bad
```

### Insight priority

Show only the most useful 3-5 insights.

Avoid showing ten low-value messages.

Insight cards should be dismissible only if persistence already exists. Otherwise keep them simple and non-dismissible.

## Task 34.3 - Improve volume trend chart

### Goal

Show workload progression clearly.

The chart should show:

```text
Total volume over time
Optional moving average if already easy
Clear tooltip with date and volume
```

Tooltip should say:

```text
Date
Total volume
Exercises / sets if available
```

### Requirements

- Use clear axis labels.
- Format large volume values compactly.
- Avoid unexplained abbreviations.
- Empty state should explain how to generate data.

Empty state:

```text
No volume trend yet.
Complete at least two workouts to see how your training volume changes over time.
```

## Task 34.4 - Improve strength progression chart

### Goal

Make strength progress obvious for a selected exercise.

Should show:

```text
Estimated 1RM
Best set weight
Reps
PR markers
```

If e1RM is already available, use it.

If not enough data:

```text
Not enough strength data yet.
Log at least 2 completed workouts with this exercise.
```

### Required interactions

- Exercise selector.
- Time range selector using existing Stats limit mechanism if available.
- Tooltip with date, weight, reps, e1RM.
- PR marker if data already supports it.

### Do not do

- Do not introduce complex strength formulas unless already used in backend.
- Do not compare unrelated exercises on one chart by default.
- Do not overstate tiny e1RM changes as meaningful progress.

## Task 34.5 - Add or improve weekly workload heatmap

### Goal

Show training consistency by exercise and week.

Rows:

```text
Exercises
```

Columns:

```text
Weeks
```

Cell value:

```text
Volume or set count
```

Purpose:

```text
Show which exercises are trained consistently and which are missing.
```

### Preferred behavior

- Default to top exercises by recent volume or frequency.
- Keep rows limited to avoid a huge wall.
- Provide tooltip per cell:

```text
Week
Exercise
Sets
Volume
```

### Mobile behavior

On mobile, allow horizontal scroll for the heatmap if needed.

Do not compress it until unreadable.

### If too large for Phase 34

If implementation is too risky, leave heatmap as a planned item and instead improve the existing weekly workload chart.

## Task 34.6 - Improve back pain vs load scatter

### Goal

Help identify whether higher workload correlates with higher logged lower-back pain.

### Chart design

X-axis:

```text
Workout load or volume
```

Y-axis:

```text
Lower back pain
```

Each point:

```text
One workout
```

Tooltip:

```text
Date
Workout name
Volume/load
Lower back pain
Session RPE
```

Chart title:

```text
Training load vs lower-back pain
```

Subtitle:

```text
Each point is one completed workout with logged lower-back pain.
```

### Important language

Do not claim causation.

Use wording like:

```text
This can help you notice patterns between workload and logged pain.
```

Avoid wording like:

```text
This shows which workouts caused pain.
```

## Task 34.7 - Make training load metrics understandable

### Problem

ATL/CTL/TSB style metrics are useful but not obvious.

### Required labels

If ATL/CTL/TSB is displayed, use plain labels first:

```text
Short-term load
Long-term load
Freshness
```

Optional technical labels can appear second:

```text
Short-term load (ATL)
Long-term load (CTL)
Freshness (TSB)
```

### Required explanation

Add a short explanation:

```text
Short-term load reacts quickly to recent workouts.
Long-term load changes more slowly.
Freshness compares recent load with your baseline.
```

### Avoid duplication

Do not show duplicate cards/charts for the same ATL/CTL/TSB numbers.

If the same values appear in both top cards and detailed chart, top cards should summarize and detailed chart should explain trends.

## Task 34.8 - Improve completed workout analytics

### Goal

Completed workout review should help the user understand the session.

Show:

```text
Workout date
Duration
Session RPE
Lower back pain
Total volume
Exercise list
Set table
PRs/highlights
Notes if available
```

Exercise sections should show:

```text
Exercise name
Total volume for this exercise
Best set
Estimated 1RM if relevant
Previous comparison if available
```

Example:

```text
Bench Press
Total: 2,420 kg
Best: 70 kg x 6
Estimated 1RM: 84 kg
```

This can be implemented in Phase 34 if Phase 33 did not already complete it.

## Task 34.9 - Improve analytics empty states

### Goal

Empty states should guide the user.

Examples:

### No stats yet

```text
No stats yet

Complete your first workout to see volume, strength, consistency, and recovery trends.
```

Action:

```text
Start workout
```

### No exercise trend yet

```text
Not enough data for this exercise

Log this exercise in at least two completed workouts to see a trend.
```

### No lower-back pain data

```text
No lower-back pain data

Add a quick 0-10 lower-back pain score after workouts to track how training affects your back.
```

Keep language calm and non-medical.

## Task 34.10 - Loading and error states

### Goal

Avoid blank screens.

Every major Stats section should have:

```text
Loading state
Error state
Empty state
Success state
```

Error state should include:

```text
What failed
Retry button
Short technical detail if useful
```

Example:

```text
Could not load stats.
Check that the add-on is running and try again.

[Retry]
```

Do not expose long stack traces in UI.

## Task 34.11 - Mobile Stats UX

On small screens:

- One-column layout.
- Clear section headings.
- No cramped chart legends.
- Tooltips must be readable.
- Charts may scroll horizontally only when needed.
- Top cards should be stacked or 2-column depending on available width.
- Avoid tiny tap targets.

Test browser widths:

```text
360px
390px
430px
768px
```

## Task 34.12 - Visualization quality checklist

Every chart should have:

- Clear title.
- Clear subtitle or explanation when needed.
- Axis labels where useful.
- Tooltip with real values.
- Empty state.
- Mobile behavior.
- No unexplained abbreviations in the primary UI.
- No claims stronger than the data supports.

## Phase 34 verification

Implementation status:

- Added Stats "What changed?" insight cards using existing stats response data.
- Improved the volume trend tooltip with date, total volume, sets, and reps.
- Added a load vs lower-back pain scatter chart with non-causal wording.
- Updated training-load labels to show Short-term load, Long-term load, and Freshness before ATL/CTL/TSB terminology.
- Improved the no-stats empty state and mobile behavior for the new analytics sections.
- Did not change backend formulas, backend APIs, Garmin sync, theme behavior, or Active Workout UI.

### Frontend checks

Run:

```bash
cd frontend
npm run typecheck
npm run build
```

If frontend tests exist, run them.

### Backend checks

If backend was touched, run:

```bash
python -m unittest
```

### Manual Stats check

Verify:

```text
Stats overview loads
Insight cards make sense
Top cards are understandable
Volume chart renders with real data
Strength chart renders with selected exercise
Training load explanation is readable
Back pain scatter does not claim causation
Empty states work with no data
Tooltips are readable
Mobile Stats page is usable
```

### Manual mobile check

Use browser responsive mode.

Check:

```text
360px width
390px width
430px width
768px width
```

Verify:

```text
No broken layout
No unreadable chart sections
Cards do not overflow
Tooltips are usable
Charts do not destroy layout
```

## Phase 34 release metadata

### config.yaml

Bump:

```yaml
version: "1.4.0"
```

to:

```yaml
version: "1.5.0"
```

### CHANGELOG.md

Add:

```markdown
## 1.5.0

### Improved

- Reorganized the Stats dashboard around readiness, load, strength, consistency, and back-pain context.
- Added recent-change insight cards to make training trends easier to understand.
- Improved volume, strength, workload, and back-pain visualizations with clearer labels and tooltips.
- Improved explanations for training load metrics such as short-term load, long-term load, and freshness.
- Improved analytics empty states, loading states, error states, and mobile layout.

### Notes

- This release keeps the single dark theme.
- No light theme or theme switching was added.
- Chart color/theme refactor remains intentionally out of scope.
```

## Phase 34 acceptance criteria

Stats UX:

- Stats page has clearer section hierarchy.
- Top cards explain what matters.
- Insight cards summarize meaningful recent changes.
- Charts have understandable labels and tooltips.
- Empty states explain what data is missing.
- Mobile Stats layout remains usable.
- Back pain charts use cautious non-medical language.

Technical acceptance:

- Frontend typecheck passes.
- Frontend build passes.
- Backend tests pass if backend was touched.
- No theme system was added.
- No light mode was added.
- No chart color refactor was added.
- No active workout redesign was included.
- Home Assistant ingress still works.
- Version bumped to `1.5.0`.
- Changelog updated.

## Phase 34 suggested commit and PR

Suggested commit message:

```text
Phase 34: improve stats and visualization UX
```

Suggested PR title:

```text
Phase 34: Stats and data visualization UX upgrade
```

Suggested PR description:

```markdown
## Summary

This PR improves the Stats dashboard and data visualization experience.

Included:
- Clearer Stats dashboard hierarchy.
- Recent-change insight cards.
- Better volume, strength, workload, and back-pain visualizations.
- Clearer training load labels and explanations.
- Better analytics empty/loading/error states.
- Better mobile Stats layout.

Intentionally not included:
- No light theme.
- No theme switcher.
- No chart color/theme refactor.
- No Active Workout UI redesign.
- No backend sparkbar API changes.

## Verification

- [ ] cd frontend && npm run typecheck
- [ ] cd frontend && npm run build
- [ ] python -m unittest, if backend touched
- [ ] Manual Stats dashboard check
- [ ] Manual mobile Stats check
- [ ] Manual empty-state check
```

---

# Final roadmap checklist

## Phase 32 must finish before Phase 33

- [ ] `1.3.2` released.
- [ ] Sparkline parser fixed.
- [ ] Metadata PATCH fixed.
- [ ] Numbering/renumbering fixed.
- [ ] Tests pass.

## Phase 33 must finish before Phase 34

- [ ] `1.4.0` released.
- [ ] Active Workout UI improved.
- [ ] Mobile workout logging improved.
- [ ] Finish confirmation safe.
- [ ] Frontend build passes.

## Phase 34 final target

- [x] `1.5.0` release metadata updated.
- [x] Stats hierarchy improved.
- [x] Insight cards added.
- [x] Charts are clearer.
- [x] Analytics empty states improved.
- [x] Mobile Stats experience improved.

## Recommended order for Codex sessions

Use separate Codex sessions or PRs:

```text
Session 1: Phase 32 only
Session 2: Phase 33 only
Session 3: Phase 34 only
```

Do not ask Codex to implement all three phases in one PR. That would increase risk and make review harder.
