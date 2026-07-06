# Training Log — Stats UI Polish Codex Plan

**Base:** latest `master` after the 1.3.0 implementation batch
**Observed problem:** features/calculations were implemented, but the Stats UI does not match the approved design direction. It is cramped, repetitive, visually noisy, and some metric visualizations are semantically wrong.
**Recommended next version:** `1.3.1` patch release after design polish
**New phase numbering:** continue after Phase 29.

---

# Phase 30 — Stats UI design polish and visual system cleanup

## Purpose

Polish the new Stats dashboard UI so it matches the approved design direction:

- premium dark dashboard look
- readable, less cramped metric cards
- correct visual semantics for bars/ranges
- no duplicated ATL/CTL/TSB rows
- better desktop layout
- clean mobile layout
- consistent colors, labels, and spacing

This phase is mostly frontend/CSS. Do not change training-load formulas unless a visual bug exposes a clearly incorrect field mapping.

---

## Current implementation problems

### Problem 1 — Stats page is too narrow for a 5-card dashboard

Current CSS caps Stats width at about 820px:

```css
.app-shell-stats {
  width: min(100%, 820px);
}
```

At the same time the top metric grid uses 5 columns:

```css
.metric-card-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}
```

Result: five cards are squeezed into narrow columns, causing tall cards, cramped labels, and non-premium layout.

### Problem 2 — Metric cards look like plain boxes, not dashboard cards

Current `MetricCard` supports `icon`, but no icons are actually passed from `StatsOverview`.

Cards need:

- leading colored icon circle
- better hierarchy
- value + badge alignment
- shorter descriptions
- cleaner visual spacing
- min width and responsive grid behavior

### Problem 3 — Sparkline visuals are weak

`MetricSparkline` renders only a bare polyline. It has:

- no area fill
- no empty state
- no semantic color variants
- no trend endpoint marker
- no different colors per card
- no visible baseline or context

This makes Weekly Load and Strength Progress look like thin generic blue lines.

### Problem 4 — Progress/range bars are visually rough

The current bars use full-opacity segmented zones and put the value label below the bar. Problems:

- marker can sit at extreme edge and look clipped
- label appears twice in rows
- no axis labels like Low / Moderate / High
- consistency uses recovery zones, which is semantically wrong
- row bars are too large and heavy

### Problem 5 — Training load status repeats the same metrics twice

Current Stats page shows:

1. Training load chart
2. Full rows for ATL / CTL / TSB directly below chart
3. Calculations panel with ATL / CTL / TSB again

This duplicates information and makes the page feel messy.

Final design should be:

```text
Training load status card:
- chart
- small summary chips for ATL / CTL / TSB

Calculations panel:
- full compact rows for ATL / CTL / TSB / AC ratio / Monotony / Strain
```

### Problem 6 — Calculations rows are too chunky

Current `MetricRow` layout is functional but visually heavy. Each row is a large card. It should become a compact table-like row.

### Problem 7 — Status labels are inconsistent

Metric rows currently pass raw status strings to `MetricStatusBadge`, so labels become lower-case like:

```text
good
info
watch
```

Final UI should show human labels:

```text
Good
Info
Watch
Risk
No data
```

### Problem 8 — Training load chart color mapping does not match approved design

Current chart uses:

```text
ATL = orange
CTL = green
TSB = blue
```

Approved design direction:

```text
ATL / Fatigue = blue
CTL / Fitness = teal/cyan
TSB / Stress Balance = purple
```

Use consistent colors in chart, rows, legends, and summary chips.

### Problem 9 — No chart legend in Training load chart

The chart needs a visible legend:

```text
ATL (Fatigue)
CTL (Fitness)
TSB (Stress Balance)
```

### Problem 10 — Desktop layout should be two-column for main Stats body

Approved direction had:

```text
Top metric cards full width
Main grid:
  left: Training load status
  right: Calculations
Bottom charts
Summary
```

Current implementation stacks Training load and Calculations vertically.

---

## Target files

Primary:

