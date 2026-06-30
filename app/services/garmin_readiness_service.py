from datetime import date, datetime, timedelta
from statistics import median
from typing import Any, Callable

from app.repositories import garmin as garmin_repository
from app.services import date_service


BASELINE_DAYS = 28
MIN_BASELINE_SAMPLES = 7
MIN_GARMIN_DELTA = -20
MAX_GARMIN_DELTA = 10

MetricDeltaFunction = Callable[[float, float], tuple[int, str]]


def parse_as_of_date_with_source(as_of: str | None) -> tuple[date, str]:
    return date_service.parse_local_date_from_as_of(as_of)


def parse_as_of_date(as_of: str | None) -> date:
    return parse_as_of_date_with_source(as_of)[0]


def clamp_garmin_delta(value: int) -> int:
    return max(MIN_GARMIN_DELTA, min(MAX_GARMIN_DELTA, value))


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


def hrv_delta(current: float, baseline: float) -> tuple[int, str]:
    ratio = (current - baseline) / baseline if baseline > 0 else 0
    if ratio <= -0.20:
        return -10, "HRV is much below baseline."
    if ratio <= -0.10:
        return -6, "HRV is below baseline."
    if ratio >= 0.10:
        return 4, "HRV is above baseline."
    if ratio >= 0.05:
        return 2, "HRV is slightly above baseline."
    return 0, "HRV is close to baseline."


def resting_heart_rate_delta(current: float, baseline: float) -> tuple[int, str]:
    diff = current - baseline
    if diff >= 10:
        return -10, "Resting heart rate is much above baseline."
    if diff >= 5:
        return -6, "Resting heart rate is above baseline."
    if diff <= -5:
        return 4, "Resting heart rate is below baseline."
    if diff <= -3:
        return 2, "Resting heart rate is slightly below baseline."
    return 0, "Resting heart rate is close to baseline."


def body_battery_delta(current: float, baseline: float) -> tuple[int, str]:
    diff = current - baseline
    if diff <= -30:
        return -10, "Body Battery start is much below baseline."
    if diff <= -20:
        return -6, "Body Battery start is below baseline."
    if diff >= 20:
        return 4, "Body Battery start is above baseline."
    if diff >= 10:
        return 2, "Body Battery start is slightly above baseline."
    return 0, "Body Battery start is close to baseline."


def previous_day_stress_delta(current: float, baseline: float) -> tuple[int, str]:
    diff = current - baseline
    if diff >= 25:
        return -8, "Previous-day stress was much above baseline."
    if diff >= 15:
        return -5, "Previous-day stress was above baseline."
    if diff <= -20:
        return 3, "Previous-day stress was below baseline."
    if diff <= -10:
        return 2, "Previous-day stress was slightly below baseline."
    return 0, "Previous-day stress was close to baseline."


def build_metric_rule(
    *,
    metric: dict[str, Any] | None,
    metric_key: str,
    label: str,
    baseline_metrics: list[dict[str, Any]],
    source_date: str,
    delta_function: MetricDeltaFunction,
) -> dict[str, Any]:
    baseline_values = metric_values(
        baseline_metrics,
        metric_key,
        exclude_date=source_date,
    )
    baseline_median = median(baseline_values) if baseline_values else None
    current_value = metric.get(metric_key) if metric is not None else None

    rule = {
        "metric": metric_key,
        "label": label,
        "source_date": source_date,
        "current": current_value if isinstance(current_value, (int, float)) else None,
        "baseline_median": rounded_value(baseline_median),
        "baseline_sample_count": len(baseline_values),
        "score_delta": 0,
        "status": "missing_current",
        "message": f"{label} is unavailable for scoring.",
    }

    if not isinstance(current_value, (int, float)):
        return rule

    if len(baseline_values) < MIN_BASELINE_SAMPLES:
        rule["status"] = "insufficient_baseline"
        rule["message"] = f"{label} needs at least {MIN_BASELINE_SAMPLES} baseline samples."
        return rule

    if baseline_median is None or baseline_median <= 0:
        rule["status"] = "missing_baseline"
        rule["message"] = f"{label} has no usable baseline."
        return rule

    delta, message = delta_function(float(current_value), float(baseline_median))
    rule["score_delta"] = delta
    rule["status"] = "scored" if delta != 0 else "neutral"
    rule["message"] = message
    return rule


def build_current_stress_display_rule(
    *,
    current_metric: dict[str, Any] | None,
    baseline_metrics: list[dict[str, Any]],
    current_date: str,
) -> dict[str, Any]:
    baseline_values = metric_values(baseline_metrics, "stress_avg")
    baseline_median = median(baseline_values) if baseline_values else None
    current_value = current_metric.get("stress_avg") if current_metric else None

    return {
        "metric": "current_stress_avg",
        "label": "Current stress",
        "source_date": current_date,
        "current": current_value if isinstance(current_value, (int, float)) else None,
        "baseline_median": rounded_value(baseline_median),
        "baseline_sample_count": len(baseline_values),
        "score_delta": 0,
        "status": "display_only" if isinstance(current_value, (int, float)) else "missing_current",
        "message": (
            "Current-day stress is partial and display-only."
            if isinstance(current_value, (int, float))
            else "Current-day stress is unavailable."
        ),
    }


