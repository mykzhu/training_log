import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any, Protocol
from uuid import uuid4

from app.repositories import garmin as garmin_repository
from app.services import date_service
from app.services.garmin_client import GarminClientAdapter
from app.services.garmin_insights import (
    BASELINE_DAYS as GARMIN_STATS_BASELINE_DAYS,
    MIN_BASELINE_SAMPLES as GARMIN_STATS_MIN_BASELINE_SAMPLES,
    annotate_metric_completeness,
    annotate_metrics_completeness,
    baseline_metric_stats,
    build_garmin_insight_inputs,
    classify_body_battery_start,
    classify_hrv,
    classify_overnight_recharge,
    classify_resting_heart_rate,
    classify_steps,
    classify_stress,
    metric_number,
    rounded_float,
    signal_delta,
    stats_baselines,
    stats_freshness,
    status_label,
)
from app.services.garmin_readiness_service import build_garmin_readiness_adjustment


logger = logging.getLogger("training_log")
DEFAULT_SYNC_DAYS = 35
MIN_SYNC_DAYS = 1
MAX_SYNC_DAYS = 90
GARMIN_STATS_RANGES = {"35": 35, "90": 90, "180": 180, "365": 365}
PENDING_MFA: dict[str, "PendingMfaSession"] = {}


class GarminClientProtocol(Protocol):
    def has_tokens(self) -> bool: ...
    def login(self, username: str, password: str) -> tuple[bool, Any, Any]: ...
    def resume_mfa(self, client: Any, state: Any, code: str) -> None: ...
    def connect_from_tokens(self) -> Any: ...
    def disconnect(self) -> None: ...
    def get_daily_summary(self, client: Any, metric_date: str) -> Any: ...
    def get_hrv_data(self, client: Any, metric_date: str) -> Any: ...
    def get_stress_data(self, client: Any, metric_date: str) -> Any: ...
    def get_body_battery_data(self, client: Any, metric_date: str) -> Any: ...


@dataclass
class PendingMfaSession:
    client: Any
    state: Any
    created_at: datetime


def clamp_days(days: int | None) -> int:
    days = DEFAULT_SYNC_DAYS if days is None else int(days)
    if days < MIN_SYNC_DAYS or days > MAX_SYNC_DAYS:
        raise ValueError(f"Sync days must be between {MIN_SYNC_DAYS} and {MAX_SYNC_DAYS}.")
    return days


def local_date_range(days: int, *, today: date | None = None) -> list[str]:
    today = today or date_service.app_today()
    return [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(days)
    ]


def garmin_stats_range_days(range_value: str | None) -> tuple[str, int | None]:
    normalized = str(range_value or "90").lower()
    if normalized == "all":
        return normalized, None
    if normalized not in GARMIN_STATS_RANGES:
        raise ValueError("Stats range must be one of 35, 90, 180, 365, or all.")
    return normalized, GARMIN_STATS_RANGES[normalized]


def stats_point(metric: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": metric.get("date"),
        **{column: metric.get(column) for column in garmin_repository.GARMIN_VALUE_COLUMNS},
        "is_complete": metric.get("is_complete"),
        "completeness_status": metric.get("completeness_status"),
        "completeness_message": metric.get("completeness_message"),
    }


def build_metric_signal(
    *,
    metric_key: str,
    output_metric: str | None = None,
    label: str,
    unit: str,
    source_metric: dict[str, Any] | None,
    source_date: str,
    baseline_metrics: list[dict[str, Any]],
    direction: str,
    used_for_readiness: bool,
    score_delta: int,
    classifier: Any,
    missing_message: str,
    display_only: bool = False,
    baseline_required: bool = True,
) -> dict[str, Any]:
    current = metric_number(source_metric, metric_key)
    baseline, sample_count = baseline_metric_stats(
        baseline_metrics,
        metric_key,
        exclude_date=source_date,
    )
    delta, delta_percent = signal_delta(current, baseline)

    if current is None:
        status = "missing"
        message = missing_message
    elif display_only:
        status = "display_only"
        message = f"{label} is display-only for readiness."
    elif baseline is None and baseline_required:
        status = "insufficient_baseline"
        message = f"{label} needs at least {GARMIN_STATS_MIN_BASELINE_SAMPLES} baseline samples."
    else:
        status = classifier(float(current), baseline)
        if baseline is None:
            message = f"{label} is {status_label(status).lower()} by absolute display bands."
        else:
            message = f"{label} is {status_label(status).lower()} versus your baseline."

    return {
        "metric": output_metric or metric_key,
        "label": label,
        "unit": unit,
        "source_date": source_date,
        "current": rounded_float(current, 1 if unit == "ms" else 0),
        "baseline_median": baseline,
        "baseline_sample_count": sample_count,
        "delta": delta,
        "delta_percent": delta_percent,
        "status": status,
        "direction": direction,
        "used_for_readiness": used_for_readiness,
        "score_delta": score_delta,
        "message": message,
    }