```text
frontend/src/components/stats/StatsOverview.tsx
frontend/src/components/stats/MetricCard.tsx
frontend/src/components/stats/MetricRow.tsx
frontend/src/components/stats/MetricProgressBar.tsx
frontend/src/components/stats/MetricRangeBar.tsx
frontend/src/components/stats/MetricSparkline.tsx
frontend/src/components/stats/MetricStatusBadge.tsx
frontend/src/components/stats/MetricInfo.tsx
frontend/src/styles.css
```

Secondary:

```text
frontend/src/pages/StatsPage.tsx
frontend/src/api/types.ts
docs/CODEX_PLAN.md
CHANGELOG.md
```

Do not change backend unless a frontend data field is missing or incorrectly named.

---

## Required visual target

The Stats page should visually follow this structure:

```text
Stats page
  Page header + range selector

  Top metric cards
    Recovery
    7-day Load
    Strength Intensity
    Back Pain Risk
    Consistency

  Stats main grid
    Training load status
      ATL/CTL/TSB chart
      ATL chip
      CTL chip
      TSB chip

    Calculations
      compact rows:
      ATL
      CTL
      TSB
      AC ratio
      Monotony
      Training strain

  Existing charts / summary
```

---

# 30.1 Widen Stats page desktop layout

## Implementation

Change Stats shell width from narrow 820px to a dashboard width.

In `frontend/src/styles.css`:

```css
.app-shell-stats {
  width: min(100%, 1180px);
}
```

If Home Assistant ingress feels too wide, use:

```css
.app-shell-stats {
  width: min(100%, 1120px);
}
```

Do not widen non-stats pages.

## Responsive grid

Update metric cards:

```css
.metric-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(205px, 1fr));
  gap: 14px;
  margin: 0 0 16px;
}
```

Use this instead of hard-coded `repeat(5, 1fr)`.

Desktop with enough space will show five cards. Narrow desktop/tablet will wrap naturally.

## Acceptance criteria

```text
On wide desktop, top metric cards are not cramped.
On 820px viewport, cards wrap cleanly.
On mobile, cards become one or two columns depending width.
No horizontal overflow.
```

---

# 30.2 Redesign MetricCard component

## Current issue

`MetricCard` is too minimal and does not use icon/tones well.

## New API

Update `MetricCard.tsx`:

```tsx
type MetricTone = "recovery" | "load" | "strength" | "pain" | "consistency" | "neutral";

type MetricCardProps = {
  title: string;
  value: string;
  subtitle?: string;
  icon?: ReactNode;
  tone?: MetricTone;
  status?: {
    label: string;
    status: MetricStatus;
  };
  visual?: ReactNode;
  description?: string;
};
```

## New markup

Target structure:

```tsx
<article className={`metric-card metric-card-${tone ?? "neutral"}`}>
  <div className="metric-card-top">
    <div className="metric-card-icon" aria-hidden="true">
      {icon}
    </div>

    <div className="metric-card-copy">
      <span className="metric-card-title">{title}</span>
      {subtitle && <small>{subtitle}</small>}
    </div>

    {status && <MetricStatusBadge ... />}
  </div>

  <div className="metric-card-value-row">
    <strong>{value}</strong>
  </div>

  {visual && <div className="metric-card-visual">{visual}</div>}

  {description && <p>{description}</p>}
</article>
```

## Icons

Do not add an icon package if not already installed.

Use simple inline SVG icons:

```text
Recovery: heartbeat/heart
7-day Load: dumbbell/barbell or kg
Strength: upward trend arrow
Back Pain Risk: warning/back/spine simple icon
Consistency: calendar/check
```

## CSS target

