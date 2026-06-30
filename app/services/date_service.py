from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app import config


def app_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(config.APP_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def app_today() -> date:
    return datetime.now(app_timezone()).date()


def parse_local_date_from_as_of(as_of: str | None) -> tuple[date, str]:
    if as_of:
        try:
            return datetime.fromisoformat(str(as_of)).date(), "as_of"
        except ValueError:
            pass

    return app_today(), "configured_timezone_today"
