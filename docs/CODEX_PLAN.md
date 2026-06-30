# Training Log — Garmin Recovery and Stats Detailed Codex Plan

Repository: `mykzhu/training_log`  
Target branch: latest `master`  
Purpose: replace or extend the Garmin phases in `docs/CODEX_PLAN.md`.

This version intentionally expands the Garmin work beyond the previous high-level plan. It includes concrete backend payloads, UI sections, metric ranges, chart behavior, tests, and acceptance criteria.

---

## Execution rule for Codex

1. Pull latest `master`.
2. Re-read `docs/CODEX_PLAN.md` and current Garmin/recovery code before editing.
3. Execute only the first unchecked phase unless explicitly told otherwise.
4. Keep each branch focused.
5. Do not mix unrelated stats refactors, release work, or UI redesign into Garmin explainability.
6. Do not commit runtime databases, Garmin tokens, logs, private Garmin payloads, or local generated artifacts.
7. Report changed files, tests, builds, manual checks, and known gaps.

---

## Hard Garmin constraints

- Garmin network calls are allowed only for explicit login/MFA/sync actions.
- Rendering `/`, `/garmin`, recommendations, stats, or recovery context must never contact Garmin.
- Garmin credentials must not be stored in SQLite, backup payloads, frontend storage, logs, URLs, or diagnostics.
- `raw_diagnostics` may remain in local debug/daily payloads if already present, but must not be returned from stats/insights endpoints.
- Garmin readiness must remain based on local persisted daily metrics.
- Current-date RHR, HRV, and Body Battery start are eligible for scoring.
- Current-day stress is display-only because a partial day is not comparable to full-day history.
- Previous-day stress is eligible for scoring.
- Steps are informational for now; do not score steps into readiness unless a later phase explicitly changes this.
- Garmin metrics must not be passed into per-exercise target logic.
- Existing safety caps after Garmin adjustment must remain in force.
- Do not change scoring thresholds unless tests expose a concrete bug.

---

# Recommended next Garmin work

## [x] Phase 14 — Garmin recovery explainability and local-date correctness

Branch:

```text
fix/garmin-readiness-explainability
```

### Goal

Make the Current Workout “Next workout” and “Garmin recovery” cards explain exactly why Garmin changed readiness, why it did not change readiness, or why data is missing/stale.

Also make the Garmin scoring date explicit and safe for Home Assistant deployments in Ukraine.

### Problem to solve

Current code already computes a structured `garmin_adjustment` with per-metric rules, but the UI mostly shows only:

```text
Garmin adj: -N
Garmin: Garmin recovery metrics reduce readiness.
```

That is not enough. The user should be able to see:

- which date is treated as “today”;
- which baseline window is used;
- which metrics were scored;
- which metrics were missing;
- which metrics had insufficient baseline samples;
- which metrics were display-only;
- how raw Garmin delta was clamped;
- why stale/historical latest data did not score as current.

### Backend: local date helper

Add app timezone configuration.

Suggested default:

```python
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Uzhgorod")
```

Add a focused helper, for example:

```python
# app/services/date_service.py

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app import config

def app_today() -> date:
    return datetime.now(ZoneInfo(config.APP_TIMEZONE)).date()

def parse_local_date_from_as_of(as_of: str | None) -> tuple[date, str]:
    if as_of:
        try:
            return datetime.fromisoformat(str(as_of)).date(), "as_of"
        except ValueError:
            pass
    return app_today(), "configured_timezone_today"
```

Use this helper in:

- `garmin_readiness_service.parse_as_of_date()` or replacement;
- `garmin_service.local_date_range()` when no test `today` is passed;
- `garmin_service.stats()` when no test `today` is passed;
- `garmin_service.recovery_snapshot()` when no test `today` is passed.

Keep tests deterministic by allowing `today` and/or `as_of` injection.

### Backend: enrich `garmin_adjustment`

Keep the existing `rules` array.

Add top-level fields:

```python
{
    "applied": bool,
    "status": "positive" | "negative" | "neutral" | "display_only" | "insufficient_baseline" | "not_available",
    "score_delta": int,
    "raw_score_delta": int,
    "min_score_delta": -20,
    "max_score_delta": 10,

    "current_date": "2026-06-27",
    "previous_date": "2026-06-26",
    "baseline_start_date": "2026-05-30",
    "baseline_end_date": "2026-06-26",
    "baseline_days": 28,
    "minimum_baseline_samples": 7,
    "local_date_source": "as_of" | "configured_timezone_today",

    "available_rule_count": 4,
    "scored_rule_count": 3,
    "missing_rule_count": 1,
    "insufficient_baseline_rule_count": 0,
    "display_only_rule_count": 1,

    "scored_metrics_summary": "HRV -6, RHR -6, previous-day stress -5",
    "summary": "Garmin recovery metrics reduce readiness.",
    "rules": [...]
}
```