```css
.metric-card {
  position: relative;
  min-height: 164px;
  padding: 16px;
  border-radius: 18px;
  background:
    radial-gradient(circle at top left, rgba(10, 132, 255, 0.10), transparent 42%),
    var(--card);
  border: 1px solid var(--border);
  display: grid;
  gap: 12px;
  align-content: start;
}

.metric-card-top {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: start;
}

.metric-card-icon {
  width: 38px;
  height: 38px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(10, 132, 255, 0.38);
  background: rgba(10, 132, 255, 0.13);
  color: var(--blue);
}

.metric-card-title {
  color: var(--text);
  font-size: 14px;
  font-weight: 800;
}

.metric-card-copy small {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.3;
}

.metric-card-value-row strong {
  font-size: 28px;
  line-height: 1;
  letter-spacing: -0.02em;
}

.metric-card p {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.35;
}
```

Tone classes should only change icon/accent color, not the entire card background.

## Acceptance criteria

```text
Each top card has a leading icon.
Value hierarchy is clearer.
Descriptions are readable but not dominant.
Badges align consistently.
Cards look like dashboard cards, not plain boxes.
```

---

# 30.3 Fix top metric card semantics and labels

## Recovery

Final:

```text
Recovery
RPE + back pain
68%
Watch
```

Description:

```text
Combined session feedback from RPE and back pain.
```

## Weekly Load should be renamed to 7-day Load

Current screenshot shows:

```text
Weekly Load
15.3 average per workout
0.0
```

This feels broken because current 7-day load can be zero while average per workout is not zero.

Final card:

```text
7-day Load
Including rest days
```

Value rule:

```text
If trainingLoad.weekly_load is null or zero: "No recent load"
Otherwise: formatted weekly_load
```

Description:

```text
Load from the last 7 local days.
```

Do not show `average per workout` as subtitle for this card; it is not the same concept.

## Strength Progress should be renamed to Strength Intensity

Current title implies trend/progress, but value is average relative intensity.

Final:

```text
Strength Intensity
Average e1RM context
105%
```

Status:

```text
Info
```

or no badge if no trend is computed.

Do not use `Trend` badge unless the backend actually computes a trend.

## Back Pain Risk

Keep title:

```text
Back Pain Risk
```

Description:

```text
Average reported back pain across logged workouts.
```

Use range bar with labels:

```text
Low | Moderate | High
```

## Consistency

Current visual uses `recoveryZones`, which is wrong.

Create separate consistency zones:

```ts
const consistencyZones = [
  { from: 0, to: 50, status: "bad", label: "Low" },
  { from: 50, to: 80, status: "watch", label: "Partial" },
  { from: 80, to: 100, status: "good", label: "Good" },
];
```

For 100%, show full green-dominant progress, not a misleading recovery bar.

Description:

```text
Workouts with both RPE and back-pain feedback.
```

## Acceptance criteria

```text
No top card uses misleading labels.
7-day Load no longer shows contradictory 0.0 + average per workout.
Strength card no longer says Progress unless actual progress is calculated.
Consistency bar uses consistency-specific zones.
```

---

# 30.4 Improve MetricProgressBar and MetricRangeBar

## New props

Update both components to support:

```tsx
size?: "sm" | "md"
showValueLabel?: boolean
showEdgeLabels?: boolean
edgeLabels?: {
  left?: string;
  center?: string;
  right?: string;
}
tone?: "recovery" | "load" | "strength" | "pain" | "neutral"
```

## Marker clamp

Do not let marker visually overflow at 0% or 100%.

```ts
const markerPercent = percent === null ? null : Math.min(98, Math.max(2, percent));
```

## Bar labels

For top cards:

```text
showEdgeLabels = true
```

Examples:

Recovery:

```text
0%   50%   100%
```

Back pain:

```text
Low   Moderate   High
```

For calculation rows:

```text
showValueLabel = false
```

because row already has a value column.

## CSS

Use smaller bars in rows:

```css
.metric-row .metric-progress-track,
.metric-row .metric-range-track {
  height: 8px;
}

.metric-card .metric-progress-track,
.metric-card .metric-range-track {
  height: 10px;
}
```

Add labels:

```css
.metric-bar-labels {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  color: var(--muted);
  font-size: 11px;
}

.metric-bar-labels span:nth-child(2) {
  text-align: center;
}

.metric-bar-labels span:last-child {
  text-align: right;
}
```

