import asyncio
import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app import config
from app.repositories import garmin_sync_settings
from app.services import date_service
from app.services.garmin_service import garmin_service


logger = logging.getLogger("training_log")
SYNC_AFTER_PATTERN = re.compile(r"^\d{2}:\d{2}$")
_auto_sync_lock: asyncio.Lock | None = None
_auto_sync_lock_loop: asyncio.AbstractEventLoop | None = None
_stop_event: asyncio.Event | None = None


def app_timezone() -> ZoneInfo:
    return date_service.app_timezone()


def now_in_app_timezone() -> datetime:
    return datetime.now(app_timezone())


def parse_sync_after(value: str) -> time:
    if not SYNC_AFTER_PATTERN.fullmatch(value):
        raise ValueError("Sync time must be a valid HH:MM local time.")
    try:
        parsed = datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError("Sync time must be a valid HH:MM local time.") from exc
    return parsed


def local_date_from_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=app_timezone())
    return parsed.astimezone(app_timezone()).date()


def sanitize_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:300]}"


def auto_sync_lock() -> asyncio.Lock:
    global _auto_sync_lock, _auto_sync_lock_loop
    loop = asyncio.get_running_loop()
    if _auto_sync_lock is None or _auto_sync_lock_loop is not loop:
        _auto_sync_lock = asyncio.Lock()
        _auto_sync_lock_loop = loop
    return _auto_sync_lock


def next_eligible_auto_sync_at(
    settings: dict[str, Any],
    now_local: datetime | None = None,
) -> datetime | None:
    if not settings["enabled"]:
        return None

    now_local = now_local or now_in_app_timezone()
    sync_time = parse_sync_after(str(settings["sync_after_local_time"]))
    today_candidate = datetime.combine(now_local.date(), sync_time, tzinfo=now_local.tzinfo)
    last_success_date = local_date_from_iso(settings.get("last_success_at"))
    last_attempt_date = local_date_from_iso(settings.get("last_attempt_at"))

    if last_success_date == now_local.date() or last_attempt_date == now_local.date():
        return today_candidate + timedelta(days=1)
    return today_candidate


def is_auto_sync_due(
    settings: dict[str, Any],
    *,
    connected: bool,
    now_local: datetime | None = None,
) -> bool:
    if not settings["enabled"]:
        logger.info("garmin.auto_sync.skip reason=disabled")
        return False
    if not connected:
        logger.info("garmin.auto_sync.skip reason=disconnected")
        return False

    now_local = now_local or now_in_app_timezone()
    if now_local.time() < parse_sync_after(str(settings["sync_after_local_time"])):
        logger.info("garmin.auto_sync.skip reason=not_due")
        return False

    today = now_local.date()
    if local_date_from_iso(settings.get("last_attempt_at")) == today:
        logger.info("garmin.auto_sync.skip reason=attempted_today")
        return False
    if local_date_from_iso(settings.get("last_success_at")) == today:
        logger.info("garmin.auto_sync.skip reason=succeeded_today")
        return False

    return True


def settings_response() -> dict[str, Any]:
    settings = garmin_sync_settings.get_garmin_auto_sync_settings()
    return {
        **settings,
        "next_eligible_at": (
            next_eligible_auto_sync_at(settings).isoformat(timespec="minutes")
            if settings["enabled"]
            else None
        ),
        "timezone": config.APP_TIMEZONE,
    }


def validate_update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        raise ValueError("At least one auto-sync setting must be provided.")

    normalized = dict(payload)
    for key, value in normalized.items():
        if value is None:
            raise ValueError(f"{key} cannot be null.")

    if "sync_after_local_time" in normalized:
        parse_sync_after(str(normalized["sync_after_local_time"]))

    if "sync_days" in normalized:
        days = int(normalized["sync_days"])
        if days < 1 or days > 90:
            raise ValueError("Sync days must be between 1 and 90.")
        normalized["sync_days"] = days

    return normalized


def update_settings(payload: dict[str, Any]) -> dict[str, Any]:
    payload = validate_update_payload(payload)
    if "sync_after_local_time" in payload:
        parse_sync_after(str(payload["sync_after_local_time"]))
    settings = garmin_sync_settings.update_garmin_auto_sync_settings(payload)
    return {
        **settings,
        "next_eligible_at": (
            next_eligible_auto_sync_at(settings).isoformat(timespec="minutes")
            if settings["enabled"]
            else None
        ),
        "timezone": config.APP_TIMEZONE,
    }


async def run_garmin_auto_sync_once() -> dict[str, Any]:
    async with auto_sync_lock():
        settings = garmin_sync_settings.get_garmin_auto_sync_settings()
        connected = bool(garmin_service.status()["connected"])
        now_local = now_in_app_timezone()

        if not is_auto_sync_due(settings, connected=connected, now_local=now_local):
            return {"ran": False, "reason": "not_due", "settings": settings_response()}

        attempt_at = now_local.isoformat(timespec="seconds")
        garmin_sync_settings.record_garmin_auto_sync_attempt(attempt_at)
        days = int(settings["sync_days"])
        logger.info("garmin.auto_sync.start days=%s", days)

        try:
            sync_response = await asyncio.to_thread(garmin_service.sync, days)
        except Exception as exc:
            error = sanitize_error(exc)
            garmin_sync_settings.record_garmin_auto_sync_error(
                at=attempt_at,
                error=error,
            )
            logger.warning(
                "garmin.auto_sync.error error_type=%s",
                type(exc).__name__,
            )
            return {"ran": True, "success": False, "error": error}

        result = {
            "saved": len(sync_response.get("saved_dates", [])),
            "skipped": len(sync_response.get("skipped_dates", [])),
            "warnings": len(sync_response.get("errors", {})),
            "days": int(sync_response.get("days", days)),
        }
        garmin_sync_settings.record_garmin_auto_sync_success(
            at=attempt_at,
            result=result,
        )
        logger.info(
            "garmin.auto_sync.success saved=%s skipped=%s warnings=%s",
            result["saved"],
            result["skipped"],
            result["warnings"],
        )
        return {"ran": True, "success": True, "result": result}


async def garmin_auto_sync_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await run_garmin_auto_sync_once()
        except Exception:
            logger.exception("garmin.auto_sync.loop_error")

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=config.GARMIN_AUTO_SYNC_CHECK_INTERVAL_SECONDS,
            )
        except asyncio.TimeoutError:
            continue


def start_garmin_auto_sync_scheduler(app: Any) -> None:
    global _stop_event
    _stop_event = asyncio.Event()
    app.state.garmin_auto_sync_stop_event = _stop_event
    app.state.garmin_auto_sync_task = asyncio.create_task(
        garmin_auto_sync_loop(_stop_event)
    )
    logger.info(
        "garmin.auto_sync.scheduler.start interval_seconds=%s",
        config.GARMIN_AUTO_SYNC_CHECK_INTERVAL_SECONDS,
    )


async def stop_garmin_auto_sync_scheduler(app: Any) -> None:
    task = getattr(app.state, "garmin_auto_sync_task", None)
    stop_event = getattr(app.state, "garmin_auto_sync_stop_event", None)
    if stop_event is not None:
        stop_event.set()
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("garmin.auto_sync.scheduler.stop")
