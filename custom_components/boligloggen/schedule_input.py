"""Parse schedule input from services and the options flow."""

from __future__ import annotations

import re
from collections.abc import Iterable

from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .planner import MonthDay, Schedule
from .planner.catalog import validate_month_day

_ISO = re.compile(r"^\s*(\d{1,2})-(\d{1,2})\s*$")  # MM-DD
_NORWEGIAN = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.?\s*$")  # D.M


class ScheduleInputError(ValueError):
    """Invalid schedule input; ``key`` is a translation key."""

    def __init__(self, key: str, value: str = "") -> None:
        super().__init__(key)
        self.key = key
        self.value = value

    def as_service_error(self) -> ServiceValidationError:
        return ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=self.key,
            translation_placeholders={"value": self.value},
        )


def parse_month_day(text: str) -> MonthDay:
    """Parse ``MM-DD`` (``12-01``) or Norwegian ``D.M`` (``1.12``)."""
    if m := _ISO.match(text):
        month, day = int(m.group(1)), int(m.group(2))
    elif m := _NORWEGIAN.match(text):
        day, month = int(m.group(1)), int(m.group(2))
    else:
        raise ScheduleInputError("invalid_date", text)
    if validate_month_day({"month": month, "day": day}):
        raise ScheduleInputError("invalid_date", text)
    return MonthDay(month, day)


def split_dates(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = re.split(r"[,;\s]+", value)
    return [v for v in (s.strip() for s in value) if v]


def build_schedule(
    schedule_type: str,
    *,
    every: int | None = None,
    unit: str | None = None,
    dates: str | Iterable[str] | None = None,
) -> Schedule:
    if schedule_type == "interval":
        if not every or every < 1 or unit not in ("months", "years"):
            raise ScheduleInputError("invalid_interval", f"{every} {unit}")
        return Schedule.interval(int(every), unit)  # type: ignore[arg-type]
    if schedule_type == "fixed":
        parts = split_dates(dates)
        if not parts:
            raise ScheduleInputError("invalid_date", "")
        return Schedule.fixed(*(parse_month_day(p) for p in parts))
    raise ScheduleInputError("invalid_interval", schedule_type)


def format_dates(schedule: Schedule) -> str:
    return ", ".join(f"{d.month:02d}-{d.day:02d}" for d in schedule.dates)