## Acceptance criteria

```text
Top card bars have useful labels.
Row bars do not duplicate value labels.
Markers never clip at edges.
Bars look consistent across cards and rows.
```

---

# 30.5 Redesign MetricSparkline

## New API

```tsx
type MetricSparklineProps = {
  data: MetricSparklinePoint[];
  tone?: "load" | "strength" | "consistency" | "neutral";
  label?: string;
  emptyLabel?: string;
  showArea?: boolean;
};
```

## Empty state

If data length is less than 2:

```tsx
return <div className="metric-sparkline-empty">No trend yet</div>;
```

Do not draw a flat line if there is no real trend.

## SVG improvements

Add:

```tsx
<defs>...</defs>
<polygon className="metric-sparkline-area" ... />
<polyline className="metric-sparkline-line" ... />
<circle className="metric-sparkline-end" ... />
```

## Acceptance criteria

```text
Sparkline cards look intentional.
Empty trend state does not render misleading flat line.
Load and strength can have different tones.
```

---

# 30.6 Redesign Training load status layout

## Final structure

```tsx
<section className="panel training-load-status-card">
  <div className="panel-header training-load-header">...</div>

  <div className="training-load-legend">
    <span className="legend-atl">ATL (Fatigue)</span>
    <span className="legend-ctl">CTL (Fitness)</span>
    <span className="legend-tsb">TSB (Stress Balance)</span>
  </div>

  <div className="training-load-chart">...</div>

  <div className="training-load-chip-grid">
    <TrainingLoadChip metric={atlMetric} tone="atl" />
    <TrainingLoadChip metric={ctlMetric} tone="ctl" />
    <TrainingLoadChip metric={tsbMetric} tone="tsb" />
  </div>
</section>
```

Remove full `TrainingLoadMetricRow` rows from the Training load card. Those rows belong only in Calculations.

## Chart color mapping

Set:

```text
ATL = blue
CTL = teal/cyan
TSB = purple
```

CSS variables:

```css
:root {
  --stats-atl: #0a84ff;
  --stats-ctl: #30d5c8;
  --stats-tsb: #af52de;
}
```

Use:

```tsx
<Line dataKey="atl" stroke="var(--stats-atl)" />
<Line dataKey="ctl" stroke="var(--stats-ctl)" />
<Line dataKey="tsb" stroke="var(--stats-tsb)" />
```

## Acceptance criteria

```text
Training load card does not duplicate the full Calculations rows.
ATL/CTL/TSB chart has visible legend.
ATL is blue, CTL is teal, TSB is purple.
Three summary chips appear below chart.
Chart looks closer to approved mockup.
```

---

# 30.7 Make Calculations panel compact and premium

## MetricRow markup

```tsx
<div className="metric-row">
  <div className="metric-row-main">
    <strong>{label}</strong>
    <span>{description}</span>
  </div>

  <div className="metric-row-visual">{visual}</div>

  <div className="metric-row-value">{value}</div>

  <MetricStatusBadge ... />
</div>
```

Use human labels:

```ts
function metricStatusDisplay(status: MetricStatus) {
  switch (status) {
    case "good": return "Good";
    case "watch": return "Watch";
    case "bad": return "Risk";
    case "info": return "Info";
    case "neutral": return "No data";
  }
}
```

## CSS

```css
.metric-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.15fr) minmax(220px, 1fr) minmax(64px, auto) auto;
  gap: 12px;
  align-items: center;
  border: 0;
  border-top: 1px solid rgba(255,255,255,0.08);
  border-radius: 0;
  padding: 12px 0;
  background: transparent;
}

.metric-row:first-of-type {
  border-top: 0;
}

.metric-row-main strong {
  color: var(--text);
  font-size: 14px;
}

.metric-row-main span {
  color: var(--muted);
  font-size: 12px;
}

.metric-row-value {
  color: var(--text);
  font-size: 18px;
  font-weight: 800;
  text-align: right;
}
```

## Mobile layout