Each rule should stay renderable:

```python
{
    "metric": "hrv_ms",
    "label": "HRV",
    "source_date": "2026-06-27",
    "current": 35.0,
    "baseline_median": 42.0,
    "baseline_sample_count": 21,
    "score_delta": -6,
    "status": "scored" | "neutral" | "missing_current" | "missing_baseline" | "insufficient_baseline" | "display_only",
    "message": "HRV is below baseline."
}
```

### Frontend: Next Workout Garmin detail block

In `CurrentWorkoutPage.tsx`, replace the single Garmin summary paragraph with a compact detail section.

Suggested layout:

```text
Garmin adjustment: -17
Status: negative
Window: today 2026-06-27, baseline 2026-05-30..2026-06-26

Scored
  HRV: 35 ms vs 42 ms median — -6
  Resting HR: 67 bpm vs 60 bpm median — -6
  Previous-day stress: 68 vs 40 median — -5

Not scored
  Body Battery start: missing today
  Current stress: 45 — display-only partial day

Clamp
  Raw -17, applied -17, bounds -20..+10
```

Rules:

- Show current value, baseline median, sample count, status, source date, and score delta.
- Show `display_only` clearly for current stress.
- Show `missing_current` clearly when today’s metric is absent.
- Show `insufficient_baseline` clearly when fewer than 7 baseline samples exist.
- Show `raw_score_delta` vs `score_delta` and clamp bounds.
- Keep the default view compact on mobile.
- Use `<details>` / expandable panel if the card becomes too tall.
- Do not duplicate full `/garmin` charts inside Current Workout.
- Add a link to `/garmin`.

### Frontend: Garmin Recovery card improvements

Current “Garmin recovery” card should show freshness, not just latest values.

Add:

```text
Garmin: connected/off
Scoring date: Jun 27
Today: present / missing
Yesterday: present / missing
Latest synced row: Jun 26
35d samples: 28
Status: today synced / historical only / connected, not synced / not connected
```

Rules:

- If latest data is historical, show: “Historical only — not scored as today.”
- If today is missing, show what is missing.
- Keep “Sync 35 days”.
- Add a `/garmin` link.

### Backend tests

Add or update tests for:

- configured timezone local date is used when no `as_of` is passed;
- explicit `as_of` wins over configured timezone today;
- current-date RHR scores only when current local date row exists;
- current-date HRV scores only when current local date row exists;
- current-date Body Battery start scores only when current local date row exists;
- previous-day stress uses local previous date;
- current-day stress remains display-only;
- stale historical latest metric is displayed but not scored;
- insufficient baseline counts are correct;
- missing-current counts are correct;
- display-only counts are correct;
- `scored_metrics_summary` is stable;
- no-Garmin behavior remains unchanged;
- positive Garmin delta is still capped by short-gap safety rule;
- negative Garmin delta respects clamp lower bound;
- no Garmin client/network method is called from recommendation/current-workout reads.

### Frontend checks

```bash
cd frontend
npm run typecheck
npm run build
```

### Manual smoke

```text
Current page with no Garmin data
Current page with connected but never synced Garmin
Current page with historical-only Garmin data
Current page with insufficient baseline
Current page with positive Garmin adjustment
Current page with negative Garmin adjustment
Current page with clamped Garmin adjustment
Current page on mobile width
/garmin link from Current page
Settings Garmin sync/login still works
```

### Acceptance criteria

- User can tell exactly why Garmin changed readiness.
- User can tell exactly why Garmin did not change readiness.
- Stale/historical Garmin data is visible but not incorrectly scored as today.
- Current stress is clearly display-only.
- No raw diagnostics are exposed in UI.
- No Garmin network request occurs during Current Workout/recommendation rendering.
- Existing Garmin readiness score behavior is unchanged except local-date correctness.

---

## [ ] Phase 15 — Garmin Stats insights and better metric representation

Branch:

```text
feat/garmin-stats-insights
```

### Goal

Turn `/garmin` from a raw chart page into an interpretation page.

The page should still show charts, but it should answer:

