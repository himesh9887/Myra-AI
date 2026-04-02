from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from myra.core.config import Settings
from myra.core.time import get_zone, now_in_zone
from myra.models.task import ParsedTask


TASK_KEYWORDS = {
    "exam": ["exam", "test", "paper"],
    "meeting": ["meeting", "call", "interview", "sync"],
    "reminder": ["remind", "reminder", "yaad dilana"],
    "assignment": ["assignment", "submission", "project"],
    "workout": ["workout", "gym", "exercise"],
}


@dataclass
class TimeRange:
    start: time | None = None
    end: time | None = None


class TaskParser:
    """Rule-based parser for extracting user tasks, dates, and times."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._zone = get_zone(settings.timezone)

    def parse(self, text: str, reference_time: datetime | None = None) -> ParsedTask | None:
        reference_time = reference_time or now_in_zone(self._settings.timezone)
        lowered = text.strip().lower()
        task_type = self._detect_task_type(lowered)
        if not task_type:
            return None

        task_date, date_label = self._extract_date(lowered, reference_time)
        time_range = self._extract_time_range(lowered)
        start_at = datetime.combine(task_date, time_range.start or time(9, 0), tzinfo=self._zone)
        end_at = (
            datetime.combine(task_date, time_range.end, tzinfo=self._zone) if time_range.end is not None else None
        )

        confidence = 0.55
        if date_label != "unspecified":
            confidence += 0.2
        if time_range.start:
            confidence += 0.15

        return ParsedTask(
            task_type=task_type,
            title=self._build_title(task_type, text),
            date_label=date_label,
            start_at=start_at,
            end_at=end_at,
            confidence=min(confidence, 0.95),
        )

    @staticmethod
    def _detect_task_type(text: str) -> str | None:
        for task_type, keywords in TASK_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return task_type
        return None

    def _extract_date(self, text: str, reference_time: datetime) -> tuple[date, str]:
        if "day after tomorrow" in text or "parso" in text:
            return reference_time.date() + timedelta(days=2), "day after tomorrow"
        if "tomorrow" in text or re.search(r"\bkal\b", text):
            return reference_time.date() + timedelta(days=1), "tomorrow"
        if "today" in text or re.search(r"\baaj\b", text):
            return reference_time.date(), "today"

        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        for day_name, day_index in weekdays.items():
            if day_name in text:
                days_ahead = (day_index - reference_time.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                return reference_time.date() + timedelta(days=days_ahead), day_name

        return reference_time.date(), "unspecified"

    @staticmethod
    def _extract_time_range(text: str) -> TimeRange:
        range_patterns = [
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:to|-|se)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
            r"(\d{1,2})\s*baje\s*(?:se|-)\s*(\d{1,2})\s*baje",
        ]
        for pattern in range_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if "baje" in pattern:
                    return TimeRange(start=time(int(groups[0]), 0), end=time(int(groups[1]), 0))

                return TimeRange(
                    start=TaskParser._to_24h(int(groups[0]), int(groups[1] or 0), groups[2]),
                    end=TaskParser._to_24h(int(groups[3]), int(groups[4] or 0), groups[5]),
                )

        single_patterns = [
            r"(?:at|from)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
            r"(\d{1,2})\s*baje",
        ]
        for pattern in single_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                minute = int(groups[1] or 0) if len(groups) > 1 else 0
                period = groups[2] if len(groups) > 2 else None
                return TimeRange(start=TaskParser._to_24h(int(groups[0]), minute, period))

        return TimeRange()

    @staticmethod
    def _to_24h(hour: int, minute: int, period: str | None) -> time:
        if period:
            normalized = period.lower()
            if normalized == "pm" and hour != 12:
                hour += 12
            if normalized == "am" and hour == 12:
                hour = 0
        return time(hour % 24, minute)

    @staticmethod
    def _build_title(task_type: str, raw_text: str) -> str:
        cleaned = re.sub(r"\s+", " ", raw_text).strip()
        return cleaned[:80] if cleaned else task_type.title()