def build_derived_signal(
    *,
    metric: str,
    label: str,
    unit: str,
    source_date: str,
    current: float | None,
    status: str,
    message: str,
) -> dict[str, Any]:
    return {
        "metric": metric,
        "label": label,
        "unit": unit,
        "source_date": source_date,
        "current": rounded_float(current),
        "baseline_median": None,
        "baseline_sample_count": 0,
        "delta": None,
        "delta_percent": None,
        "status": status if current is not None else "missing",
        "direction": "contextual",
        "used_for_readiness": False,
        "score_delta": 0,
        "message": message if current is not None else f"{label} is unavailable.",
    }


def stats_overall_status(signals: list[dict[str, Any]]) -> str:
    if not any(signal.get("current") is not None for signal in signals):
        return "no_data"

    readiness_signals = [signal for signal in signals if signal.get("used_for_readiness")]
    if any(signal["status"] == "poor" for signal in readiness_signals):
        return "poor"
    if any(signal["status"] == "watch" for signal in readiness_signals):
        return "watch"
    if any(signal["status"] == "insufficient_baseline" for signal in readiness_signals):
        return "not_enough_data"
    return "good"


def stats_overall_message(
    *,
    overall_status: str,
    freshness: dict[str, Any],
    signals: list[dict[str, Any]],
) -> str:
    if overall_status == "no_data":
        return "No Garmin metrics are available for the scoring date."
    if freshness["status"] == "historical_only":
        return "Latest Garmin row is historical, so current-day recovery metrics are not scored as today."
    if freshness["status"] in {"partial_today", "partial_sync"}:
        return "Today's Garmin row is partial, so readiness uses the previous completed row."

    concerning = [
        signal["label"]
        for signal in signals
        if signal.get("used_for_readiness") and signal["status"] in {"watch", "poor"}
    ]
    if concerning:
        if len(concerning) == 1:
            return f"{concerning[0]} is outside your usual range."
        return f"{', '.join(concerning[:-1])} and {concerning[-1]} are outside your usual range."
    if overall_status == "not_enough_data":
        return "Garmin data exists, but personal baselines are still building."
    return "Garmin recovery metrics look normal for your current baseline."


