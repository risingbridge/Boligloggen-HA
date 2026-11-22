"""Export / import of a property's plan as a self-describing JSON document.

Export format (``format_version`` 1)::

    {
      "format": "boligloggen-export",
      "format_version": 1,
      "exported_at": "2026-11-22T19:00:00+00:00",
      "integration_version": "<manifest version>",
      "property": {<the stored property data: schema_version, language,
                   profile, tasks[], log[], onboarding_feedback>}
    }

``parse_export`` validates a document strictly before anything is replaced, so a
bad file never leaves a property half-imported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .catalog import validate_month_day
from .models import (
    AGE_BANDS,
    BATHROOM_COUNTS,
    CABIN_WATER,
    CABIN_WINTER_USE,
    CATEGORIES,
    CLADDING,
    DECK,
    DRIVEWAY,
    GARAGE,
    HEATING,
    LANGUAGES,
    PROPERTY_TYPES,
    VENTILATION,
    WATER,
    LogEntry,
    PropertyProfile,
    Task,
)

EXPORT_FORMAT = "boligloggen-export"
EXPORT_FORMAT_VERSION = 1
SUPPORTED_SCHEMA_VERSION = 1
MAX_TASKS = 2000
MAX_LOG_ENTRIES = 50000

_FEEDBACK_KEYS = ("deselected_at_review", "added_later", "removed_later")

# Allowed values for profile attributes (``None`` = may be null/omitted).
_ATTRIBUTE_ENUMS: dict[str, tuple[Any, ...]] = {
    "ventilation": VENTILATION,
    "cladding": (*CLADDING, None),
    "bathroom_count": BATHROOM_COUNTS,
    "driveway": DRIVEWAY,
    "deck": DECK,
    "garage": GARAGE,
    "water": WATER,
    "cabin_winter_use": (*CABIN_WINTER_USE, None),
    "cabin_water": (*CABIN_WATER, None),
}


class TransferError(ValueError):
    """Invalid import. ``key`` is a stable error code; ``detail`` says where."""

    def __init__(self, key: str, detail: str = "") -> None:
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


@dataclass(frozen=True)
class PlanSnapshot:
    """A validated, parsed export."""

    profile: PropertyProfile
    language: str | None
    tasks: tuple[Task, ...]
    log: tuple[LogEntry, ...]
    feedback: dict[str, list[str]] = field(default_factory=dict)
    exported_at: str = ""
    integration_version: str = ""

    @property
    def active_count(self) -> int:
        return sum(1 for t in self.tasks if t.is_active)


def build_export(
    property_data: dict[str, Any], *, exported_at: str, integration_version: str
) -> dict[str, Any]:
    return {
        "format": EXPORT_FORMAT,
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": exported_at,
        "integration_version": integration_version,
        "property": property_data,
    }


def _require_dict(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TransferError("invalid_content", f"{where} must be an object")
    return value


def _require_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise TransferError("invalid_content", f"{where} must be a list")
    return value


def _parse_profile(raw: Any) -> PropertyProfile:
    data = _require_dict(raw, "property.profile")
    try:
        profile = PropertyProfile.from_dict(data)
    except (KeyError, TypeError, ValueError) as err:
        raise TransferError("invalid_content", f"property.profile: {err!r}") from err
    if not isinstance(profile.name, str) or not profile.name.strip():
        raise TransferError("invalid_content", "property.profile.name is empty")
    if profile.type not in PROPERTY_TYPES:
        raise TransferError("invalid_content", f"property.profile.type {profile.type!r}")
    if profile.age_band is not None and profile.age_band not in AGE_BANDS:
        raise TransferError("invalid_content", f"property.profile.age_band {profile.age_band!r}")
    if profile.build_year is not None and not 1000 <= profile.build_year <= 2200:
        raise TransferError("invalid_content", "property.profile.build_year out of range")
    attrs = profile.attributes
    for value in attrs.heating:
        if value not in HEATING:
            raise TransferError("invalid_content", f"property.profile.attributes.heating {value!r}")
    for name, allowed in _ATTRIBUTE_ENUMS.items():
        value = getattr(attrs, name)
        if value not in allowed:
            raise TransferError("invalid_content", f"property.profile.attributes.{name} {value!r}")
    raw_garden = (data.get("attributes") or {}).get("garden", False)
    if not isinstance(raw_garden, bool):
        raise TransferError(
            "invalid_content", "property.profile.attributes.garden must be true/false"
        )
    return profile


def _parse_task(raw: Any, index: int) -> Task:
    where = f"property.tasks[{index}]"
    data = _require_dict(raw, where)
    schedule = _require_dict(data.get("schedule"), f"{where}.schedule")
    if schedule.get("type") == "fixed":
        dates = _require_list(schedule.get("dates"), f"{where}.schedule.dates")
        if not dates:
            raise TransferError("invalid_content", f"{where}.schedule.dates is empty")
        for d in dates:
            if errors := validate_month_day(d):
                raise TransferError("invalid_content", f"{where}.schedule: {errors[0]}")
    elif schedule.get("type") == "interval":
        every, unit = schedule.get("every"), schedule.get("unit")
        if not isinstance(every, int) or every < 1 or unit not in ("months", "years"):
            raise TransferError("invalid_content", f"{where}.schedule: bad interval")
    else:
        raise TransferError("invalid_content", f"{where}.schedule.type {schedule.get('type')!r}")
    try:
        task = Task.from_dict(data)
    except (KeyError, TypeError, ValueError) as err:
        raise TransferError("invalid_content", f"{where}: {err!r}") from err
    if not isinstance(task.id, str) or not task.id:
        raise TransferError("invalid_content", f"{where}.id is empty")
    if not isinstance(task.title, str) or not task.title.strip():
        raise TransferError("invalid_content", f"{where}.title is empty")
    if task.category not in CATEGORIES:
        raise TransferError("invalid_content", f"{where}.category {task.category!r}")
    if task.status not in ("active", "archived"):
        raise TransferError("invalid_content", f"{where}.status {task.status!r}")
    if task.due_soon_days < 0:
        raise TransferError("invalid_content", f"{where}.due_soon_days is negative")
    return task


def _parse_log_entry(raw: Any, index: int) -> LogEntry:
    where = f"property.log[{index}]"
    data = _require_dict(raw, where)
    try:
        entry = LogEntry.from_dict(data)
    except (KeyError, TypeError, ValueError) as err:
        raise TransferError("invalid_content", f"{where}: {err!r}") from err
    if not isinstance(entry.id, str) or not entry.id:
        raise TransferError("invalid_content", f"{where}.id is empty")
    return entry


def parse_export(payload: Any) -> PlanSnapshot:
    """Validate and parse an export document. Raises :class:`TransferError`."""
    if not isinstance(payload, dict) or payload.get("format") != EXPORT_FORMAT:
        raise TransferError("not_boligloggen_file")
    version = payload.get("format_version")
    if not isinstance(version, int) or version > EXPORT_FORMAT_VERSION or version < 1:
        raise TransferError("unsupported_version", f"format_version {version!r}")
    prop = _require_dict(payload.get("property"), "property")
    schema = prop.get("schema_version", 1)
    if not isinstance(schema, int) or schema > SUPPORTED_SCHEMA_VERSION:
        raise TransferError("unsupported_version", f"schema_version {schema!r}")

    profile = _parse_profile(prop.get("profile"))
    raw_tasks = _require_list(prop.get("tasks", []), "property.tasks")
    raw_log = _require_list(prop.get("log", []), "property.log")
    if len(raw_tasks) > MAX_TASKS or len(raw_log) > MAX_LOG_ENTRIES:
        raise TransferError("invalid_content", "too many tasks or log entries")
    tasks = tuple(_parse_task(t, i) for i, t in enumerate(raw_tasks))
    log = tuple(_parse_log_entry(e, i) for i, e in enumerate(raw_log))
    ids = [t.id for t in tasks]
    if len(set(ids)) != len(ids):
        raise TransferError("invalid_content", "duplicate task ids")
    log_ids = [e.id for e in log]
    if len(set(log_ids)) != len(log_ids):
        raise TransferError("invalid_content", "duplicate log entry ids")

    language = prop.get("language")
    if language not in LANGUAGES:
        language = None
    raw_feedback = prop.get("onboarding_feedback")
    feedback: dict[str, list[str]] = {}
    for key in _FEEDBACK_KEYS:
        values = raw_feedback.get(key) if isinstance(raw_feedback, dict) else None
        feedback[key] = (
            [v for v in values if isinstance(v, str)] if isinstance(values, list) else []
        )

    return PlanSnapshot(
        profile=profile,
        language=language,
        tasks=tasks,
        log=log,  # stored order = completion order; undo relies on it
        feedback=feedback,
        exported_at=str(payload.get("exported_at") or ""),
        integration_version=str(payload.get("integration_version") or ""),
    )