```text
Are today’s recovery metrics normal for me?
Which metric is the biggest concern?
Is the data fresh enough to trust?
Which values are good / warning / poor?
Which metrics affect readiness and which are only informational?
```

### Problem to solve

Current `/garmin` already has:

- range selector;
- sync button;
- latest date and sync cards;
- available/missing day cards;
- HRV chart with median/balanced band;
- resting HR chart with baseline bands;
- Body Battery start/end chart;
- stress chart with bands;
- steps chart with median baseline.

But it lacks:

- a top-level interpretation;
- per-metric status chips;
- deltas versus baseline in summary cards;
- clear freshness status;
- readiness impact explanation;
- 7-day trend overlays;
- Body Battery recharge/drain;
- missing-data/freshness hints.

### Backend: add stats insights object

Extend `GET /api/v1/garmin/stats?range=...`.

Keep existing fields:

```python
{
    "range": ...,
    "date_from": ...,
    "date_to": ...,
    "metric_count": ...,
    "coverage": ...,
    "latest_metric": ...,
    "series": ...,
    "baselines": ...
}
```

Add:

```python
{
    "insights": {
        "current_date": "2026-06-27",
        "previous_date": "2026-06-26",
        "baseline_start_date": "2026-05-30",
        "baseline_end_date": "2026-06-26",
        "baseline_days": 28,
        "minimum_baseline_samples": 7,
        "freshness": {
            "status": "fresh" | "historical_only" | "missing" | "not_connected",
            "latest_metric_date": "2026-06-27",
            "days_since_latest_metric": 0,
            "message": "Today synced"
        },
        "overall_status": "good" | "watch" | "poor" | "not_enough_data" | "no_data",
        "overall_message": "HRV and resting HR are worse than baseline.",
        "readiness_impact": {
            "score_delta": -12,
            "raw_score_delta": -12,
            "min_score_delta": -20,
            "max_score_delta": 10,
            "used_metric_count": 3,
            "display_only_metric_count": 2
        },
        "signals": []
    }
}
```

Each `signals[]` item:

```python
{
    "metric": "hrv_ms",
    "label": "HRV",
    "unit": "ms",
    "source_date": "2026-06-27",
    "current": 35.0,
    "baseline_median": 42.0,
    "baseline_sample_count": 21,
    "delta": -7.0,
    "delta_percent": -16.67,
    "status": "good" | "normal" | "watch" | "poor" | "missing" | "insufficient_baseline" | "display_only",
    "direction": "higher_is_better" | "lower_is_better" | "contextual",
    "used_for_readiness": true,
    "score_delta": -6,
    "message": "HRV is below your baseline."
}
```

### Backend: status heuristics

Use personal baseline zones, not universal medical critical values.

#### HRV

Higher than baseline is usually better, but too much “better” should not be over-celebrated.

Suggested zones:

```text
good:   current >= baseline * 1.05
normal: baseline * 0.95 <= current < baseline * 1.05
watch:  baseline * 0.85 <= current < baseline * 0.95
poor:   current < baseline * 0.85
```

For chart shading:

```text
poor:   below baseline * 0.85
watch:  baseline * 0.85 .. baseline * 0.95
normal: baseline * 0.95 .. baseline * 1.05
good:   above baseline * 1.05
```

#### Resting heart rate

Lower or stable is generally better.

Suggested zones:

```text
good:   current <= baseline - 3 bpm
normal: baseline - 2 .. baseline + 3 bpm
watch:  baseline + 4 .. baseline + 7 bpm
poor:   current >= baseline + 8 bpm
```

Chart shading:

```text
good/normal: <= baseline + 3
watch:       baseline + 4 .. baseline + 7
poor:        >= baseline + 8
```

#### Body Battery start

Use baseline-relative morning value.

Suggested zones:

```text
good:   current >= baseline + 10
normal: baseline - 10 .. baseline + 9
watch:  baseline - 25 .. baseline - 11
poor:   current <= baseline - 26
```

If no Body Battery baseline exists, fall back to simple absolute display bands:

```text
low:      0..25
limited:  26..50
ok:       51..75
high:     76..100
```

#### Body Battery drain / recharge

Derived values:

```python
daily_drain = body_battery_start - body_battery_end
overnight_recharge = today.body_battery_start - yesterday.body_battery_end
```

Add these to insights only when both required values exist.

Suggested labels:

```text
overnight recharge:
  good:   >= +35
  normal: +20 .. +34
  watch:  +10 .. +19
  poor:   < +10

daily drain:
  informational only
```

