"""Load and validate the bundled task catalog (``catalog.json``)."""

from __future__ import annotations

import calendar
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import models as m
from .models import MonthDay, Schedule, TaskTemplate
from .rules import BOOL_KEYS, INT_KEYS, LIST_KEY_ENUMS, MATCHERS

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent.parent / "catalog.json"

_TEMPLATE_KEYS = frozenset(
    {
        "id",
        "category",
        "title",
        "description",
        "schedule",
        "due_soon_days",
        "per_bathroom",
        "include",
    }
)
_REQUIRED_TEMPLATE_KEYS = frozenset({"id", "category", "title", "schedule"})


class CatalogError(ValueError):
    """Raised when the catalog is structurally invalid."""


@dataclass(frozen=True)
class Catalog:
    version: int
    templates: tuple[TaskTemplate, ...]

    def __iter__(self) -> Iterator[TaskTemplate]:
        return iter(self.templates)

    def __len__(self) -> int:
        return len(self.templates)

    def get(self, template_id: str) -> TaskTemplate | None:
        return next((t for t in self.templates if t.id == template_id), None)


def load_catalog(path: Path | str | None = None) -> Catalog:
    """Read and validate a catalog file (default: the bundled ``catalog.json``)."""
    with open(path or DEFAULT_CATALOG_PATH, encoding="utf-8") as fh:
        return parse_catalog(json.load(fh))


def parse_catalog(data: Any) -> Catalog:
    errors: list[str] = []
    if not isinstance(data, dict):
        raise CatalogError("Catalog root must be an object")
    unknown_root = set(data) - {"version", "templates", "$schema"}
    if unknown_root:
        errors.append(f"unknown root keys: {sorted(unknown_root)}")
    version = data.get("version")
    if not isinstance(version, int) or version < 1:
        errors.append("version must be a positive integer")
    raw_templates = data.get("templates")
    if not isinstance(raw_templates, list) or not raw_templates:
        raise CatalogError("templates must be a non-empty list")

    templates: list[TaskTemplate] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_templates):
        where = f"templates[{index}]"
        if isinstance(raw, dict) and isinstance(raw.get("id"), str):
            where = f"template {raw['id']!r}"
        template_errors = _validate_template(raw)
        if template_errors:
            errors.extend(f"{where}: {e}" for e in template_errors)
            continue
        if raw["id"] in seen:
            errors.append(f"{where}: duplicate id")
            continue
        seen.add(raw["id"])
        templates.append(_build_template(raw))

    if errors:
        raise CatalogError("Invalid catalog:\n  " + "\n  ".join(errors))
    assert isinstance(version, int)
    return Catalog(version=version, templates=tuple(templates))


def _validate_localized(value: Any, name: str, required: bool) -> list[str]:
    if value is None and not required:
        return []
    if not isinstance(value, dict):
        return [f"{name} must be an object of language → text"]
    errors = [f"{name}: unknown language {k!r}" for k in value if k not in m.LANGUAGES]
    if required:
        errors += [f"{name}: missing {lang!r}" for lang in m.LANGUAGES if not value.get(lang)]
    errors += [f"{name}.{k} must be a string" for k, v in value.items() if not isinstance(v, str)]
    return errors


def _validate_schedule(raw: Any) -> list[str]:
    if not isinstance(raw, dict):
        return ["schedule must be an object"]
    stype = raw.get("type")
    if stype == "interval":
        errors = [f"schedule: unknown key {k!r}" for k in raw if k not in {"type", "every", "unit"}]
        every = raw.get("every")
        if not isinstance(every, int) or isinstance(every, bool) or every < 1:
            errors.append("schedule.every must be a positive integer")
        if raw.get("unit") not in ("months", "years"):
            errors.append("schedule.unit must be 'months' or 'years'")
        return errors
    if stype == "fixed":
        errors = [f"schedule: unknown key {k!r}" for k in raw if k not in {"type", "dates"}]
        dates = raw.get("dates")
        if not isinstance(dates, list) or not dates:
            return [*errors, "schedule.dates must be a non-empty list"]
        for i, d in enumerate(dates):
            errors.extend(f"schedule.dates[{i}]: {e}" for e in validate_month_day(d))
        return errors
    return [f"schedule.type must be 'fixed' or 'interval', got {stype!r}"]


def validate_month_day(raw: Any) -> list[str]:
    """Validate ``{"month": M, "day": D}``. 29 Feb is allowed (→ 28 Feb in non-leap years)."""
    if not isinstance(raw, dict):
        return ["must be an object"]
    errors = [f"unknown key {k!r}" for k in raw if k not in {"month", "day"}]
    month, day = raw.get("month"), raw.get("day", 1)
    if not isinstance(month, int) or not 1 <= month <= 12:
        return [*errors, f"invalid month {month!r}"]
    if not isinstance(day, int) or not 1 <= day <= calendar.monthrange(2024, month)[1]:
        errors.append(f"invalid day {day!r} for month {month}")
    return errors


def validate_include(raw: Any) -> list[str]:
    if not isinstance(raw, dict):
        return ["include must be an object"]
    errors: list[str] = []
    for key, value in raw.items():
        if key not in MATCHERS:
            errors.append(f"include: unknown key {key!r}")
        elif key in LIST_KEY_ENUMS:
            if not isinstance(value, list) or not value:
                errors.append(f"include.{key} must be a non-empty list")
                continue
            bad = [v for v in value if v not in LIST_KEY_ENUMS[key]]
            if bad:
                errors.append(f"include.{key}: invalid values {bad}")
        elif key in BOOL_KEYS:
            if not isinstance(value, bool):
                errors.append(f"include.{key} must be a boolean")
        elif key in INT_KEYS and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            errors.append(f"include.{key} must be a non-negative integer")
    return errors


def _validate_template(raw: Any) -> list[str]:
    if not isinstance(raw, dict):
        return ["must be an object"]
    errors = [f"unknown key {k!r}" for k in raw if k not in _TEMPLATE_KEYS]
    errors += [f"missing {k!r}" for k in sorted(_REQUIRED_TEMPLATE_KEYS - set(raw))]
    if errors:
        return errors
    tid = raw["id"]
    if not isinstance(tid, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", tid):
        errors.append("id must be a lower_snake_case string")
    if raw["category"] not in m.CATEGORIES:
        errors.append(f"invalid category {raw['category']!r}")
    errors += _validate_localized(raw["title"], "title", required=True)
    errors += _validate_localized(raw.get("description"), "description", required=False)
    errors += _validate_schedule(raw["schedule"])
    dsd = raw.get("due_soon_days")
    if dsd is not None and (not isinstance(dsd, int) or isinstance(dsd, bool) or dsd < 0):
        errors.append("due_soon_days must be a non-negative integer")
    if not isinstance(raw.get("per_bathroom", False), bool):
        errors.append("per_bathroom must be a boolean")
    errors += validate_include(raw.get("include", {}))
    return errors


def _build_template(raw: dict[str, Any]) -> TaskTemplate:
    sched = raw["schedule"]
    if sched["type"] == "fixed":
        schedule = Schedule.fixed(*(MonthDay(d["month"], d.get("day", 1)) for d in sched["dates"]))
    else:
        schedule = Schedule.interval(sched["every"], sched["unit"])
    return TaskTemplate(
        id=raw["id"],
        category=raw["category"],
        title=dict(raw["title"]),
        description=dict(raw.get("description") or {}),
        schedule=schedule,
        due_soon_days=raw.get("due_soon_days"),
        per_bathroom=raw.get("per_bathroom", False),
        include=dict(raw.get("include") or {}),
    )