```css
@media (max-width: 640px) {
  .metric-row {
    grid-template-columns: 1fr auto;
  }

  .metric-row-visual {
    grid-column: 1 / -1;
  }

  .metric-row-value {
    text-align: left;
  }
}
```

## Acceptance criteria

```text
Calculations rows are compact.
Rows do not look like separate chunky cards.
Badges use Good/Watch/Risk/Info/No data labels.
Rows are readable on mobile.
No duplicated value labels under bars.
```

---

# 30.8 Add desktop two-column Stats main grid

In `StatsOverview.tsx`, wrap Training load card and Calculations panel:

```tsx
<section className="stats-main-grid">
  <TrainingLoadStatusCard ... />
  <CalculationsPanel ... />
</section>
```

CSS:

```css
.stats-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(340px, 0.95fr);
  gap: 16px;
  margin-bottom: 16px;
  align-items: start;
}

@media (max-width: 960px) {
  .stats-main-grid {
    grid-template-columns: 1fr;
  }
}
```

## Acceptance criteria

```text
On wide desktop, Training load status and Calculations are side by side.
On tablet/mobile, they stack.
The layout resembles approved dashboard mockup.
```

---

# 30.9 Move Summary lower and reduce visual priority

Keep Summary, but it should not compete with top dashboard cards.

Visual treatment:

```css
.stats-summary-panel {
  background: rgba(255,255,255,0.025);
}
```

Do not remove Summary.

## Acceptance criteria

```text
Summary is still available.
Summary does not visually dominate the new Stats dashboard.
```

---

# 30.10 Fix CSS color tokens for stats

Add stats-specific tokens:

```css
:root {
  --stats-atl: #0a84ff;
  --stats-ctl: #30d5c8;
  --stats-tsb: #af52de;
  --stats-load: #0a84ff;
  --stats-strength: #af52de;
  --stats-pain: #ff9f0a;
  --stats-good: #30d158;
  --stats-watch: #ffd60a;
  --stats-risk: #ff453a;
}
```

Do not replace global `--green` everywhere unless necessary.

For metric badges, use `--stats-good`, not the dark global `--green`.

## Acceptance criteria

```text
Green labels are readable.
ATL/CTL/TSB colors are consistent.
Badges and bars use same semantic colors.
```

---

# 30.11 Update empty/no-data states

Rules:

```text
If trainingLoad.weekly_load is null or 0 and no workouts in last 7 days:
  show "No recent load"

If sparkline data has fewer than 2 points:
  show "No trend yet"

If monotony/strain are null:
  show "No data", no marker, neutral badge

If AC ratio is very low because CTL is nonzero but ATL near zero:
  show value but description should explain "Recent load is low versus base"
```

Do not hide true zero values if they are meaningful, but avoid making the dashboard look broken.

## Acceptance criteria

```text
No misleading flat blue line for no data.
No confusing 0.0 with unrelated average subtitle.
No data rows look intentional.
```

---

# 30.12 Update docs and plan

Update:

```text
docs/CODEX_PLAN.md
CHANGELOG.md
```

Add:

```text
Phase 30 — Stats UI design polish and visual system cleanup
```

Do not bump `config.yaml` during Phase 30 unless this phase is combined with release prep.

Recommended `CHANGELOG.md` under Unreleased or 1.3.1 draft:

```markdown
## 1.3.1 - Unreleased

### Changed
- Polished Stats dashboard layout, metric cards, training-load chart, and calculations panel.
- Improved Stats desktop layout and mobile readability.
- Standardized ATL/CTL/TSB colors and metric status labels.

### Fixed
- Fixed misleading top-card labels and visuals for 7-day load, strength intensity, and consistency.
- Removed duplicate ATL/CTL/TSB rows from the Training load card.
```

---

## Phase 30 verification

Run:

```bash
cd frontend
npm run typecheck
npm run build
cd ..
```

If any backend files are touched:

```bash
python -m unittest discover -s tests
```

Manual desktop checks:

```text
Open Stats on desktop width >= 1100px.
Top cards are readable and not cramped.
Training load and Calculations are side by side.
ATL/CTL/TSB chart has legend.
ATL/CTL/TSB colors match across chart/chips/rows.
No duplicate ATL/CTL/TSB full rows in Training load card.
```

Manual mobile checks:

```text
Open Stats at 360px width.
No horizontal overflow.
Cards stack cleanly.
Calculation rows stack cleanly.
Bars are readable.
Summary does not dominate.
```

Data state checks:

```text
Recent load = 0.
7-day Load card shows "No recent load" or clear zero state.
No sparkline renders fake trend for insufficient data.
Monotony/strain No data state looks intentional.
```

Suggested commit message:

```text
Phase 30: polish Stats dashboard visual design
```

Status: completed on 2026-07-05.

Implementation notes:

- Widened the Stats desktop shell and replaced the fixed five-column card grid with responsive dashboard cards.
- Redesigned metric cards with tone accents, inline icons, clearer labels, and corrected 7-day Load, Strength Intensity, and Consistency semantics.
- Improved progress/range bars with clamped markers, optional edge labels, and compact row mode.
- Reworked sparklines with area fill, endpoint markers, tone colors, and intentional empty states.
- Rebuilt Training load status with ATL/CTL/TSB legend, approved blue/teal/purple color mapping, and summary chips instead of duplicated full rows.
- Made Calculations a compact table-like panel and placed it beside Training load on wide desktop.

---

# Phase 31 — Stats UI polish release verification

## Purpose

Prepare patch release `1.3.1` after Phase 30.

## Target files

```text
config.yaml
CHANGELOG.md
docs/CODEX_PLAN.md
```

## Tasks

1. Confirm Phase 30 is implemented and manually checked.
2. Run full backend tests:

```bash
python -m unittest discover -s tests
```

3. Run frontend checks:

```bash
cd frontend
npm run typecheck
npm run build
cd ..
```

4. Run Docker build:

```bash
docker build -t training-log:1.3.1 .
```

5. Update `config.yaml`:

```yaml
version: "1.3.1"
```

6. Update `CHANGELOG.md`:

```markdown
## 1.3.1 - YYYY-MM-DD
```

7. Mark Phase 30 and Phase 31 complete in `docs/CODEX_PLAN.md`.

## Acceptance criteria

```text
Frontend build passes.
Backend tests pass.
Docker build passes.
Stats UI manually approved.
config.yaml version is 1.3.1.
CHANGELOG has 1.3.1 section.
CODEX_PLAN marks Phase 30 and 31 complete.
```

Suggested commit message:

```text
Phase 31: release Stats UI polish 1.3.1
```

Status: completed on 2026-07-06.

Implementation notes:

- Confirmed Phase 30 is implemented in `9e59713`.
- Ran backend verification with `python3 -m unittest discover -s tests` because `python` is not available in this environment.
- Re-ran frontend typecheck and production build.
- Built Docker image `training-log:1.3.1`.
- Bumped `config.yaml` to `1.3.1` and dated the `1.3.1` changelog section.

---

# Codex prompt to use

```text
Read AGENTS.md.
Read docs/CODEX_PLAN.md.
Use:
- docs/codex-skills/skills/training-log-phase-executor/SKILL.md
- docs/codex-skills/skills/training-log-frontend-ux/SKILL.md
- docs/codex-skills/skills/training-log-stats-training-load/SKILL.md

Implement Phase 30 only: Stats UI design polish and visual system cleanup.

Important:
- Do not change backend training-load formulas.
- Do not bump config.yaml version.
- Do not start Phase 31.
- Focus on Stats UI layout and visual quality.
- Match the approved dark dashboard design direction.
- Fix the bad UI from current implementation: cramped cards, duplicated ATL/CTL/TSB rows, chunky calculation rows, wrong semantic labels, weak sparklines, and inconsistent colors.

Run:
cd frontend && npm run typecheck && npm run build

If backend files are touched, also run:
python -m unittest discover -s tests

Return:
- changed files
- screenshots/manual notes if available
- verification results
- remaining risks
```
