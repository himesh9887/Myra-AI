from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_zone(timezone_name: str) -> ZoneInfo:
    return ZoneInfo(timezone_name)


def now_in_zone(timezone_name: str) -> datetime:
    return utc_now().astimezone(get_zone(timezone_name))


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_zone(value: datetime, timezone_name: str) -> datetime:
    return ensure_utc(value).astimezone(get_zone(timezone_name))