Do not score these into readiness yet unless a later phase explicitly changes scoring.

#### Stress average

For readiness, use previous-day stress, not partial current-day stress.

Suggested zones relative to baseline:

```text
good:   current <= baseline - 10
normal: baseline - 9 .. baseline + 10
watch:  baseline + 11 .. baseline + 20
poor:   current >= baseline + 21
```

Absolute background bands for chart remain useful:

```text
rest/very low: 0..25
low:           26..50
medium:        51..75
high:          76..100
```

#### Steps

Steps should remain informational.

Suggested zones relative to baseline:

```text
very_low: current < baseline * 0.5
low:      baseline * 0.5 .. baseline * 0.8
normal:   baseline * 0.8 .. baseline * 1.2
high:     current > baseline * 1.2
```

Rules:

- Do not include steps in readiness score.
- Show “low steps” as context, not as a recovery penalty.
- Low steps can mean rest, travel, illness, or inactivity.

### Frontend: new top section

Add this above the charts:

```text
Garmin overview

Status: Watch
Message: HRV is below baseline and resting HR is elevated.
Freshness: Today synced
Range: 90 days
Coverage: 82/90 days
Baseline: 28-day median, 21 valid samples
Readiness impact: -12
```

Use compact cards:

```text
[Overall] Watch
[Readiness impact] -12
[Freshness] Today synced
[Coverage] 82/90
[Baseline] 21 samples
```

### Frontend: Today readiness signals strip

Add a horizontal or responsive grid:

```text
Today readiness signals

HRV
35 ms
-16.7% vs 42 ms median
Poor
Used: -6

Resting HR
67 bpm
+7 bpm vs 60 median
Watch
Used: -6

Body Battery start
42
-26 vs 68 median
Poor
Used: -6

Previous-day stress
68
+23 vs 45 median
Poor
Used: -5

Current stress
45
Display-only partial day
Not scored

Steps
4,200
-46% vs 7,800 median
Informational
```

Rules:

- Use status chips: `Good`, `Normal`, `Watch`, `Poor`, `Missing`, `Not enough baseline`, `Display only`.
- Make the source date visible for each signal.
- Show baseline sample count in a tooltip or subtitle.
- Use the same labels in `/garmin` and Current Workout.

### Frontend: readiness impact panel

Add a panel that mirrors the recommendation Garmin adjustment:

```text
Readiness impact

Used for readiness:
✓ HRV: -6
✓ Resting HR: -6
✓ Body Battery start: 0
✓ Previous-day stress: -5

Display only:
• Current stress: partial day
• Steps: informational

Result:
Raw Garmin delta: -17
Applied Garmin delta: -17
Clamp: -20..+10
```

If no current-date data:

```text
Readiness impact
No current Garmin row for Jun 27. Latest row is Jun 26, so HRV/RHR/Body Battery are shown as historical but not scored as today.
```

### Frontend: chart upgrades

#### Shared chart rules

- Always show baseline median when available.
- Add legend explaining zones.
- Use consistent status names across all charts.
- Missing values should stay as gaps, not zero.
- Highlight the latest point.
- Highlight the scoring date and previous-day stress date.
- Tooltips should show:
  - date;
  - metric value;
  - baseline median;
  - delta vs baseline;
  - status;
  - whether it is used for readiness.

#### HRV chart

Keep median and baseline band, but improve zones:

```text
poor:   < baseline * 0.85
watch:  0.85x .. 0.95x
normal: 0.95x .. 1.05x
good:   > 1.05x
```

Add:

- 7-day rolling median line;
- latest point status chip;
- “used for readiness today” marker.

#### Resting HR chart

Add:

- 7-day rolling average line;
- zones based on baseline:
  - normal <= baseline + 3;
  - watch baseline +4..+7;
  - poor >= baseline +8;
- latest point label like `+7 bpm`;
- combined warning if latest RHR is high and latest HRV is low.

#### Body Battery chart

Keep start/end lines, add:

- horizontal zones:
  - 0..25 low;
  - 26..50 limited;
  - 51..75 okay;
  - 76..100 high;
- optional bar below chart for daily drain;
- optional derived card:
  - overnight recharge;
  - daily drain;
  - morning value vs baseline.

#### Stress chart

Keep stress bands and bar colors.

Add:

- 7-day average line;
- previous-day stress marker;
- high-stress day count in selected range;
- average stress in selected range;
- show current-day stress separately as display-only.

