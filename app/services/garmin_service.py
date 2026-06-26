import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean, median
from typing import Any, Protocol
from uuid import uuid4

from app.repositories import garmin as garmin_repository
from app.services.garmin_client import GarminClientAdapter


logger = logging.getLogger("training_log")
DEFAULT_SYNC_DAYS = 35
MIN_SYNC_DAYS = 1
MAX_SYNC_DAYS = 90
GARMIN_STATS_RANGES = {"35": 35, "90": 90, "180": 180, "365": 365}
GARMIN_STATS_BASELINE_DAYS = 28
GARMIN_STATS_MIN_BASELINE_SAMPLES = 7
GARMIN_STATS_BASELINE_COLUMNS = (
    "resting_heart_rate",
    "hrv_ms",
    "stress_avg",
    "steps",
)
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
    today = today or date.today()
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
    }


def rounded_median(values: list[float]) -> float | None:
    if len(values) < GARMIN_STATS_MIN_BASELINE_SAMPLES:
        return None
    return round(float(median(values)), 2)


def stats_baselines(
    metrics: list[dict[str, Any]],
    *,
    baseline_end_date: date | None,
) -> dict[str, float | None]:
    if baseline_end_date is None:
        baseline_metrics: list[dict[str, Any]] = []
    else:
        baseline_start = (
            baseline_end_date - timedelta(days=GARMIN_STATS_BASELINE_DAYS - 1)
        ).isoformat()
        baseline_end = baseline_end_date.isoformat()
        baseline_metrics = [
            metric
            for metric in metrics
            if baseline_start <= str(metric.get("date")) <= baseline_end
        ]

    baselines: dict[str, float | None] = {}
    for column in GARMIN_STATS_BASELINE_COLUMNS:
        values = [
            float(metric[column])
            for metric in baseline_metrics
            if isinstance(metric.get(column), (int, float))
        ]
        baselines[column] = rounded_median(values)

    return baselines


def latest_metric_summary(metric: dict[str, Any] | None) -> dict[str, str] | None:
    if metric is None:
        return None
    return {"date": str(metric["date"]), "synced_at": str(metric["synced_at"])}


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


def body_battery_values(body_battery_payload: Any) -> list[int]:
    source = body_battery_payload
    if isinstance(body_battery_payload, dict):
        for key in ("bodyBatteryValuesArray", "bodyBatteryValues", "values"):
            if isinstance(body_battery_payload.get(key), list):
                source = body_battery_payload[key]
                break

    values: list[int] = []
    if not isinstance(source, list):
        return values

    for item in source:
        candidate: Any = None
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            candidate = item[-1]
        elif isinstance(item, dict):
            candidate = item.get("bodyBatteryValue") or item.get("value")
        elif isinstance(item, (int, float)):
            candidate = item

        if isinstance(candidate, (int, float)):
            values.append(int(round(candidate)))

    return values


def extract_body_battery(body_battery_payload: Any) -> tuple[int | None, int | None]:
    start = integer_or_none(
        number_from_keys(
            body_battery_payload,
            ("bodyBatteryStart", "bodyBatteryStarting", "startValue"),
        )
    )
    end = integer_or_none(
        number_from_keys(
            body_battery_payload,
            ("bodyBatteryEnd", "bodyBatteryEnding", "endValue"),
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
        return {
            "connected": self.client.has_tokens(),
            "last_synced_at": garmin_repository.get_last_synced_at(),
            "latest_metric": garmin_repository.get_latest_metric(),
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
        today = today or date.today()
        start_date = (today - timedelta(days=sync_days - 1)).isoformat()
        return {
            "days": sync_days,
            "metrics": garmin_repository.list_daily_metrics(start_date=start_date),
        }

    def stats(
        self,
        range_value: str = "90",
        *,
        today: date | None = None,
    ) -> dict[str, Any]:
        selected_range, expected_days = garmin_stats_range_days(range_value)
        today = today or date.today()

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
        series = [stats_point(metric) for metric in metrics]

        if expected_days is None:
            date_from = metrics[0]["date"] if metrics else None
            date_to = metrics[-1]["date"] if metrics else None
            baseline_end_date = (
                datetime.fromisoformat(str(date_to)).date() if date_to else None
            )
            missing_days = None
        else:
            date_from = start_date
            date_to = end_date
            baseline_end_date = today
            missing_days = max(expected_days - len(metrics), 0)

        return {
            "range": selected_range,
            "date_from": date_from,
            "date_to": date_to,
            "metric_count": len(metrics),
            "coverage": {
                "expected_days": expected_days,
                "available_days": len(metrics),
                "missing_days": missing_days,
            },
            "latest_metric": latest_metric_summary(garmin_repository.get_latest_metric()),
            "series": series,
            "baselines": stats_baselines(
                metrics,
                baseline_end_date=baseline_end_date,
            ),
        }

    def recovery_snapshot(self, *, today: date | None = None) -> dict[str, Any]:
        today = today or date.today()
        today_metric = garmin_repository.get_daily_metric(today.isoformat())
        yesterday_metric = garmin_repository.get_daily_metric(
            (today - timedelta(days=1)).isoformat()
        )
        latest_metric = garmin_repository.get_latest_metric()
        sample_start = (today - timedelta(days=34)).isoformat()

        return {
            "connected": self.client.has_tokens(),
            "today": today_metric,
            "yesterday": yesterday_metric,
            "latest": latest_metric,
            "last_synced_at": garmin_repository.get_last_synced_at(),
            "sample_count_35d": garmin_repository.get_metric_count_since(sample_start),
            "message": self._snapshot_message(today_metric, latest_metric),
        }

    def _snapshot_message(
        self,
        today_metric: dict[str, Any] | None,
        latest_metric: dict[str, Any] | None,
    ) -> str:
        if today_metric is not None:
            return "Today synced"
        if latest_metric is not None:
            return "Latest Garmin data is historical"
        if self.client.has_tokens():
            return "Connected, not synced"
        return "Not connected"


garmin_service = GarminService()