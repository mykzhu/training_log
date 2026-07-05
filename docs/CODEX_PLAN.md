# Training Log — CODEX_PLAN.md

**Base:** `master @ 965c7e7` — Release 1.2.0  
**Next planned version:** `1.3.0`  
**Phase numbering:** continue after Phase 22.

This plan contains the agreed issues/improvements #1–#10 and turns them into Codex-ready implementation phases.

---

## Scope

Implement the next UX and stats improvement batch:

1. Settings foldable sections collapsed by default.
2. Remove redundant Settings link from Garmin stats range row.
3. Fix mobile scroll jump when adding the first exercise to a new active workout.
4. Auto-save RPE and Back pain on active workout page; remove local Session stats Save button.
5. Remove inline new-exercise creation from active workout page; manage exercises in Settings only.
6. Keep active page visible in top navigation; only highlight active route.
7. Align Edit Workout page with Current Workout: one save button, unsaved changes notice, consistent delete controls.
8. Normalize date formatting for all Stats page date X-axes and improve small-screen chart labels.
9. Improve Stats metric cards with progress bars, range bars, sparklines, and a Calculations panel.
10. Add training-load calculations: ATL, CTL, TSB, AC ratio, monotony, training strain, ATL percent.

---

## Non-goals

- Do not add VO2max, Marathon Shape, race prediction, or other unsupported cardio-only metrics.
- Do not change Garmin auth/sync backend behavior except UI cleanup and using existing sync controls.
- Do not persist Settings accordion open/closed state in this version.
- Do not add new chart/UI dependencies unless existing tools cannot support the design.
- Do not remove the global Settings navigation item.
- Do not hide the current active nav item.
- Do not remove backend exercise creation endpoints; only remove inline creation from Active Workout UI.
- Do not make Edit Workout auto-save. Edit Workout should be batch-edit + one explicit save.

---

# Phase 23 — Navigation, Settings, Garmin stats polish, and carryover cleanup

## Purpose

Resolve small but visible UI issues before larger workout/stats work.

Covers:

- #1 Settings foldable sections collapsed by default.
- #2 Remove redundant Settings link from Garmin stats page.
- #6 Keep active page visible in top navigation.
- Carryover: restore safe `asyncio.to_thread` monkeypatch cleanup in tests.
- Carryover: keep `docs/CODEX_PLAN.md` in repo.

## Expected target files

```text
frontend/src/pages/SettingsPage.tsx
frontend/src/pages/GarminStatsPage.tsx
frontend/src/App.tsx
frontend/src/styles.css
tests/test_garmin_auto_sync.py
docs/CODEX_PLAN.md
CHANGELOG.md
```

## 23.1 Settings foldable sections collapsed by default

### Current problem

Settings foldable sections are expanded by default, so the page becomes too dense.

### Desired behavior

```text
All foldable Settings sections are collapsed on initial page load.
User can expand any section manually.
Refresh returns them to collapsed state.
No localStorage/sessionStorage persistence in this phase.
```

### Implementation notes

Find all Settings accordions/details. If native `<details>` is used, remove `open`:

```tsx
// Before
<details className="settings-fold-panel garmin-panel" open>

// After
<details className="settings-fold-panel garmin-panel">
```

If custom state is used:

```tsx
// Before
const [isOpen, setIsOpen] = useState(true);

// After
const [isOpen, setIsOpen] = useState(false);
```

Apply this to:

```text
Garmin
Analysis Types
Exercises and Weights
Backup and Restore
Advanced
```

Collapsed rows should still show useful summaries:

```text
Garmin: Connected/Disconnected, auto-sync enabled/disabled, sync range.
Analysis Types: N types, M custom.
Exercises and Weights: N exercises configured.
Backup and Restore: Backup history and restore data.
Advanced: Developer and system settings.
```

### Acceptance criteria

```text
Open Settings.
All sections are collapsed by default.
Clicking each header expands/collapses correctly.
Refreshing Settings returns all sections to collapsed.
No Settings content or functionality disappears.
```

## 23.2 Remove redundant Settings link from Garmin stats page

### Current problem

Garmin stats page has an extra inline `Settings` link in the same row as range buttons and sync.

### Desired behavior

Garmin stats controls show only:

```text
35 / 90 / 180 / 365 / All / Sync X days
```

No inline Settings link there. The global top-nav Settings item remains.

### Implementation notes

In `frontend/src/pages/GarminStatsPage.tsx`, find the range/sync action row and remove only the inline Settings link/button.

Do not remove:

```text
Top navigation Settings
Garmin Settings page/panel
Sync button
Range buttons
```

### Acceptance criteria

```text
On /garmin, no inline Settings link is shown next to day range controls.
Top nav still shows Settings.
Range buttons work.
Sync button works.
Mobile layout is less crowded.
```

## 23.3 Keep active page visible in top navigation

### Current problem

When opening a page, its nav item may disappear from the top navigation.

### Desired behavior

Top nav list is stable on every page:

```text
Current | History | Stats | Garmin | Backup | Settings
```

Current route is highlighted, not removed.

### Implementation notes

Inspect `frontend/src/App.tsx` or the nav component.

Remove any filtering like:

```tsx
navItems.filter((item) => item.path !== currentPath)
```

Render all items and apply active class:

```tsx
navItems.map((item) => (
  <NavLink
    key={item.path}
    to={item.path}
    className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}
  >
    {item.label}
  </NavLink>
))
```

If not using `NavLink`, compute active state manually but still render all items.

### Acceptance criteria

```text
On /current, Current is visible and active.
On /history, History is visible and active.
On /stats, Stats is visible and active.
On /garmin, Garmin is visible and active.
On /backup, Backup is visible and active.
On /settings, Settings is visible and active.
Nav order and item count never change.
```

## 23.4 Fix `asyncio.to_thread` monkeypatch cleanup

### Current problem

A test monkeypatches `asyncio.to_thread` but does not restore it.

### Implementation

In `tests/test_garmin_auto_sync.py`, replace direct non-restored assignment with `try/finally`:

```python
original_to_thread = asyncio.to_thread
asyncio.to_thread = fake_to_thread
try:
    first = asyncio.run(garmin_auto_sync_service.run_garmin_auto_sync_once())
    second = asyncio.run(garmin_auto_sync_service.run_garmin_auto_sync_once())
finally:
    asyncio.to_thread = original_to_thread
```

Alternative acceptable implementation:

```python
from unittest.mock import patch

with patch("asyncio.to_thread", side_effect=fake_to_thread):
    first = asyncio.run(...)
    second = asyncio.run(...)
```

### Acceptance criteria

```text
Test no longer leaks monkeypatch state.
Full test suite can run in any order.
No production code is changed for this test-only issue.
```

## Phase 23 verification

```bash
python -m unittest discover -s tests
cd frontend && npm run typecheck && npm run build
```

Status: completed on 2026-07-05.

Implementation notes:

- Settings Garmin, Analysis Types, and Exercises and Weights sections are collapsed by default with summary text.
- Garmin Stats no longer shows the inline Settings link next to range/sync controls.
- Top navigation renders the stable Current, History, Stats, Garmin, Backup, Settings item set on all routes.
- `asyncio.to_thread` monkeypatching is restored within the auto-sync test.
- `docs/CODEX_PLAN.md` is present as a pointer to this active plan.

Manual checks:

```text
Settings sections collapsed by default.
Garmin stats page has no extra inline Settings link.
All top-nav items stay visible on every page.
```

Suggested commit:

```text
Phase 23: polish navigation, settings accordions, and Garmin stats controls
```

---

# Phase 24 — Active Workout mobile and logging UX

## Purpose

Make active workout logging cleaner and more phone-friendly.

Covers:

- #3 Fix mobile scroll jump when adding first exercise.
- #4 Auto-save RPE and Back pain; remove Session stats save button.
- #5 Remove inline exercise creation from active workout page.

## Expected target files

```text
frontend/src/pages/CurrentWorkoutPage.tsx
frontend/src/styles.css
frontend/src/api/client.ts
frontend/src/types.ts
app/routes or app/api files only if endpoint changes are required
tests only if backend behavior changes
```

## 24.1 Fix mobile scroll jump when adding first exercise

### Current problem

On phone:

```text
Start new workout.
Add first exercise.
Page unexpectedly scrolls/jumps.
Add second/third exercise.
Everything works as expected.
```

### Likely cause

```text
First exercise card/list appears for the first time.
Layout height changes.
Focused select/button/input causes browser auto-scroll.
There may also be explicit scrollIntoView/focus logic.
```

### Implementation notes

Inspect add-exercise handler in `CurrentWorkoutPage.tsx`.

Search for:

```text
scrollIntoView
focus()
window.scrollTo
autoFocus
setTimeout
requestAnimationFrame
```

If explicit scroll/focus exists after add, remove or limit it.

Preserve scroll position around add-exercise operation, especially on small screens:

```ts
const previousScrollY = window.scrollY;
const isSmallScreen = window.matchMedia("(max-width: 640px)").matches;

if (isSmallScreen && document.activeElement instanceof HTMLElement) {
  document.activeElement.blur();
}

await addExerciseToWorkout(...);

if (isSmallScreen) {
  requestAnimationFrame(() => {
    window.scrollTo({ top: previousScrollY, behavior: "auto" });
  });
}
```

Apply only to add-exercise action, not every set edit.

### Acceptance criteria

```text
On phone/small viewport, adding the first exercise does not jump unexpectedly.
Adding second and later exercises still works normally.
Desktop behavior is unchanged.
No automatic scroll to top or bottom.
Focus does not remain trapped in the exercise selector.
```

## 24.2 Auto-save RPE and Back pain on active workout page

### Desired behavior

```text
No separate Save button in Session stats.
RPE saves when changed.
Back pain saves when changed.
Show lightweight Saving/Saved/Failed status.
```

### Implementation notes

Remove active-workout session stats buttons like:

```text
Save
Save workout info
Save session stats
```

Add save state:

```ts
type SaveStatus = "idle" | "saving" | "saved" | "error";
```

For button-style controls:

```text
RPE: save immediately on click.
Back pain: save immediately on click.
```

For input-style controls, if present:

```text
Save on blur or 300-500ms debounce.
```

Example implementation:

```ts
async function updateSessionStatsPatch(patch: Partial<WorkoutSessionStats>) {
  setSessionStatsDraft((prev) => ({ ...prev, ...patch }));
  setSessionStatsSaveStatus("saving");

  try {
    await updateWorkout(workoutId, patch);
    setSessionStatsSaveStatus("saved");
  } catch (error) {
    setSessionStatsSaveStatus("error");
    setSessionStatsError("Could not save session stats.");
  }
}
```