#### Steps chart

Add:

- 7-day average line;
- 28-day median line;
- 7-day total;
- average/day;
- days below 50% baseline;
- make it visually neutral/informational, not recovery-negative.

### Frontend: mobile behavior

- Signal cards should become a one-column list on narrow screens.
- Readiness impact details can be collapsed by default.
- Chart legends should wrap.
- Avoid huge fixed-height sections.
- Keep sync/range controls easy to tap.

### API/type work

Update:

- `app/schemas.py`
- `app/services/garmin_service.py`
- `app/routes/api_garmin.py`
- `docs/openapi.json`
- `frontend/src/api/generated.ts`
- `frontend/src/api/types.ts`
- `frontend/src/pages/GarminStatsPage.tsx`
- CSS in `frontend/src/styles.css`

Run the API contract generator if that is the repo convention:

```bash
python scripts/generate_api_contracts.py
```

### Backend tests

Add tests for:

- `/api/v1/garmin/stats` includes `insights`;
- no `raw_diagnostics` in stats response;
- fresh current date status;
- historical-only status;
- missing/no-data status;
- HRV good/normal/watch/poor;
- RHR good/normal/watch/poor;
- Body Battery good/normal/watch/poor;
- previous-day stress good/normal/watch/poor;
- current stress display-only;
- steps informational only;
- insufficient baseline;
- missing current metric;
- baseline sample count per metric;
- derived Body Battery recharge when values exist;
- no Body Battery recharge when values are missing;
- 7-day rolling values if computed backend-side;
- endpoint never calls Garmin client/network methods.

### Frontend checks

```bash
cd frontend
npm run typecheck
npm run build
```

### Manual smoke

```text
/garmin with no rows
/garmin with 1..6 rows
/garmin with enough baseline
/garmin with missing HRV
/garmin with missing Body Battery
/garmin with historical-only latest row
/garmin positive-looking day
/garmin negative-looking day
/garmin mobile width
/garmin range 35
/garmin range 90
/garmin range 180
/garmin range 365
/garmin range all
Sync button invalidates Garmin stats/status
Settings link works
Current Workout link to /garmin works
```

### Acceptance criteria

- `/garmin` answers whether current Garmin metrics look normal for the user.
- Critical-looking values are highlighted relative to personal baseline.
- HRV and RHR statuses are not based on generic population thresholds.
- Current stress is clearly display-only.
- Steps are clearly informational.
- Stale/historical data is visible but not treated as current readiness data.
- Users can understand Garmin readiness impact without opening developer tools.
- No Garmin raw diagnostics are exposed.
- No Garmin network request occurs during `/garmin` rendering.
- Frontend typecheck/build passes.
- Backend tests pass.

---

## [ ] Phase 16 — Garmin insights reuse and cleanup

Branch:

```text
refactor/garmin-insights-shared
```

### Goal

Avoid two independent Garmin interpretation systems.

After Phase 14 and Phase 15, ensure Current Workout and `/garmin` use shared backend insight/status logic.

### Tasks

- Extract shared Garmin signal classification helpers.
- Reuse signal status names in readiness and stats.
- Ensure Current Workout and `/garmin` agree on:
  - scoring date;
  - previous-day stress date;
  - baseline window;
  - status labels;
  - baseline sample counts;
  - display-only logic;
  - freshness logic.
- Add regression tests proving both endpoints classify the same fixture consistently.

### Acceptance criteria

- No duplicated threshold tables in React.
- No disagreement between `/garmin` and Current Workout for the same data.
- Shared backend helpers have focused unit tests.
- Existing UI behavior remains unchanged except consistency improvements.

---

## [ ] Phase 17 — Stats page componentization

Branch:

```text
refactor/stats-page-components
```

Only after Garmin explainability and insights are stable.

### Goal

Split the large global stats page without changing behavior.

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
- do not mix global Stats refactor with Garmin Stats work.

---

## [ ] Phase 18 — Next release

Branch:

```text
chore/release-next
```

Required checks:

```bash
python -m unittest discover -s tests
cd frontend
npm ci
npm run typecheck
npm run build
cd ..
docker build -t training-log:release-candidate .
```

Manual smoke matrix:

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

Release tasks:

- update README;
- update changelog;
- update docs;
- update add-on version according to actual delivered scope;
- confirm `docs/openapi.json` is current;
- scan repository, fixtures, logs, DB exports, backups, and docs for secrets;
- confirm no runtime SQLite database or Garmin token file is tracked.
