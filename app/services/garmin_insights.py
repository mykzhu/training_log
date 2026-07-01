from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median
from typing import Any

from app.repositories import garmin as garmin_repository
from app.services import date_service


BASELINE_DAYS = 28
MIN_BASELINE_SAMPLES = 7
BASELINE_COLUMNS = (
    "resting_heart_rate",
    "hrv_ms",
    "stress_avg",
    "body_battery_start",
    "steps",
)


@dataclass(frozen=True)
class GarminInsightInputs:
    current_date: str
    previous_date: str
    baseline_start_date: str
    baseline_end_date: str
    local_date_source: str
    current_metric: dict[str, Any] | None
    previous_metric: dict[str, Any] | None
    baseline_metrics: list[dict[str, Any]]


def parse_as_of_date_with_source(as_of: str | None) -> tuple[date, str]:
    return date_service.parse_local_date_from_as_of(as_of)


def parse_as_of_date(as_of: str | None) -> date:
    return parse_as_of_date_with_source(as_of)[0]


def build_garmin_insight_inputs(
    *,
    as_of: str | None = None,
    today: date | None = None,
) -> GarminInsightInputs:
    if today is not None:
        as_of_date = today
        local_date_source = "explicit_today"
    else:
        as_of_date, local_date_source = parse_as_of_date_with_source(as_of)

    current_date = as_of_date.isoformat()
    previous_date = (as_of_date - timedelta(days=1)).isoformat()
    baseline_start = (as_of_date - timedelta(days=BASELINE_DAYS)).isoformat()
    baseline_end = previous_date

    return GarminInsightInputs(
        current_date=current_date,
        previous_date=previous_date,
        baseline_start_date=baseline_start,
        baseline_end_date=baseline_end,
        local_date_source=local_date_source,
        current_metric=garmin_repository.get_daily_metric(current_date),
        previous_metric=garmin_repository.get_daily_metric(previous_date),
        baseline_metrics=garmin_repository.list_daily_metrics(
            start_date=baseline_start,
            end_date=baseline_end,
        ),
    )


def metric_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def metric_number(metric: dict[str, Any] | None, key: str) -> float | None:
    if metric is None:
        return None
    value = metric.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def metric_values(
    metrics: list[dict[str, Any]],
    metric_key: str,
    *,
    exclude_date: str | None = None,
) -> list[float]:
    values: list[float] = []
    for metric in metrics:
        if exclude_date is not None and metric.get("date") == exclude_date:
            continue

        value = metric.get(metric_key)
        if isinstance(value, (int, float)):
            values.append(float(value))

    return values


def rounded_value(value: float | None) -> float | None:
    if value is None:
        return None

    return round(float(value), 2)


def rounded_float(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def rounded_median(values: list[float]) -> float | None:
    if len(values) < MIN_BASELINE_SAMPLES:
        return None
    return rounded_value(float(median(values)))


def baseline_metric_stats(
    baseline_metrics: list[dict[str, Any]],
    key: str,
    *,
    exclude_date: str | None = None,
) -> tuple[float | None, int]:
    values = metric_values(baseline_metrics, key, exclude_date=exclude_date)
    if len(values) < MIN_BASELINE_SAMPLES:
        return None, len(values)
    return rounded_value(float(median(values))), len(values)


def stats_baselines(
    metrics: list[dict[str, Any]],
    *,
    baseline_end_date: date | None,
) -> dict[str, float | None]:
    if baseline_end_date is None:
        baseline_metrics: list[dict[str, Any]] = []
    else:
        baseline_start = (
            baseline_end_date - timedelta(days=BASELINE_DAYS - 1)
        ).isoformat()
        baseline_end = baseline_end_date.isoformat()
        baseline_metrics = [
            metric
            for metric in metrics
            if baseline_start <= str(metric.get("date")) <= baseline_end
        ]

    return {
        column: rounded_median(metric_values(baseline_metrics, column))
        for column in BASELINE_COLUMNS
    }


def signal_delta(current: float | None, baseline: float | None) -> tuple[float | None, float | None]:
    if current is None or baseline is None:
        return None, None
    delta = round(float(current) - float(baseline), 2)
    delta_percent = None if baseline == 0 else round((delta / float(baseline)) * 100, 2)
    return delta, delta_percent


def classify_hrv(current: float, baseline: float) -> str:
    if current >= baseline * 1.05:
        return "good"
    if current >= baseline * 0.95:
        return "normal"
    if current >= baseline * 0.85:
        return "watch"
    return "poor"


def classify_resting_heart_rate(current: float, baseline: float) -> str:
    diff = current - baseline
    if diff <= -3:
        return "good"
    if diff <= 3:
        return "normal"
    if diff <= 7:
        return "watch"
    return "poor"


def classify_body_battery_start(current: float, baseline: float | None) -> str:
    if baseline is None:
        if current <= 25:
            return "poor"
        if current <= 50:
            return "watch"
        if current <= 75:
            return "normal"
        return "good"
    diff = current - baseline
    if diff >= 10:
        return "good"
    if diff >= -10:
        return "normal"
    if diff >= -25:
        return "watch"
    return "poor"


def classify_stress(current: float, baseline: float) -> str:
    diff = current - baseline
    if diff <= -10:
        return "good"
    if diff <= 10:
        return "normal"
    if diff <= 20:
        return "watch"
    return "poor"


def classify_steps(current: float, baseline: float | None) -> str:
    if baseline is None or baseline <= 0:
        return "display_only"
    ratio = current / baseline
    if ratio > 1.2:
        return "good"
    if ratio >= 0.8:
        return "normal"
    return "watch"


def classify_overnight_recharge(current: float) -> str:
    if current >= 35:
        return "good"
    if current >= 20:
        return "normal"
    if current >= 10:
        return "watch"
    return "poor"


def status_label(status: str) -> str:
    return {
        "good": "Good",
        "normal": "Normal",
        "watch": "Watch",
        "poor": "Poor",
        "missing": "Missing",
        "insufficient_baseline": "Not enough baseline",
        "display_only": "Display only",
    }.get(status, status.replace("_", " ").title())


def stats_freshness(
    *,
    today: date,
    latest_metric: dict[str, Any] | None,
) -> dict[str, Any]:
    latest_date = metric_date(latest_metric.get("date") if latest_metric else None)
    days_since = (today - latest_date).days if latest_date is not None else None
    if latest_date == today:
        status = "fresh"
        message = "Today synced"
    elif latest_date is not None:
        status = "historical_only"
        message = "Historical only - not scored as today"
    else:
        status = "missing"
        message = "No Garmin rows synced"

    return {
        "status": status,
        "latest_metric_date": latest_date.isoformat() if latest_date else None,
        "days_since_latest_metric": days_since,
        "message": message,
    }
