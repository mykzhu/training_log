---
name: training-log-stats-training-load
description: Use this when implementing or reviewing Training Log Stats, metric cards, chart formatting, and training-load calculations such as ATL, CTL, TSB, AC ratio, monotony, and strain.
---

# Training Log Stats and Training Load Skill

## When to use

Use for:

```text
StatsPage
stats_service.py
training load model
ATL / CTL / TSB
AC ratio
monotony
training strain
chart X-axis dates
metric cards
progress/range bars
sparklines
```

## Core design decision

This app is primarily strength-training focused.

Do not blindly copy cardio-only models based on TRIMP.

Use the app's existing workout load points as the base.

```text
daily_load[date] = sum of all workout load points for that local app date
```

Include zero-load rest days in time series.

## Training-load formulas

### ATL

```text
ATL = 7-day EWMA of daily_load
```

### CTL

```text
CTL = 42-day EWMA of daily_load
```

### TSB

```text
TSB = CTL - ATL
```

Positive TSB means fresher. Negative TSB means more fatigued.

### AC ratio

```text
AC ratio = ATL / CTL, if CTL > 0 else null
```

### EWMA update

Use time-constant style:

```python
today_value = yesterday_value + (daily_load - yesterday_value) / window_days
```

### ATL percent

Do not normalize only by all-time max.

Prefer:

```text
atl_reference_max = historical 95th percentile ATL
fallback = max ATL if not enough samples
fallback = null if no data
```

Then:

```text
atl_percent = atl / atl_reference_max * 100
```

### Monotony and strain

Use last 7 local days:

```text
weekly_load = sum(last_7_daily_loads)
mean_load = average(last_7_daily_loads)
std_load = standard deviation(last_7_daily_loads)
monotony = mean_load / std_load if std_load > 0 else None
training_strain = weekly_load * monotony if monotony is not None else None
```

If std is zero, do not crash and do not show infinity.

## Status zones

### ATL percent

```text
0–40%: low
40–70%: good/normal
70–90%: watch/high
90%+: bad/very high
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
1.3–1.5: watch/high
>1.5: bad/risky spike
```

### Monotony

```text
<1.0: good/varied
1.0–2.0: watch/moderate
>2.0: bad/high monotony
```

## UI representation

Use 3 levels:

```text
1. Top summary card
2. Compact visual inside card
3. Detailed chart/panel
```

### Visual choices

```text
Progress bar: bounded 0-100 metrics like recovery or ATL %
Range bar: zone-based metrics like TSB, AC ratio, monotony
Sparkline: trends like weekly load, strength progress, back pain trend
Line chart: ATL / CTL / TSB grouped Training load status
```

Do not add unsupported cardio metrics:

```text
VO2max
Marathon Shape
Race predictor
```

## Chart date formatting

Stats date axes should be consistent.

Desktop:

```text
03 Jul
10 Jul
17 Jul
```

Mobile:

```text
03.07
10.07
17.07
```

Tooltip:

```text
03 Jul 2026
```

No raw ISO dates on axes.

## Empty state

Stats page must not crash with:

```text
- no workouts
- one workout
- no load data
- no Garmin data
```

Show:

```text
No data yet
Insufficient data
```

## Tests to add

Backend:

```text
EWMA calculation
zero-load days included
TSB = CTL - ATL
AC ratio null when CTL is zero
ATL reference max fallback
monotony/strain no crash on zero std
empty data no crash
```

Frontend/manual:

```text
metric cards render
training load chart renders
mobile date labels readable
unsupported cardio metrics absent
```