Do not wait until Finish workout to persist these values.

### Acceptance criteria

```text
Changing RPE shows Saving then Saved.
Refresh keeps changed RPE.
Changing Back pain shows Saving then Saved.
Refresh keeps changed Back pain.
API failure shows error and does not claim Saved.
No Save button appears in active workout Session stats.
Finish workout behavior is unchanged.
```

## 24.3 Remove inline exercise creation from active workout page

### Current problem

Active workout page has fields for creating a new exercise:

```text
new exercise name
initial numbers/weights field
create button
```

### Desired behavior

Active workout page only adds existing exercises.
Exercise creation belongs in Settings.

Final active workout add-exercise UI:

```text
Exercise dropdown/select
Add exercise button
Small helper link: Missing an exercise? Add it in Settings.
```

### Implementation notes

Remove from `CurrentWorkoutPage.tsx`:

```text
New exercise name field.
Initial numbers/weights field.
Inline Create button.
Inline create-exercise API call.
```

Keep:

```text
Existing exercise dropdown.
Add selected exercise button.
```

Add helper link:

```tsx
<Link to="/settings">Missing an exercise? Add it in Settings.</Link>
```

Optional if easy:

```tsx
<Link to="/settings?section=exercises">Missing an exercise? Add it in Settings.</Link>
```

Do not make accordion persistence part of this phase.

### Acceptance criteria

```text
Active workout page has no inline exercise creation form.
User can still add existing exercises.
Settings page remains the place for creating/managing exercises.
Mobile active workout page is shorter and cleaner.
Backend exercise creation endpoint remains available.
```

## Phase 24 verification

```bash
cd frontend && npm run typecheck && npm run build
```

Status: completed on 2026-07-05.

Implementation notes:

- Active Workout preserves mobile scroll position around add-exercise actions.
- RPE and Back pain save immediately on select changes with Saving/Saved/Failed status.
- Removed inline active-workout exercise creation fields and API usage.
- Added a Settings link for missing exercises while keeping backend exercise creation endpoints unchanged.

Manual mobile checks:

```text
Start new workout.
Add first exercise; no scroll jump.
Add second exercise; still normal.
Change RPE; refresh; value persists.
Change Back pain; refresh; value persists.
Confirm no inline new-exercise fields.
```

Suggested commit:

```text
Phase 24: simplify active workout logging and auto-save session stats
```

---

# Phase 25 — Edit Workout UX alignment and page-level dirty save

## Purpose

Make Edit Workout consistent with Current Workout and avoid scattered save buttons.

Covers:

- #7 Remove `Save workout info`.
- #7 Use one main `Save workout` button.
- #7 Notify user about unsaved changes.
- #7 Use same delete button style as Current Workout.

## Expected target files

```text
frontend/src/pages/HistoryPage.tsx
frontend/src/pages/CurrentWorkoutPage.tsx
frontend/src/styles.css
frontend/src/components/workout/* if components exist or are added
app/services/draft_service.py only if backend behavior requires change
```

Note: edit-workout UI may currently live inside `HistoryPage.tsx`, not a separate `EditWorkoutPage.tsx`.

## 25.1 Remove `Save workout info`

Search for UI text:

```text
Save workout info
```

Remove this local metadata/session-info save button.

Do not remove the new page-level final save button.

## 25.2 Add one page-level Save workout button

### Desired behavior

```text
User edits workout metadata, session stats, exercises, and sets.
Page shows Unsaved changes.
User presses one Save workout button.
All changes are persisted.
```

### Implementation notes

Add page-level state:

```ts
const [draftWorkout, setDraftWorkout] = useState(...);
const [originalWorkout, setOriginalWorkout] = useState(...);
const [isDirty, setIsDirty] = useState(false);
const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
```

Use explicit dirty flag:

```ts
function markDirty() {
  setIsDirty(true);
}
```

Call `markDirty()` on every edit:

```text
workout name
workout date/time
session RPE
back pain
set weight/reps/RPE
add set
remove set
add exercise
remove exercise
exercise order if supported
```

Save logic:

```ts
async function saveWorkoutChanges() {
  setSaveStatus("saving");

  try {
    await persistWorkoutDraft(draftWorkout);
    setOriginalWorkout(draftWorkout);
    setIsDirty(false);
    setSaveStatus("saved");
  } catch (error) {
    setSaveStatus("error");
  }
}
```

Use existing APIs if possible.
Do not create a large new backend endpoint unless current endpoints cannot safely persist all fields.

If multiple calls are needed:

```text
1. Save workout metadata/session fields.
2. Save exercise/set changes.
3. Save ordering/removals/additions.
```

If any call fails:

```text
Show error.
Keep dirty state.
Do not reset UI as saved.
Avoid partial success messaging.
```

## 25.3 Unsaved changes notification

Show when dirty:

```text
Unsaved changes
```

Suggested placement:

```text
Top-right of edit page header, and/or near Save workout button.
```

Show save status:

```text
Saving...
Workout saved
Could not save workout
```

Optional browser leave protection:

```ts
useEffect(() => {
  if (!isDirty) return;

  const handler = (event: BeforeUnloadEvent) => {
    event.preventDefault();
    event.returnValue = "";
  };

  window.addEventListener("beforeunload", handler);
  return () => window.removeEventListener("beforeunload", handler);
}, [isDirty]);
```

