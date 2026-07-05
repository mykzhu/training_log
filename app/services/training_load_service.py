from __future__ import annotations

from datetime import date, timedelta
from math import sqrt
from typing import Any

MetricStatus = str

ATL_DAYS = 7
CTL_DAYS = 42
REFERENCE_SAMPLE_MIN = 20


def parse_workout_date(workout: dict[str, Any]) -> date:
    value = workout.get("date") or str(workout.get("created_at", ""))[:10]
    return date.fromisoformat(str(value)[:10])


def date_range(start: date, end: date) -> list[date]:
    if end < start:
        return []

    days = (end - start).days
    return [start + timedelta(days=index) for index in range(days + 1)]


def percentile_95(values: list[float]) -> float | None:
    if not values:
        return None

    sorted_values = sorted(values)
    if len(sorted_values) < REFERENCE_SAMPLE_MIN:
        return max(sorted_values)

    position = (len(sorted_values) - 1) * 0.95
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + ((upper - lower) * fraction)


def ewma(values: list[float], window_days: int) -> list[float]:
    if not values:
        return []

    alpha = 1 / window_days
    current = values[0]
    points = [current]

    for value in values[1:]:
        current = (value * alpha) + (current * (1 - alpha))
        points.append(current)

    return points


def format_value(value: float | None, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "No data"

    return f"{value:.{digits}f}{suffix}"


def atl_status(value: float | None) -> MetricStatus:
    if value is None:
        return "neutral"
    if value < 40:
        return "info"
    if value < 70:
        return "good"
    if value < 90:
        return "watch"
    return "bad"


def tsb_status(value: float | None) -> MetricStatus:
    if value is None:
        return "neutral"
    if value > 10:
        return "info"
    if value >= -10:
        return "good"
    if value >= -25:
        return "watch"
    return "bad"


def ratio_status(value: float | None) -> MetricStatus:
    if value is None:
        return "neutral"
    if value < 0.8:
        return "watch"
    if value <= 1.3:
        return "good"
    if value <= 1.5:
        return "watch"
    return "bad"


def monotony_status(value: float | None) -> MetricStatus:
    if value is None:
        return "neutral"
    if value < 1:
        return "good"
    if value <= 2:
        return "watch"
    return "bad"


def metric(
    *,
    key: str,
    label: str,
    description: str,
    value: float | None,
    formatted: str,
    status: MetricStatus,
    percent: float | None = None,
    min_value: float = 0,
    max_value: float = 100,
    zones: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "description": description,
        "value": value,
        "formatted": formatted,
        "status": status,
        "percent": percent,
        "min": min_value,
        "max": max_value,
        "zones": zones or [],
    }


def build_training_load_summary(
    workouts: list[dict[str, Any]],
    today: date,
) -> dict[str, Any]:
    if not workouts:
        return {
            "latest_date": None,
            "daily_load": [],
            "series": [],
            "weekly_load": None,
            "weekly_mean": None,
            "weekly_std": None,
            "monotony": None,
            "strain": None,
            "atl_reference": None,
            "ctl_reference": None,
            "metrics": empty_metrics(),
        }

    daily: dict[date, float] = {}
    for workout in workouts:
        workout_date = parse_workout_date(workout)
        daily[workout_date] = daily.get(workout_date, 0.0) + float(
            workout.get("load_score") or 0.0
        )

    start_date = min(daily)
    end_date = max(max(daily), today)
    dates = date_range(start_date, end_date)
    loads = [daily.get(day, 0.0) for day in dates]
    atl_values = ewma(loads, ATL_DAYS)
    ctl_values = ewma(loads, CTL_DAYS)
    tsb_values = [
        ctl - atl for atl, ctl in zip(atl_values, ctl_values, strict=True)
    ]

    atl_reference = percentile_95([value for value in atl_values if value > 0])
    ctl_reference = percentile_95([value for value in ctl_values if value > 0])
    latest_atl = atl_values[-1] if atl_values else None
    latest_ctl = ctl_values[-1] if ctl_values else None
    latest_tsb = tsb_values[-1] if tsb_values else None
    ac_ratio = (
        latest_atl / latest_ctl
        if latest_atl is not None and latest_ctl is not None and latest_ctl > 0
        else None
    )
    atl_percent = (
        latest_atl / atl_reference * 100
        if latest_atl is not None and atl_reference
        else None
    )
    ctl_percent = (
        latest_ctl / ctl_reference * 100
        if latest_ctl is not None and ctl_reference
        else None
    )

    recent_loads = loads[-7:]
    weekly_load = sum(recent_loads)
    weekly_mean = weekly_load / len(recent_loads) if recent_loads else None
    weekly_std = None
    monotony = None
    strain = None

    if weekly_mean is not None and recent_loads:
        variance = sum((value - weekly_mean) ** 2 for value in recent_loads) / len(
            recent_loads
        )
        weekly_std = sqrt(variance)
        if weekly_std > 0:
            monotony = weekly_mean / weekly_std
            strain = weekly_load * monotony

    series = []
    for index, day in enumerate(dates):
        atl = atl_values[index]
        ctl = ctl_values[index]
        atl_day_percent = atl / atl_reference * 100 if atl_reference else None
        ctl_day_percent = ctl / ctl_reference * 100 if ctl_reference else None
        series.append(
            {
                "date": day.isoformat(),
                "load": loads[index],
                "atl": atl,
                "ctl": ctl,
                "tsb": tsb_values[index],
                "ac_ratio": atl / ctl if ctl > 0 else None,
                "atl_percent": atl_day_percent,
                "ctl_percent": ctl_day_percent,
            }
        )

    return {
        "latest_date": dates[-1].isoformat(),
        "daily_load": [
            {"date": day.isoformat(), "load": load}
            for day, load in zip(dates, loads, strict=True)
        ],
        "series": series,
        "weekly_load": weekly_load,
        "weekly_mean": weekly_mean,
        "weekly_std": weekly_std,
        "monotony": monotony,
        "strain": strain,
        "atl_reference": atl_reference,
        "ctl_reference": ctl_reference,
        "metrics": build_metrics(
            atl=latest_atl,
            atl_percent=atl_percent,
            ctl=latest_ctl,
            ctl_percent=ctl_percent,
            tsb=latest_tsb,
            ac_ratio=ac_ratio,
            monotony=monotony,
            strain=strain,
            weekly_load=weekly_load,
        ),
    }


def empty_metrics() -> list[dict[str, Any]]:
    return build_metrics(
        atl=None,
        atl_percent=None,
        ctl=None,
        ctl_percent=None,
        tsb=None,
        ac_ratio=None,
        monotony=None,
        strain=None,
        weekly_load=None,
    )


def build_metrics(
    *,
    atl: float | None,
    atl_percent: float | None,
    ctl: float | None,
    ctl_percent: float | None,
    tsb: float | None,
    ac_ratio: float | None,
    monotony: float | None,
    strain: float | None,
    weekly_load: float | None,
) -> list[dict[str, Any]]:
    return [
        metric(
            key="atl",
            label="Fatigue (ATL)",
            description="Short-term fatigue from the 7-day load curve.",
            value=atl,
            formatted=format_value(atl, 1),
            status=atl_status(atl_percent),
            percent=atl_percent,
            zones=load_zones(),
        ),
        metric(
            key="ctl",
            label="Fitness (CTL)",
            description="Longer-term base from the 42-day load curve.",
            value=ctl,
            formatted=format_value(ctl, 1),
            status=atl_status(ctl_percent),
            percent=ctl_percent,
            zones=load_zones(),
        ),
        metric(
            key="tsb",
            label="Stress Balance (TSB)",
            description="Fitness minus fatigue; positive values are fresher.",
            value=tsb,
            formatted=format_value(tsb, 1),
            status=tsb_status(tsb),
            min_value=-40,
            max_value=40,
            zones=tsb_zones(),
        ),
        metric(
            key="ac_ratio",
            label="Workload Ratio (AC)",
            description="Acute load divided by chronic load.",
            value=ac_ratio,
            formatted=format_value(ac_ratio, 2),
            status=ratio_status(ac_ratio),
            min_value=0,
            max_value=2,
            zones=ratio_zones(),
        ),
        metric(
            key="monotony",
            label="Monotony",
            description="How repetitive the last 7 days of load were.",
            value=monotony,
            formatted=format_value(monotony, 2),
            status=monotony_status(monotony),
            min_value=0,
            max_value=3,
            zones=monotony_zones(),
        ),
        metric(
            key="training_strain",
            label="Training strain",
            description="Weekly load multiplied by monotony.",
            value=strain,
            formatted=format_value(strain, 1),
            status=monotony_status(monotony),
            percent=(
                strain / (weekly_load * 2) * 100
                if strain is not None and weekly_load and weekly_load > 0
                else None
            ),
            zones=load_zones(),
        ),
    ]


def load_zones() -> list[dict[str, Any]]:
    return [
        {"from_value": 0, "to_value": 40, "status": "info", "label": "Low"},
        {"from_value": 40, "to_value": 70, "status": "good", "label": "Productive"},
        {"from_value": 70, "to_value": 90, "status": "watch", "label": "High"},
        {"from_value": 90, "to_value": 100, "status": "bad", "label": "Very high"},
    ]


def tsb_zones() -> list[dict[str, Any]]:
    return [
        {"from_value": -40, "to_value": -25, "status": "bad", "label": "Very fatigued"},
        {"from_value": -25, "to_value": -10, "status": "watch", "label": "Fatigued"},
        {"from_value": -10, "to_value": 10, "status": "good", "label": "Balanced"},
        {"from_value": 10, "to_value": 40, "status": "info", "label": "Fresh"},
    ]


def ratio_zones() -> list[dict[str, Any]]:
    return [
        {"from_value": 0, "to_value": 0.8, "status": "watch", "label": "Low"},
        {"from_value": 0.8, "to_value": 1.3, "status": "good", "label": "Good"},
        {"from_value": 1.3, "to_value": 1.5, "status": "watch", "label": "High"},
        {"from_value": 1.5, "to_value": 2, "status": "bad", "label": "Risky"},
    ]


def monotony_zones() -> list[dict[str, Any]]:
    return [
        {"from_value": 0, "to_value": 1, "status": "good", "label": "Varied"},
        {"from_value": 1, "to_value": 2, "status": "watch", "label": "Repetitive"},
        {"from_value": 2, "to_value": 3, "status": "bad", "label": "Monotonous"},
    ]
