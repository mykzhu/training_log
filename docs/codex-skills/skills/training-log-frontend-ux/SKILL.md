---
name: training-log-frontend-ux
description: Use this when changing Training Log React UI/UX, especially Settings, Current Workout, Edit Workout, Stats, Garmin, and mobile behavior.
---

# Training Log Frontend UX Skill

## When to use

Use this for React/TypeScript UI work in:

```text
frontend/src/pages/
frontend/src/components/
frontend/src/styles.css
```

Especially:

```text
SettingsPage
GarminStatsPage
CurrentWorkoutPage
HistoryPage / edit workout flow
StatsPage
navigation in App.tsx
```

## UX principles for this app

### Stable top navigation

Always show:

```text
Current | History | Stats | Garmin | Log | Backup | Settings
```

Never hide the active route. Highlight it instead.

### Mobile-first logging

Active Workout is used on a phone during training.

Prefer:

```text
- fewer fields
- fewer buttons
- no layout jumps
- large enough tap targets
- status text instead of modal noise
```

### Settings should not be noisy

Foldable sections should be collapsed by default unless explicitly requested otherwise.

### Active Workout vs Edit Workout

Current / active workout:

```text
- live logging
- session RPE and Back pain auto-save
- no separate Session stats Save button
- only add existing exercises
- missing exercise link goes to Settings
```

Edit workout:

```text
- batch editing
- one page-level Save workout button
- visible Unsaved changes state
- no multiple scattered save buttons
```

## Common implementation patterns

### Active nav

Prefer `NavLink`:

```tsx
<NavLink
  to="/stats"
  className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}
>
  Stats
</NavLink>
```

### Delete controls

Use consistent compact delete icon:

```tsx
<button
  type="button"
  className="icon-delete-button"
  aria-label="Remove exercise"
  title="Remove exercise"
>
  ×
</button>
```

Do not mix:

```text
×
Delete
Remove
```

on equivalent controls.

### Auto-save status

Use simple statuses:

```text
Saving...
Saved
Could not save
```

Do not add a Save button when the control already auto-saves.

### Avoid mobile scroll jumps

After adding first exercise:

```ts
const previousScrollY = window.scrollY;

if (document.activeElement instanceof HTMLElement) {
  document.activeElement.blur();
}

await addExerciseToWorkout(...);

requestAnimationFrame(() => {
  window.scrollTo({ top: previousScrollY, behavior: "auto" });
});
```

Only apply if needed; do not fight normal user scrolling.

## Styling rules

Use existing dark theme.

Prefer existing variables/classes.

Do not introduce inconsistent one-off colors.

Cards should use:

```text
- rounded corners
- consistent gap spacing
- readable labels
- compact status badges
- mobile wrapping
```

## Acceptance checklist

Before finishing UI work:

```text
Desktop view works.
Mobile width 360-430px works.
No horizontal overflow.
No disappearing nav items.
No duplicate Settings links.
No redundant Save buttons.
Error state is visible.
Loading state is visible.
Empty state is handled.
```