Internal React Router blocking can be added only if simple; visible warning is required.

## 25.4 Align delete controls with Current Workout

### Desired behavior

Use same delete control everywhere. Prefer compact `×` icon.

Create reusable component if useful:

```tsx
type IconDeleteButtonProps = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
};

function IconDeleteButton({ label, onClick, disabled }: IconDeleteButtonProps) {
  return (
    <button
      type="button"
      className="icon-delete-button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
    >
      ×
    </button>
  );
}
```

Use it on:

```text
Current workout exercise delete.
Current workout set delete, if present.
Edit workout exercise delete.
Edit workout set delete, if present.
```

Accessibility:

```text
Visual text can be ×.
aria-label must be clear: Remove exercise, Remove set, etc.
```

## 25.5 Important UX distinction

```text
Current Workout:
- live logging
- session stats auto-save
- status can say Saved

Edit Workout:
- batch editing
- changes persist only after Save workout
- show Unsaved changes until saved
```

Do not make Edit Workout auto-save in this phase.

### Acceptance criteria

```text
Edit workout page has no Save workout info button.
One main Save workout button exists.
Changing workout name marks page dirty.
Changing date/time marks page dirty.
Changing RPE/back pain marks page dirty.
Changing set weight/reps/RPE marks page dirty.
Adding/removing sets marks page dirty.
Adding/removing exercises marks page dirty.
Save workout persists all changes.
After successful save, dirty warning disappears.
After failed save, dirty warning remains.
Delete controls use same × style as Current Workout.
Current Workout behavior is unchanged.
```

## Phase 25 verification

Manual:

```text
Open existing workout from History.
Edit metadata; Unsaved changes appears.
Edit sets; dirty state remains.
Click Save workout; success state appears.
Refresh; changes persist.
Remove exercise; save; refresh; removal persists.
Confirm no Save workout info button.
Confirm only one main Save workout button.
```

Status: completed on 2026-07-05.

Implementation notes:

- Edit Workout now edits a local page draft and marks changes dirty.
- A single Save workout button persists metadata, exercise adds/removals, set adds/removals, and set weight/reps changes through existing APIs.
- Removed the separate Save workout info button and edit set-row Save buttons.
- Added Unsaved changes and save status messaging plus a browser refresh warning while dirty.
- Current and Edit Workout exercise/set deletes use the shared compact `×` button style.

Suggested commit:

```text
Phase 25: unify edit workout save flow and delete controls
```

---

# Phase 26 — Stats chart X-axis date formatting and mobile layout

## Purpose

Make Stats charts visually consistent and readable on small screens.

Covers:

- #8 Align X-axis date format for all Stats charts that use dates on X.
- #8 Improve phone/small-screen chart label layout.

## Expected target files

```text
frontend/src/pages/StatsPage.tsx
frontend/src/styles.css
frontend/src/utils/chartDateFormat.ts
frontend/src/hooks/useMediaQuery.ts
frontend tests if available
```

## 26.1 Add shared chart date formatter

Create:

```text
frontend/src/utils/chartDateFormat.ts
```

Recommended helpers:

```ts
export function parseChartDate(value: string | Date): Date | null;

export function formatChartDateTick(
  value: string | Date,
  options?: {
    compact?: boolean;
    includeYear?: boolean;
    monthOnly?: boolean;
  }
): string;

export function formatChartDateTooltip(value: string | Date): string;

export function isDateLikeChartValue(value: unknown): boolean;
```

Formatting rules:

```text
Desktop day axis: 03 Jul, 10 Jul, 17 Jul.
Desktop with year if needed: 03 Jul 2026.
Month-level: Jul 2026.
Mobile day axis: 03.07, 10.07, 17.07.
Tooltip: 03 Jul 2026.
No raw ISO dates on axes.
```

Bad:

```text
2026-07-03
```

Good:

```text
03 Jul
```

## 26.2 Add responsive chart axis helper

Create:

```text
frontend/src/hooks/useMediaQuery.ts
```

or use an existing hook if present.

Recommended hook:

```ts
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    setMatches(media.matches);

    const listener = () => setMatches(media.matches);
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [query]);

  return matches;
}
```

Add helper:

```ts
export function getResponsiveXAxisProps(
  pointCount: number,
  isSmallScreen: boolean
) {
  if (!isSmallScreen) {
    return {
      angle: 0,
      textAnchor: "middle",
      interval: "preserveStartEnd",
      height: 36,
    };
  }

  if (pointCount <= 6) {
    return {
      angle: 0,
      textAnchor: "middle",
      interval: 0,
      height: 36,
    };
  }

  if (pointCount <= 12) {
    return {
      angle: -45,
      textAnchor: "end",
      interval: 0,
      height: 56,
    };
  }

  return {
    angle: -65,
    textAnchor: "end",
    interval: "preserveStartEnd",
    height: 72,
  };
}
```

Avoid always using vertical 90° labels. Prefer `-45` or `-65` first.

## 26.3 Apply to every date-based Stats chart

In `StatsPage.tsx`, identify all charts where X-axis is date/time.

Apply:

```tsx
<XAxis
  dataKey="date"
  tickFormatter={(value) =>
    formatChartDateTick(value, { compact: isSmallScreen })
  }
  {...getResponsiveXAxisProps(data.length, isSmallScreen)}
/>
```