def build_garmin_stats_insights(
    *,
    today: date,
    latest_metric: dict[str, Any] | None,
) -> dict[str, Any]:
    inputs = build_garmin_insight_inputs(today=today)
    adjustment = build_garmin_readiness_adjustment(
        f"{inputs.current_date}T00:00:00",
        today=today,
    )
    rules_by_metric = {rule["metric"]: rule for rule in adjustment["rules"]}
    readiness_source_date = str(adjustment.get("readiness_scoring_date") or inputs.current_date)
    readiness_metric = garmin_repository.get_daily_metric(readiness_source_date)
    previous_readiness_date = str(adjustment.get("readiness_previous_date") or inputs.previous_date)
    previous_readiness_metric = garmin_repository.get_daily_metric(previous_readiness_date)
    baseline_metrics = garmin_repository.list_daily_metrics(
        start_date=str(adjustment["baseline_start_date"]),
        end_date=str(adjustment["baseline_end_date"]),
    )

    signals = [
        build_metric_signal(
            metric_key="hrv_ms",
            label="HRV",
            unit="ms",
            source_metric=readiness_metric,
            source_date=readiness_source_date,
            baseline_metrics=baseline_metrics,
            direction="higher_is_better",
            used_for_readiness=True,
            score_delta=int(rules_by_metric.get("hrv_ms", {}).get("score_delta") or 0),
            classifier=classify_hrv,
            missing_message="No current-day HRV row for the scoring date.",
        ),
        build_metric_signal(
            metric_key="resting_heart_rate",
            label="Resting HR",
            unit="bpm",
            source_metric=readiness_metric,
            source_date=readiness_source_date,
            baseline_metrics=baseline_metrics,
            direction="lower_is_better",
            used_for_readiness=True,
            score_delta=int(rules_by_metric.get("resting_heart_rate", {}).get("score_delta") or 0),
            classifier=classify_resting_heart_rate,
            missing_message="No current-day resting heart rate row for the scoring date.",
        ),
        build_metric_signal(
            metric_key="body_battery_start",
            label="Body Battery start",
            unit="",
            source_metric=readiness_metric,
            source_date=readiness_source_date,
            baseline_metrics=baseline_metrics,
            direction="higher_is_better",
            used_for_readiness=True,
            score_delta=int(rules_by_metric.get("body_battery_start", {}).get("score_delta") or 0),
            classifier=classify_body_battery_start,
            missing_message="No current-day Body Battery start row for the scoring date.",
            baseline_required=False,
        ),
        build_metric_signal(
            metric_key="stress_avg",
            label="Previous-day stress",
            unit="",
            source_metric=previous_readiness_metric,
            source_date=previous_readiness_date,
            baseline_metrics=baseline_metrics,
            direction="lower_is_better",
            used_for_readiness=True,
            score_delta=int(rules_by_metric.get("stress_avg", {}).get("score_delta") or 0),
            classifier=classify_stress,
            missing_message="No previous-day stress row for readiness scoring.",
        ),
        build_metric_signal(
            metric_key="stress_avg",
            output_metric="current_stress_avg",
            label="Current stress",
            unit="",
            source_metric=inputs.current_metric,
            source_date=inputs.current_date,
            baseline_metrics=baseline_metrics,
            direction="contextual",
            used_for_readiness=False,
            score_delta=0,
            classifier=classify_stress,
            missing_message="No current-day stress row for display.",
            display_only=True,
            baseline_required=False,
        ),
        build_metric_signal(
            metric_key="steps",
            label="Steps",
            unit="",
            source_metric=inputs.current_metric,
            source_date=inputs.current_date,
            baseline_metrics=baseline_metrics,
            direction="contextual",
            used_for_readiness=False,
            score_delta=0,
            classifier=classify_steps,
            missing_message="No current-day step count row for display.",
            baseline_required=False,
        ),
    ]

    current_start = metric_number(inputs.current_metric, "body_battery_start")
    current_end = metric_number(inputs.current_metric, "body_battery_end")
    previous_end = metric_number(inputs.previous_metric, "body_battery_end")
    if current_start is not None and previous_end is not None:
        recharge = current_start - previous_end
        signals.append(
            build_derived_signal(
                metric="overnight_recharge",
                label="Overnight recharge",
                unit="",
                source_date=inputs.current_date,
                current=recharge,
                status=classify_overnight_recharge(recharge),
                message="Overnight recharge is derived from today's start and yesterday's end Body Battery.",
            )
        )
    if current_start is not None and current_end is not None:
        drain = current_start - current_end
        signals.append(
            build_derived_signal(
                metric="body_battery_daily_drain",
                label="Daily Body Battery drain",
                unit="",
                source_date=inputs.current_date,
                current=drain,
                status="display_only",
                message="Daily drain is informational and is not used for readiness.",
            )
        )

    freshness = stats_freshness(today=today, latest_metric=latest_metric)
    overall_status = stats_overall_status(signals)

    return {
        "current_date": inputs.current_date,
        "previous_date": inputs.previous_date,
        "baseline_start_date": adjustment["baseline_start_date"],
        "baseline_end_date": adjustment["baseline_end_date"],
        "readiness_scoring_date": adjustment["readiness_scoring_date"],
        "readiness_scoring_date_source": adjustment["readiness_scoring_date_source"],
        "readiness_previous_date": adjustment["readiness_previous_date"],
        "current_metric_completeness": adjustment["current_metric_completeness"],
        "scoring_metric_completeness": adjustment["scoring_metric_completeness"],
        "baseline_days": GARMIN_STATS_BASELINE_DAYS,
        "minimum_baseline_samples": GARMIN_STATS_MIN_BASELINE_SAMPLES,
        "freshness": freshness,
        "overall_status": overall_status,
        "overall_message": stats_overall_message(
            overall_status=overall_status,
            freshness=freshness,
            signals=signals,
        ),
        "readiness_impact": {
            "score_delta": adjustment["score_delta"],
            "raw_score_delta": adjustment["raw_score_delta"],
            "min_score_delta": adjustment["min_score_delta"],
            "max_score_delta": adjustment["max_score_delta"],
            "used_metric_count": adjustment["scored_rule_count"],
            "display_only_metric_count": sum(
                1
                for signal in signals
                if not signal["used_for_readiness"] and signal.get("current") is not None
            ),
        },
        "signals": signals,
    }