def adjustment_summary(score_delta: int, scored_rules: list[dict[str, Any]]) -> str:
    if score_delta < 0:
        return "Garmin recovery metrics reduce readiness."
    if score_delta > 0:
        return "Garmin recovery metrics improve readiness."
    if scored_rules:
        return "Garmin recovery metrics are close to baseline."
    return "Garmin readiness adjustment was not scored."


def adjustment_status(
    *,
    score_delta: int,
    rules: list[dict[str, Any]],
    has_available_metric: bool,
) -> str:
    if score_delta < 0:
        return "negative"
    if score_delta > 0:
        return "positive"
    if any(rule["status"] in {"scored", "neutral"} for rule in rules):
        return "neutral"
    if has_available_metric and any(
        rule["status"] == "insufficient_baseline" for rule in rules
    ):
        return "insufficient_baseline"
    if has_available_metric:
        return "display_only"
    return "not_available"


def has_rule_value(rule: dict[str, Any]) -> bool:
    return isinstance(rule.get("current"), (int, float))


def format_signed_delta(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def scored_metrics_summary(scored_rules: list[dict[str, Any]]) -> str:
    changed_rules = [rule for rule in scored_rules if int(rule.get("score_delta") or 0) != 0]
    if not changed_rules:
        return "No Garmin metric changed readiness."

    return ", ".join(
        f"{rule['label']} {format_signed_delta(int(rule['score_delta']))}"
        for rule in changed_rules
    )


def build_garmin_readiness_adjustment(as_of: str | None = None) -> dict[str, Any]:
    as_of_date, local_date_source = parse_as_of_date_with_source(as_of)
    current_date = as_of_date.isoformat()
    previous_date = (as_of_date - timedelta(days=1)).isoformat()
    baseline_start = (as_of_date - timedelta(days=BASELINE_DAYS)).isoformat()
    baseline_end = previous_date

    current_metric = garmin_repository.get_daily_metric(current_date)
    previous_metric = garmin_repository.get_daily_metric(previous_date)
    baseline_metrics = garmin_repository.list_daily_metrics(
        start_date=baseline_start,
        end_date=baseline_end,
    )

    rules = [
        build_metric_rule(
            metric=current_metric,
            metric_key="resting_heart_rate",
            label="Resting heart rate",
            baseline_metrics=baseline_metrics,
            source_date=current_date,
            delta_function=resting_heart_rate_delta,
        ),
        build_metric_rule(
            metric=current_metric,
            metric_key="hrv_ms",
            label="HRV",
            baseline_metrics=baseline_metrics,
            source_date=current_date,
            delta_function=hrv_delta,
        ),
        build_metric_rule(
            metric=current_metric,
            metric_key="body_battery_start",
            label="Body Battery start",
            baseline_metrics=baseline_metrics,
            source_date=current_date,
            delta_function=body_battery_delta,
        ),
        build_current_stress_display_rule(
            current_metric=current_metric,
            baseline_metrics=baseline_metrics,
            current_date=current_date,
        ),
        build_metric_rule(
            metric=previous_metric,
            metric_key="stress_avg",
            label="Previous-day stress",
            baseline_metrics=baseline_metrics,
            source_date=previous_date,
            delta_function=previous_day_stress_delta,
        ),
    ]

    raw_delta = sum(int(rule["score_delta"]) for rule in rules)
    score_delta = clamp_garmin_delta(raw_delta)
    scored_rules = [rule for rule in rules if rule["status"] in {"scored", "neutral"}]
    has_available_metric = any(has_rule_value(rule) for rule in rules)

    return {
        "applied": score_delta != 0,
        "status": adjustment_status(
            score_delta=score_delta,
            rules=rules,
            has_available_metric=has_available_metric,
        ),
        "score_delta": score_delta,
        "raw_score_delta": raw_delta,
        "min_score_delta": MIN_GARMIN_DELTA,
        "max_score_delta": MAX_GARMIN_DELTA,
        "baseline_days": BASELINE_DAYS,
        "minimum_baseline_samples": MIN_BASELINE_SAMPLES,
        "current_date": current_date,
        "previous_date": previous_date,
        "baseline_start_date": baseline_start,
        "baseline_end_date": baseline_end,
        "local_date_source": local_date_source,
        "available_rule_count": sum(1 for rule in rules if has_rule_value(rule)),
        "scored_rule_count": len(scored_rules),
        "missing_rule_count": sum(1 for rule in rules if rule["status"] == "missing_current"),
        "insufficient_baseline_rule_count": sum(
            1 for rule in rules if rule["status"] == "insufficient_baseline"
        ),
        "display_only_rule_count": sum(1 for rule in rules if rule["status"] == "display_only"),
        "scored_metrics_summary": scored_metrics_summary(scored_rules),
        "summary": adjustment_summary(score_delta, scored_rules),
        "rules": rules,
    }