For tooltip:

```tsx
<Tooltip
  labelFormatter={(value) => formatChartDateTooltip(value)}
/>
```

Do not apply date formatting to non-date axes such as exercise names/categories.

### Acceptance criteria

```text
All date-based Stats X-axes use one consistent format.
No raw ISO dates are visible on chart axes.
Tooltips show full readable dates.
Mobile chart labels do not overlap badly.
Non-date X-axes are unaffected.
```

## Phase 26 verification

Utility tests if available:

```text
formatChartDateTick("2026-07-03") => "03 Jul"
formatChartDateTick("2026-07-03", { compact: true }) => "03.07"
formatChartDateTooltip("2026-07-03") => "03 Jul 2026"
Invalid values return safe fallback.
```

Manual:

```text
Open Stats at 360px width.
Charts remain readable.
X labels do not overlap heavily.
Tap/hover tooltip shows full date.
```

Status: completed on 2026-07-05.

Implementation notes:

- Added shared chart date formatting helpers with fixed `03 Jul`, `03.07`, and `03 Jul 2026` outputs.
- Added a reusable media-query hook and responsive X-axis prop helper.
- Applied shared date tick and tooltip formatting to date-based Stats charts.
- Kept non-date axes such as exercise names and numeric volume axes unchanged.

Suggested commit:

```text
Phase 26: standardize Stats chart dates and mobile axis layout
```

---

# Phase 27 — Stats metric card visual representation

## Purpose

Improve Stats page data representation using cards, progress bars, range bars, sparklines, and a compact calculations panel.

Covers:

- #9 Improve metrics cards/data presentation.

## Expected target files

```text
frontend/src/pages/StatsPage.tsx
frontend/src/components/stats/MetricCard.tsx
frontend/src/components/stats/MetricRow.tsx
frontend/src/components/stats/MetricProgressBar.tsx
frontend/src/components/stats/MetricRangeBar.tsx
frontend/src/components/stats/MetricSparkline.tsx
frontend/src/components/stats/MetricStatusBadge.tsx
frontend/src/components/stats/MetricInfo.tsx
frontend/src/styles.css
```

Create `frontend/src/components/stats/` if it does not exist.

## 27.1 Create shared visual components

### MetricStatusBadge

```tsx
type MetricStatus = "good" | "watch" | "bad" | "neutral" | "info";

type MetricStatusBadgeProps = {
  status: MetricStatus;
  label: string;
};
```

Example labels:

```text
Good
On Track
Improving
Low
Watch
High
Risky
No data
```

### MetricProgressBar

For bounded 0-100 metrics:

```tsx
type MetricProgressBarProps = {
  value: number | null;
  min?: number;
  max?: number;
  markerLabel?: string;
  zones?: Array<{
    from: number;
    to: number;
    status: MetricStatus;
    label?: string;
  }>;
};
```

Use for:

```text
Recovery
Consistency
Readiness
ATL percent
CTL percent, if implemented
```

### MetricRangeBar

For zone/range metrics:

```tsx
type MetricRangeBarProps = {
  value: number | null;
  min: number;
  max: number;
  zones: Array<{
    from: number;
    to: number;
    status: MetricStatus;
    label: string;
  }>;
  valueLabel?: string;
};
```

Use for:

```text
Back pain risk
TSB
AC ratio
Monotony
Training strain
```

### MetricSparkline

Small trend chart:

```tsx
type MetricSparklinePoint = {
  date: string;
  value: number;
};

type MetricSparklineProps = {
  data: MetricSparklinePoint[];
  valueKey?: "value";
  label?: string;
};
```

Use for:

```text
Weekly load
Strength progress
Consistency mini history
Volume trend
Average RPE trend
Back pain trend
```

Use SVG or existing Recharts. Prefer no new dependency.

### MetricCard

Top dashboard card:

```tsx
type MetricCardProps = {
  title: string;
  value: string;
  subtitle?: string;
  icon?: ReactNode;
  status?: {
    label: string;
    status: MetricStatus;
  };
  visual?: ReactNode;
  description?: string;
};
```

### MetricRow

Advanced calculations row:

```tsx
type MetricRowProps = {
  label: string;
  description: string;
  value: string;
  status: MetricStatus;
  visual: ReactNode;
};
```

## 27.2 Top Stats overview cards

Improve overview section with cards:

```text
Recovery
Weekly Load
Strength Progress
Back Pain Risk
Consistency
```

Each card should contain:

```text
title
current value
status badge
compact visual
short explanation/subtitle
```

Suggested visual type:

```text
Recovery: progress bar.
Weekly Load: sparkline.
Strength Progress: sparkline.
Back Pain Risk: range bar.
Consistency: mini bars or sparkline.
```

## 27.3 Training load status card

Add grouped card:

```text
Training load status
```

Group:

```text
ATL — fatigue
CTL — fitness/base
TSB — freshness/fatigue balance
```

Display:

```text
Line chart with ATL and CTL.
TSB as line or area.
Summary chips below chart.
Short explanation.
```

Explanation text:

```text
ATL builds fatigue. CTL reflects fitness. TSB shows how fresh (+) or fatigued (–) you are.
```

Do not show ATL/CTL/TSB as disconnected random cards only.