def latest_metric_summary(metric: dict[str, Any] | None) -> dict[str, str] | None:
    if metric is None:
        return None
    return {
        "date": str(metric["date"]),
        "synced_at": str(metric["synced_at"]),
        "is_complete": bool(metric.get("is_complete")),
        "completeness_status": str(metric.get("completeness_status") or ""),
        "completeness_message": str(metric.get("completeness_message") or ""),
    }


def number_from_keys(payload: Any, keys: tuple[str, ...]) -> float | None:
    if not isinstance(payload, dict):
        return None

    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)

    return None


def nested_number(payload: Any, paths: tuple[tuple[str, ...], ...]) -> float | None:
    for path in paths:
        current = payload
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if isinstance(current, (int, float)):
            return float(current)

    return None


def integer_or_none(value: float | None) -> int | None:
    return int(round(value)) if value is not None else None


def describe_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {
            "type": "object",
            "keys": sorted(str(key) for key in payload.keys())[:30],
        }
    if isinstance(payload, list):
        item_types = sorted({type(item).__name__ for item in payload[:10]})
        return {"type": "array", "length": len(payload), "item_types": item_types}
    return {"type": type(payload).__name__}


def extract_resting_heart_rate(summary: Any) -> int | None:
    return integer_or_none(
        number_from_keys(
            summary,
            (
                "restingHeartRate",
                "restingHR",
                "restingHeartRateInBeatsPerMinute",
                "minHeartRate",
            ),
        )
    )


def extract_steps(summary: Any) -> int | None:
    return integer_or_none(number_from_keys(summary, ("totalSteps", "steps")))


def extract_hrv_ms(hrv_payload: Any) -> float | None:
    value = number_from_keys(
        hrv_payload,
        ("lastNightAvg", "weeklyAvg", "hrvValue", "average"),
    )
    if value is not None:
        return value

    return nested_number(
        hrv_payload,
        (
            ("hrvSummary", "lastNightAvg"),
            ("hrvSummary", "weeklyAvg"),
            ("hrvSummary", "average"),
        ),
    )


def extract_stress_avg(stress_payload: Any) -> int | None:
    direct = number_from_keys(
        stress_payload,
        ("avgStressLevel", "averageStressLevel", "stressAvg", "stressLevel"),
    )
    if direct is not None:
        return integer_or_none(direct)

    values: list[float] = []
    arrays = []
    if isinstance(stress_payload, dict):
        for key in ("stressValuesArray", "stressValues", "values"):
            value = stress_payload.get(key)
            if isinstance(value, list):
                arrays.append(value)
    elif isinstance(stress_payload, list):
        arrays.append(stress_payload)

    for array in arrays:
        for item in array:
            candidate: Any = None
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                candidate = item[-1]
            elif isinstance(item, dict):
                candidate = item.get("stressLevel") or item.get("value")
            elif isinstance(item, (int, float)):
                candidate = item

            if isinstance(candidate, (int, float)) and candidate >= 0:
                values.append(float(candidate))

    return integer_or_none(mean(values)) if values else None


BODY_BATTERY_ARRAY_KEYS = (
    "bodyBatteryValuesArray",
    "bodyBatteryValues",
    "bodyBatteryValueDescriptorDTOList",
    "bodyBatteryReadingDTOList",
    "values",
)
BODY_BATTERY_VALUE_KEYS = (
    "bodyBatteryValue",
    "bodyBatteryLevel",
    "bodyBattery",
    "value",
    "level",
    "percentage",
)


def body_battery_number(value: Any) -> int | None:
    if isinstance(value, (int, float)) and 0 <= value <= 100:
        return int(round(value))
    return None