## 27.4 Advanced Calculations panel

Add collapsible panel:

```text
Calculations
```

Rows:

```text
Fatigue (ATL)
Fitness (CTL)
Stress Balance (TSB)
Workload Ratio (AC)
Monotony
Training strain
```

Each row:

```text
info icon
metric name
compact visual bar
current value
small status dot/badge
```

Add legend:

```text
Low / High risk
Moderate
Good
```

## 27.5 Hide unsupported cardio-only metrics

Do not add:

```text
Effective VO2max
Marathon Shape
Race predictor
```

until running/cardio data supports them.

Focus metrics on:

```text
Load
Recovery
Fatigue
Fitness
Stress balance
Workload ratio
Monotony
Training strain
Volume
Intensity
Back pain
RPE
Consistency
Strength progress
```

### Acceptance criteria

```text
Stats page has clearer top metric cards.
Important metrics are not only raw numbers.
Bounded scores use progress bars.
Zone-based metrics use range bars.
Trend metrics use sparklines.
ATL/CTL/TSB are grouped in one Training load status card.
Advanced calculations are in collapsible Calculations panel.
No unsupported cardio-only metrics appear.
Mobile layout remains readable.
```

Status: completed on 2026-07-05.

Implementation notes:

- Added shared metric card, row, status badge, progress bar, range bar, sparkline, and info components.
- Reworked the top Stats overview into visual metric cards for Recovery, Weekly Load, Strength Progress, Back Pain Risk, and Consistency.
- Added grouped Training load status and collapsible Calculations panels as visual scaffolding for Phase 28 training-load values.
- Did not add unsupported cardio-only metrics.

Suggested commit:

```text
Phase 27: add visual metric cards and calculations panel
```

---

# Phase 28 — Training load model calculations

## Purpose

Add calculated training-load metrics for fatigue, fitness, stress balance, workload ratio, monotony, and strain.

Covers:

- #10 Add ATL, CTL, TSB, AC ratio, monotony, training strain, ATL percent.

## Expected target files

```text
app/services/stats_service.py
app/services/training_load_service.py
app/schemas.py
app/routes/stats routes if separate
docs/openapi.json
frontend/src/api/generated types if generated
frontend/src/pages/StatsPage.tsx
tests/test_stats_service.py
tests/test_stats_training_load.py
```

## 28.1 Use app-native daily training load

Do not copy Runalyze TRIMP blindly.

The app is primarily strength-training based, so use the app’s existing training load calculation as base.

Codex must inspect `app/services/stats_service.py` and identify current workout/daily load logic.

Preferred approach:

```text
If stats_service already calculates workout/daily load:
- reuse it
- extract helper if needed

If load is only calculated in frontend:
- move/copy canonical calculation to backend stats service
- keep frontend display-only

If several load concepts exist:
- choose the same one already used for recovery/readiness/stats
```

Final base metric:

```text
daily_load[date] = sum of all workout load points for that local app date
```

Important:

```text
Use APP_TIMEZONE/local app date.
Include zero-load days between first date and today.
Do not skip rest days in ATL/CTL calculation.
```

## 28.2 Add EWMA calculations

Create helper service if useful:

```text
app/services/training_load_service.py
```

Recommended function:

```python
def ewma_time_constant_series(
    values_by_date: dict[date, float],
    start_date: date,
    end_date: date,
    window_days: int,
) -> list[dict]:
    ...
```

Use time-constant EWMA:

```python
today_value = yesterday_value + (daily_load - yesterday_value) / window_days
```

Settings:

```text
ATL window_days = 7
CTL window_days = 42
```

Initial value:

```text
First day in series starts at that day’s daily_load.
Then continue day by day including zero-load days.
```

Alternative acceptable but less preferred:

```text
Start at 0 and mark warm-up period as low confidence.
```

## 28.3 Metrics to calculate

For each date:

```text
date
daily_load
atl
ctl
tsb
ac_ratio
atl_percent
ctl_percent optional
```

Definitions:

```text
ATL = 7-day EWMA of daily_load.
CTL = 42-day EWMA of daily_load.
TSB = CTL - ATL.
AC ratio = ATL / CTL, if CTL > 0 else null.
```

Reference max:

```text
atl_reference_max = historical 95th percentile of ATL values.
fallback = max(ATL) if not enough data.
fallback = null if no data.
```

Do not use all-time maximum as the only normalization because a past overload spike can make scale misleading.

ATL percent:

```text
atl_percent = atl / atl_reference_max * 100
```

CTL percent optional:

```text
ctl_percent = ctl / ctl_reference_max * 100
```

## 28.4 Monotony and strain

Use last 7 local days:

```text
last_7_daily_loads = today and previous 6 days
weekly_load = sum(last_7_daily_loads)
mean_load = average(last_7_daily_loads)
std_load = standard deviation
```

Recommended:

```python
monotony = mean_load / std_load if std_load > 0 else None
training_strain = weekly_load * monotony if monotony is not None else None
```

Handle edge cases:

```text
If std == 0 and mean == 0:
  monotony = None
  strain = None

If std == 0 and mean > 0:
  monotony = None for first implementation, with status/description explaining insufficient variation.
```

Avoid infinity or fake huge numbers in UI.

## 28.5 Status zones

Backend can return statuses, or frontend can derive them. Prefer backend returns statuses for consistency.

### ATL percent

```text
0–40%: low
40–70%: normal/good
70–90%: high/watch
90%+: very high/bad
```

### TSB

```text
> +10: fresh
-10 to +10: balanced
-25 to -10: fatigued/watch
< -25: very fatigued/bad
```

### AC ratio

```text
<0.8: low/underloading
0.8–1.3: good
1.3–1.5: high/watch
>1.5: risky/bad
```

### Monotony

```text
<1.0: varied/good
1.0–2.0: moderate/watch
>2.0: high/bad
```

### Back pain risk

If already available, keep current logic. Do not invent medical risk model in this phase.

## 28.6 API schema

Add to `app/schemas.py`.

Suggested models:

```python
class TrainingLoadPoint(BaseModel):
    date: str
    daily_load: float
    atl: float
    ctl: float
    tsb: float
    ac_ratio: float | None = None
    atl_percent: float | None = None
    ctl_percent: float | None = None

class MetricZone(BaseModel):
    from_value: float
    to_value: float
    label: str
    status: str

class TrainingLoadMetricSummary(BaseModel):
    key: str
    label: str
    value: float | None
    formatted_value: str
    status: str
    description: str
    zones: list[MetricZone] = []

class TrainingLoadSummary(BaseModel):
    latest_date: str | None
    daily_load: float | None
    atl: float | None
    ctl: float | None
    tsb: float | None
    ac_ratio: float | None
    atl_percent: float | None
    ctl_percent: float | None = None
    atl_reference_max: float | None
    ctl_reference_max: float | None = None
    weekly_load: float | None
    monotony: float | None
    training_strain: float | None
    metrics: list[TrainingLoadMetricSummary]
    series: list[TrainingLoadPoint]
```

Add to existing Stats response:

```python
training_load: TrainingLoadSummary
```

Keep it additive/backward-compatible if possible.

## 28.7 OpenAPI and generated frontend types

Because API response changes:

```text
Update docs/openapi.json.
Regenerate frontend API/types if project uses generated types.
Ensure TypeScript compile passes.
```

Codex must inspect existing scripts. Possible commands:

```bash
python -m app.scripts.generate_openapi
npm run generate-api
```

If no generator exists, update in existing project style.

## 28.8 Backend tests

Create:

```text
tests/test_stats_training_load.py
```

Test cases:

### EWMA basics

```text
Day 1 daily_load = 100
Day 2 daily_load = 0
Day 3 daily_load = 0
ATL window = 7
Day 1 ATL = 100
Day 2 ATL = 100 + (0 - 100) / 7
Day 3 ATL = previous + (0 - previous) / 7
```

### Zero days included

```text
Workout on Monday and Thursday.
Series includes Tuesday and Wednesday with daily_load = 0.
ATL decays on rest days.
```

### TSB

```text
TSB = CTL - ATL
```

### AC ratio

```text
CTL > 0 => ATL / CTL
CTL == 0 => None
```

### Reference max

```text
Enough ATL values => 95th percentile.
Not enough values => max.
No values => None.
```

### Monotony

```text
Loads [10,20,30,40,50,60,70]
monotony = mean / std
strain = weekly_sum * monotony
```

### Empty history

```text
No workouts.
training_load summary returns null values and empty series.
Stats page does not crash.
```

## 28.9 Frontend integration

Stats page consumes `training_load`.

Map metrics into Phase 27 components:

```text
ATL -> MetricRow + range/progress bar.
CTL -> MetricRow + range/progress bar.
TSB -> MetricRow + range bar.
AC ratio -> MetricRow + range bar.
Monotony -> MetricRow + range bar.
Training strain -> MetricRow + range/progress by relative status.
```

Training load chart:

```text
Series:
- ATL
- CTL
- TSB
```

Labels:

```text
ATL (Fatigue)
CTL (Fitness)
TSB (Stress Balance)
```

Use Phase 26 date formatting.

### Acceptance criteria

```text
Stats API returns training_load object.
Stats page shows Training load status card.
Calculations panel shows ATL, CTL, TSB, AC ratio, monotony, strain.
Rest days affect ATL/CTL decay.
No crash with empty workout history.
No unsupported cardio metrics appear.
TypeScript builds.
Backend tests pass.
```

Status: completed on 2026-07-05.

Implementation notes:

- Added `app/services/training_load_service.py` for daily app-load aggregation, rest-day series filling, EWMA ATL/CTL, TSB, AC ratio, ATL/CTL reference percentages, monotony, strain, statuses, and metric zones.
- Added top-level `training_load` to the Stats API response while also retaining it inside `stats` for local consumers.
- Regenerated OpenAPI/generated frontend contracts and added frontend API types for training-load metrics and series.
- Replaced Phase 27 training-load placeholders with real backend metrics, ATL/CTL/TSB charting, and populated calculation rows.
- Added focused backend tests for rest days, empty history, percentile fallback, and route-level `training_load` exposure.

Suggested commit:

```text
Phase 28: add training load calculations and Stats integration
```

---

# Phase 29 — Final integration, docs, changelog, and release prep

## Purpose

Stabilize the whole batch and prepare version `1.3.0`.

Covers:

```text
Final verification
Docs update
Changelog update
Version bump
Docker build
Manual smoke tests
```

## Expected target files

```text
CHANGELOG.md
config.yaml
docs/CODEX_PLAN.md
docs/openapi.json
frontend generated API/types if applicable
```