def body_battery_value_from_item(item: Any) -> int | None:
    candidate = body_battery_number(item)
    if candidate is not None:
        return candidate

    if isinstance(item, (list, tuple)):
        for child in reversed(item):
            candidate = body_battery_number(child)
            if candidate is not None:
                return candidate
        return None

    if not isinstance(item, dict):
        return None

    for key in BODY_BATTERY_VALUE_KEYS:
        candidate = body_battery_number(item.get(key))
        if candidate is not None:
            return candidate

    for key in ("descriptor", "valueDescriptorDTO", "bodyBatteryValueDescriptorDTO"):
        nested = item.get(key)
        if isinstance(nested, dict):
            candidate = body_battery_value_from_item(nested)
            if candidate is not None:
                return candidate

    return None


def body_battery_values(body_battery_payload: Any) -> list[int]:
    sources: list[Any] = []
    if isinstance(body_battery_payload, list):
        sources.append(body_battery_payload)
    elif isinstance(body_battery_payload, dict):
        for key in BODY_BATTERY_ARRAY_KEYS:
            value = body_battery_payload.get(key)
            if isinstance(value, list):
                sources.append(value)

        nested = body_battery_payload.get("bodyBattery")
        if isinstance(nested, (dict, list)) and not sources:
            return body_battery_values(nested)

    values: list[int] = []
    for source in sources:
        if not isinstance(source, list):
            continue
        for item in source:
            candidate = body_battery_value_from_item(item)
            if candidate is not None:
                values.append(candidate)

    return values


def extract_body_battery(body_battery_payload: Any) -> tuple[int | None, int | None]:
    start = integer_or_none(
        number_from_keys(
            body_battery_payload,
            (
                "bodyBatteryStart",
                "bodyBatteryStarting",
                "bodyBatteryStartValue",
                "bodyBatteryAtStart",
                "bodyBatteryAtWakeTime",
                "bodyBatteryWakeupValue",
                "bodyBatteryHighestValue",
                "startBodyBattery",
                "startValue",
                "morningBodyBattery",
            ),
        )
    )
    end = integer_or_none(
        number_from_keys(
            body_battery_payload,
            (
                "bodyBatteryEnd",
                "bodyBatteryEnding",
                "bodyBatteryEndValue",
                "bodyBatteryAtEnd",
                "bodyBatteryMostRecentValue",
                "bodyBatteryLatestValue",
                "bodyBatteryLowestValue",
                "endBodyBattery",
                "endValue",
                "currentValue",
                "latestValue",
            ),
        )
    )
    values = body_battery_values(body_battery_payload)
    if values:
        start = values[0] if start is None else start
        end = values[-1] if end is None else end

    return start, end


class GarminService:
    def __init__(self, client: GarminClientProtocol | None = None) -> None:
        self.client = client or GarminClientAdapter()

    def status(self) -> dict[str, Any]:
        today = date_service.app_today()
        return {
            "connected": self.client.has_tokens(),
            "last_synced_at": garmin_repository.get_last_synced_at(),
            "latest_metric": annotate_metric_completeness(
                garmin_repository.get_latest_metric(),
                today=today,
            ),
            "pending_mfa": bool(PENDING_MFA),
        }

    def login(self, username: str, password: str) -> dict[str, Any]:
        if not username or not password:
            raise ValueError("Garmin username and password are required.")

        mfa_required, client, state = self.client.login(username, password)
        if mfa_required:
            mfa_token = uuid4().hex
            PENDING_MFA[mfa_token] = PendingMfaSession(
                client=client,
                state=state,
                created_at=datetime.now(),
            )
            return {
                "connected": False,
                "mfa_required": True,
                "mfa_token": mfa_token,
            }

        if not self.client.has_tokens():
            raise RuntimeError("Garmin login succeeded but tokens were not saved.")

        return {
            "connected": True,
            "mfa_required": False,
            "mfa_token": None,
        }

    def submit_mfa(self, mfa_token: str, code: str) -> dict[str, Any]:
        session = PENDING_MFA.pop(mfa_token, None)
        if session is None:
            raise ValueError("Garmin MFA session is not available.")
        if not code.strip():
            raise ValueError("Garmin MFA code is required.")

        self.client.resume_mfa(session.client, session.state, code.strip())
        return {"connected": True, "mfa_required": False, "mfa_token": None}

    def disconnect(self) -> dict[str, Any]:
        self.client.disconnect()
        PENDING_MFA.clear()
        return self.status()

    def sync(self, days: int | None = None, *, today: date | None = None) -> dict[str, Any]:
        sync_days = clamp_days(days)
        client = self.client.connect_from_tokens()
        saved_dates: list[str] = []
        skipped_dates: list[str] = []
        errors: dict[str, str] = {}

        for metric_date in local_date_range(sync_days, today=today):
            metric = self.fetch_daily_metric(client, metric_date)
            if any(metric.get(column) is not None for column in garmin_repository.GARMIN_VALUE_COLUMNS):
                garmin_repository.upsert_daily_metric(metric)
                saved_dates.append(metric_date)
            else:
                skipped_dates.append(metric_date)

            diagnostics = metric.get("raw_diagnostics") or {}
            for source, source_diagnostics in diagnostics.items():
                if isinstance(source_diagnostics, dict) and "error" in source_diagnostics:
                    errors[f"{metric_date}:{source}"] = str(source_diagnostics["error"])

        logger.info(
            "garmin.sync.done days=%s saved=%s skipped=%s errors=%s",
            sync_days,
            len(saved_dates),
            len(skipped_dates),
            len(errors),
        )
        return {
            "synced": True,
            "days": sync_days,
            "saved_dates": saved_dates,
            "skipped_dates": skipped_dates,
            "errors": errors,
            "status": self.status(),
        }

    def fetch_daily_metric(self, client: Any, metric_date: str) -> dict[str, Any]:
        synced_at = datetime.now().isoformat(timespec="seconds")
        diagnostics: dict[str, dict[str, Any]] = {}
        payloads: dict[str, Any] = {}

        fetchers = {
            "summary": self.client.get_daily_summary,
            "hrv": self.client.get_hrv_data,
            "stress": self.client.get_stress_data,
            "body_battery": self.client.get_body_battery_data,
        }

        for source, fetcher in fetchers.items():
            try:
                payload = fetcher(client, metric_date)
                payloads[source] = payload
                diagnostics[source] = {"ok": True, **describe_payload(payload)}
            except Exception as exc:  # Keep partial syncs useful.
                diagnostics[source] = {"ok": False, "error": str(exc)}

        body_battery_start, body_battery_end = extract_body_battery(
            payloads.get("body_battery")
        )
        if body_battery_start is None or body_battery_end is None:
            summary_start, summary_end = extract_body_battery(payloads.get("summary"))
            body_battery_start = (
                summary_start if body_battery_start is None else body_battery_start
            )
            body_battery_end = summary_end if body_battery_end is None else body_battery_end

        return {
            "date": metric_date,
            "resting_heart_rate": extract_resting_heart_rate(payloads.get("summary")),
            "hrv_ms": extract_hrv_ms(payloads.get("hrv")),
            "stress_avg": extract_stress_avg(payloads.get("stress")),
            "body_battery_start": body_battery_start,
            "body_battery_end": body_battery_end,
            "steps": extract_steps(payloads.get("summary")),
            "synced_at": synced_at,
            "raw_diagnostics": diagnostics,
        }

    def list_daily(self, days: int | None = None, *, today: date | None = None) -> dict[str, Any]:
        sync_days = clamp_days(days)
        today = today or date_service.app_today()
        start_date = (today - timedelta(days=sync_days - 1)).isoformat()
        return {
            "days": sync_days,
            "metrics": annotate_metrics_completeness(
                garmin_repository.list_daily_metrics(start_date=start_date),
                today=today,
            ),
        }

    def stats(
        self,
        range_value: str = "90",
        *,
        today: date | None = None,
    ) -> dict[str, Any]:
        selected_range, expected_days = garmin_stats_range_days(range_value)
        today = today or date_service.app_today()

        if expected_days is None:
            start_date = None
            end_date = None
        else:
            start_date = (today - timedelta(days=expected_days - 1)).isoformat()
            end_date = today.isoformat()

        metrics = garmin_repository.list_daily_metrics_chronological(
            start_date=start_date,
            end_date=end_date,
        )
        metrics = annotate_metrics_completeness(metrics, today=today)
        series = [stats_point(metric) for metric in metrics]

        if expected_days is None:
            date_from = metrics[0]["date"] if metrics else None
            date_to = metrics[-1]["date"] if metrics else None
            baseline_end_date = today - timedelta(days=1)
            missing_days = None
        else:
            date_from = start_date
            date_to = end_date
            baseline_end_date = today - timedelta(days=1)
            missing_days = max(expected_days - len(metrics), 0)

        coverage = {
            "expected_days": expected_days,
            "available_days": len(metrics),
            "missing_days": missing_days,
        }
        latest_metric = annotate_metric_completeness(
            garmin_repository.get_latest_metric(),
            today=today,
        )

        return {
            "range": selected_range,
            "date_from": date_from,
            "date_to": date_to,
            "metric_count": len(metrics),
            "coverage": coverage,
            "latest_metric": latest_metric_summary(latest_metric),
            "series": series,
            "baselines": stats_baselines(
                metrics,
                baseline_end_date=baseline_end_date,
            ),
            "insights": build_garmin_stats_insights(
                today=today,
                latest_metric=latest_metric,
            ),
        }

    def recovery_snapshot(self, *, today: date | None = None) -> dict[str, Any]:
        local_date_source = "explicit_today" if today is not None else "configured_timezone_today"
        today = today or date_service.app_today()
        previous_day = today - timedelta(days=1)
        today_date = today.isoformat()
        previous_date = previous_day.isoformat()
        today_metric = annotate_metric_completeness(
            garmin_repository.get_daily_metric(today_date),
            today=today,
        )
        yesterday_metric = annotate_metric_completeness(
            garmin_repository.get_daily_metric(previous_date),
            today=today,
        )
        latest_metric = annotate_metric_completeness(
            garmin_repository.get_latest_metric(),
            today=today,
        )
        sample_start = (today - timedelta(days=34)).isoformat()
        connected = self.client.has_tokens()
        freshness_status = self._snapshot_freshness_status(
            connected=connected,
            today_metric=today_metric,
            latest_metric=latest_metric,
        )

        return {
            "connected": connected,
            "today": today_metric,
            "yesterday": yesterday_metric,
            "latest": latest_metric,
            "last_synced_at": garmin_repository.get_last_synced_at(),
            "sample_count_35d": garmin_repository.get_metric_count_since(sample_start),
            "current_date": today_date,
            "previous_date": previous_date,
            "local_date_source": local_date_source,
            "today_present": today_metric is not None,
            "yesterday_present": yesterday_metric is not None,
            "latest_metric_date": str(latest_metric["date"]) if latest_metric else None,
            "freshness_status": freshness_status,
            "missing_today_metrics": self._missing_today_metrics(today_metric),
            "message": self._snapshot_message(freshness_status, today_metric),
        }

    def _snapshot_freshness_status(
        self,
        *,
        connected: bool,
        today_metric: dict[str, Any] | None,
        latest_metric: dict[str, Any] | None,
    ) -> str:
        if today_metric is not None:
            if today_metric.get("is_complete") is False:
                return str(today_metric.get("completeness_status") or "partial_today")
            return "today_synced"
        if latest_metric is not None:
            return "historical_only"
        if connected:
            return "connected_not_synced"
        return "not_connected"

    def _snapshot_message(
        self,
        freshness_status: str,
        today_metric: dict[str, Any] | None = None,
    ) -> str:
        if freshness_status in {"partial_today", "partial_sync"} and today_metric:
            return str(
                today_metric.get("completeness_message")
                or "Today's Garmin row is partial."
            )
        if freshness_status == "today_synced":
            return "Today synced"
        if freshness_status == "historical_only":
            return "Historical only - not scored as today"
        if freshness_status == "connected_not_synced":
            return "Connected, not synced"
        return "Not connected"

    def _missing_today_metrics(self, today_metric: dict[str, Any] | None) -> list[str]:
        if today_metric is None:
            return ["Resting HR", "HRV", "Body Battery start", "Current stress"]

        checks = (
            ("resting_heart_rate", "Resting HR"),
            ("hrv_ms", "HRV"),
            ("body_battery_start", "Body Battery start"),
            ("stress_avg", "Current stress"),
        )
        return [
            label
            for key, label in checks
            if not isinstance(today_metric.get(key), (int, float))
        ]


garmin_service = GarminService()