## 29.1 Update docs

Update this file:

```text
docs/CODEX_PLAN.md
```

After implementation, mark completed:

```text
Phase 23 — completed
Phase 24 — completed
Phase 25 — completed
Phase 26 — completed
Phase 27 — completed
Phase 28 — completed
```

Add summary:

```text
1.3.0 focuses on:
- cleaner Settings and navigation
- simplified active workout mobile UX
- unified edit workout save behavior
- improved Stats chart formatting
- visual metric cards
- training load model: ATL, CTL, TSB, AC ratio, monotony, strain
```

## 29.2 Update CHANGELOG

Add:

```markdown
## 1.3.0 - YYYY-MM-DD

### Added
- Added training-load calculations: ATL, CTL, TSB, AC ratio, monotony, and training strain.
- Added visual metric cards with progress bars, range bars, and sparklines on the Stats page.
- Added grouped Training load status chart for ATL, CTL, and TSB.
- Added advanced Calculations panel for training-load metrics.

### Changed
- Settings sections are collapsed by default.
- Top navigation now keeps the active page visible and highlights it consistently.
- Active workout page now uses cleaner add-existing-exercise flow.
- RPE and Back pain on active workout auto-save when changed.
- Edit workout page now uses one page-level Save workout button.
- Stats charts now use consistent date formatting and improved mobile X-axis layout.

### Removed
- Removed redundant inline Settings link from Garmin stats controls.
- Removed inline exercise creation from active workout page.
- Removed separate Save workout info button from edit workout page.

### Fixed
- Fixed mobile scroll jump when adding the first exercise to a new workout.
- Fixed test monkeypatch cleanup for asyncio.to_thread.
```

## 29.3 Version bump

In `config.yaml`:

```yaml
version: "1.3.0"
```

Only do this after Phases 23–28 pass.

## 29.4 Verification commands

Backend:

```bash
python -m unittest discover -s tests
```

Frontend:

```bash
cd frontend
npm run typecheck
npm run build
cd ..
```

Docker:

```bash
docker build -t training-log:1.3.0 .
```

If lint exists:

```bash
cd frontend
npm run lint
cd ..
```

## 29.5 Manual smoke test checklist

### Navigation

```text
Open every page.
Current nav item remains visible on /current.
History nav item remains visible on /history.
Stats nav item remains visible on /stats.
Garmin nav item remains visible on /garmin.
Backup nav item remains visible on /backup.
Settings nav item remains visible on /settings.
Only active item is highlighted.
```

### Settings

```text
Open Settings.
All sections are collapsed by default.
Expand Garmin.
Auto-sync controls still work.
Collapse Garmin.
Refresh page.
All sections collapsed again.
```

### Garmin stats

```text
Open Garmin stats.
No inline Settings link in range row.
Range buttons work.
Sync button works.
Top nav Settings still exists.
```

### Active Workout

```text
Start new workout on phone viewport.
Add first exercise.
No scroll jump.
Add second exercise.
Still normal.
Change RPE.
Status shows Saved.
Refresh.
RPE persists.
Change Back pain.
Status shows Saved.
Refresh.
Back pain persists.
No inline new exercise creation fields.
Helper link to Settings exists.
```

### Edit Workout

```text
Open workout from History.
Change workout name.
Unsaved changes appears.
Change set values.
Unsaved changes remains.
Delete set or exercise.
Delete control uses × style.
Click Save workout.
Success status appears.
Refresh.
Changes persist.
No Save workout info button exists.
Only one main Save workout button exists.
```

### Stats

```text
Open Stats desktop.
Top metric cards render.
Training load status chart renders.
Calculations panel renders.
Date labels are consistent.
No raw ISO dates on chart axes.
Open mobile viewport.
Date labels do not overlap badly.
Tooltips show full dates.
No VO2max or Marathon Shape metrics.
```

### Empty/low-data state

```text
Use empty or nearly empty DB if possible.
Stats page does not crash.
Training load cards show No data / insufficient data.
Charts show empty states gracefully.
```

Suggested commit:

```text
Phase 29: document and release Training Log 1.3.0
```

---

# Final phase order

```text
Phase 23 — Navigation, Settings, Garmin stats polish, and carryover cleanup
Phase 24 — Active Workout mobile and logging UX
Phase 25 — Edit Workout UX alignment and page-level dirty save
Phase 26 — Stats chart X-axis date formatting and mobile layout
Phase 27 — Stats metric card visual representation
Phase 28 — Training load model calculations
Phase 29 — Final integration, docs, changelog, and release prep
```

Recommended order:

1. Phase 23 reduces small UX noise and restores docs.
2. Phase 24 cleans active workout mobile flow.
3. Phase 25 aligns edit-workout saving and deletion behavior.
4. Phase 26 prepares chart formatting infrastructure.
5. Phase 27 builds visual metric components and layout.
6. Phase 28 adds real training-load calculations under the visual layer.
7. Phase 29 stabilizes, verifies, documents, and releases `1.3.0`.

---

# Final release rule

Do not bump `config.yaml` to `1.3.0` until:

```text
All backend tests pass.
Frontend typecheck passes.
Frontend build passes.
Docker build passes.
Manual smoke test is completed.
CHANGELOG is updated.
CODEX_PLAN.md marks phases correctly.
```
