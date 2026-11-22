"""Domain models for the Boligloggen planner.

Pure Python: this package must never import ``homeassistant``.
All (de)serialisation uses plain JSON-compatible dicts so the same shapes
can be stored in Home Assistant's ``Store`` and returned over websocket.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Enumerations (English identifiers; UI labels come from translations)
# ---------------------------------------------------------------------------

PROPERTY_TYPES: tuple[str, ...] = ("house", "townhouse", "apartment", "cabin")
AGE_BANDS: dict[str, int] = {"lt10": 0, "10to30": 10, "30to50": 30, "gt50": 50}
HEATING: tuple[str, ...] = ("wood_stove", "heat_pump", "hydronic", "electric", "district")
VENTILATION: tuple[str, ...] = ("balanced", "exhaust", "natural", "unknown")
CLADDING: tuple[str, ...] = ("wood", "render", "brick", "mixed")
BATHROOM_COUNTS: tuple[int, ...] = (1, 2, 3)
DRIVEWAY: tuple[str, ...] = ("none", "asphalt", "pavers", "gravel", "concrete")
DECK: tuple[str, ...] = ("none", "wood", "composite_or_stone")
GARAGE: tuple[str, ...] = ("none", "garage_with_door", "carport")
WATER: tuple[str, ...] = ("public", "own_well")
CABIN_WINTER_USE: tuple[str, ...] = ("closed", "year_round")
CABIN_WATER: tuple[str, ...] = ("year_round", "summer", "none")
CATEGORIES: tuple[str, ...] = (
    "safety",
    "indoor",
    "wet_room",
    "heating",
    "ventilation",
    "exterior",
    "outdoor",
    "cabin",
    "seasonal",
)
LANGUAGES: tuple[str, ...] = ("nb", "en")

ScheduleType = Literal["fixed", "interval"]
IntervalUnit = Literal["months", "years"]
DueStatus = Literal["ok", "due_soon", "overdue"]
OccurrenceStatus = Literal["done", "missed", "upcoming", "due_soon", "overdue"]
TaskStatus = Literal["active", "archived"]

#: Age (years) below which ``ventilation: unknown`` is assumed to be balanced.
VENTILATION_BALANCED_MAX_AGE = 15


def _date_or_none(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _iso_or_none(value: date | None) -> str | None:
    return value.isoformat() if value else None


# ---------------------------------------------------------------------------
# Property profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PropertyAttributes:
    heating: tuple[str, ...] = ()
    ventilation: str = "unknown"
    cladding: str | None = None
    bathroom_count: int = 1
    garden: bool = False
    driveway: str = "none"
    deck: str = "none"
    garage: str = "none"
    water: str = "public"
    cabin_winter_use: str | None = None
    cabin_water: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PropertyAttributes:
        return cls(
            heating=tuple(data.get("heating") or ()),
            ventilation=data.get("ventilation") or "unknown",
            cladding=data.get("cladding"),
            bathroom_count=int(data.get("bathroom_count") or 1),
            garden=bool(data.get("garden", False)),
            driveway=data.get("driveway") or "none",
            deck=data.get("deck") or "none",
            garage=data.get("garage") or "none",
            water=data.get("water") or "public",
            cabin_winter_use=data.get("cabin_winter_use"),
            cabin_water=data.get("cabin_water"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "heating": list(self.heating),
            "ventilation": self.ventilation,
            "cladding": self.cladding,
            "bathroom_count": self.bathroom_count,
            "garden": self.garden,
            "driveway": self.driveway,
            "deck": self.deck,
            "garage": self.garage,
            "water": self.water,
            "cabin_winter_use": self.cabin_winter_use,
            "cabin_water": self.cabin_water,
        }


@dataclass(frozen=True)
class PropertyProfile:
    name: str
    type: str
    address: str = ""
    build_year: int | None = None
    age_band: str | None = None
    attributes: PropertyAttributes = field(default_factory=PropertyAttributes)

    def age_years(self, today: date) -> int:
        """Age of the building. ``build_year`` wins over ``age_band``.

        With neither given the property is treated as new (0 years).
        """
        if self.build_year is not None:
            return max(0, today.year - self.build_year)
        if self.age_band is not None:
            return AGE_BANDS[self.age_band]
        return 0

    def effective_ventilation(self, today: date) -> str:
        """Resolve ``unknown`` ventilation with a simple age heuristic."""
        vent = self.attributes.ventilation
        if vent != "unknown":
            return vent
        return "balanced" if self.age_years(today) < VENTILATION_BALANCED_MAX_AGE else "exhaust"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PropertyProfile:
        build_year = data.get("build_year")
        return cls(
            name=data["name"],
            type=data["type"],
            address=data.get("address") or "",
            build_year=int(build_year) if build_year is not None else None,
            age_band=data.get("age_band"),
            attributes=PropertyAttributes.from_dict(data.get("attributes") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "type": self.type,
            "build_year": self.build_year,
            "age_band": self.age_band,
            "attributes": self.attributes.to_dict(),
        }


# ---------------------------------------------------------------------------
# Schedules and templates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MonthDay:
    month: int
    day: int = 1


@dataclass(frozen=True)
class Schedule:
    type: ScheduleType
    every: int = 0
    unit: IntervalUnit = "months"
    dates: tuple[MonthDay, ...] = ()

    @classmethod
    def interval(cls, every: int, unit: IntervalUnit) -> Schedule:
        return cls(type="interval", every=every, unit=unit)

    @classmethod
    def fixed(cls, *dates: tuple[int, int] | MonthDay) -> Schedule:
        md = tuple(d if isinstance(d, MonthDay) else MonthDay(d[0], d[1]) for d in dates)
        return cls(type="fixed", dates=tuple(sorted(md, key=lambda x: (x.month, x.day))))

    @property
    def interval_months(self) -> int:
        """Interval length in months (interval schedules only)."""
        return self.every * (12 if self.unit == "years" else 1)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Schedule:
        if data["type"] == "interval":
            return cls.interval(int(data["every"]), data["unit"])
        if data["type"] == "fixed":
            return cls.fixed(
                *(MonthDay(int(d["month"]), int(d.get("day", 1))) for d in data["dates"])
            )
        raise ValueError(f"Unknown schedule type: {data['type']!r}")

    def to_dict(self) -> dict[str, Any]:
        if self.type == "interval":
            return {"type": "interval", "every": self.every, "unit": self.unit}
        return {
            "type": "fixed",
            "dates": [{"month": d.month, "day": d.day} for d in self.dates],
        }


@dataclass(frozen=True)
class TaskTemplate:
    id: str
    category: str
    title: dict[str, str]
    schedule: Schedule
    description: dict[str, str] = field(default_factory=dict)
    due_soon_days: int | None = None
    per_bathroom: bool = False
    include: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tasks, log entries, occurrences
# ---------------------------------------------------------------------------


def template_key(template_id: str, instance: int | None) -> str:
    """Stable key for a seeded template instance (``clean_drains#2``)."""
    return f"{template_id}#{instance}" if instance else template_id


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    category: str
    schedule: Schedule
    due_soon_days: int
    next_due: date
    template_id: str | None = None
    #: Bathroom number for ``per_bathroom`` templates, otherwise ``None``.
    instance: int | None = None
    description: str = ""
    last_completed: date | None = None
    status: TaskStatus = "active"
    last_notified_state: DueStatus = "ok"
    created_at: str = ""
    updated_at: str = ""

    @property
    def key(self) -> str | None:
        """Template key, or ``None`` for custom tasks."""
        return template_key(self.template_id, self.instance) if self.template_id else None

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def evolve(self, **changes: Any) -> Task:
        return replace(self, **changes)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        return cls(
            id=data["id"],
            template_id=data.get("template_id"),
            instance=data.get("instance"),
            title=data["title"],
            description=data.get("description") or "",
            category=data["category"],
            schedule=Schedule.from_dict(data["schedule"]),
            due_soon_days=int(data["due_soon_days"]),
            next_due=date.fromisoformat(data["next_due"]),
            last_completed=_date_or_none(data.get("last_completed")),
            status=data.get("status", "active"),
            last_notified_state=data.get("last_notified_state", "ok"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "instance": self.instance,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "schedule": self.schedule.to_dict(),
            "due_soon_days": self.due_soon_days,
            "next_due": self.next_due.isoformat(),
            "last_completed": _iso_or_none(self.last_completed),
            "status": self.status,
            "last_notified_state": self.last_notified_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class LogEntry:
    id: str
    task_id: str
    completed_on: date
    occurrence_date: date
    prev_next_due: date
    prev_last_completed: date | None = None
    user_id: str | None = None
    user_name: str = "System"
    note: str | None = None
    forced: bool = False
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LogEntry:
        return cls(
            id=data["id"],
            task_id=data["task_id"],
            completed_on=date.fromisoformat(data["completed_on"]),
            occurrence_date=date.fromisoformat(data["occurrence_date"]),
            prev_next_due=date.fromisoformat(data["prev_next_due"]),
            prev_last_completed=_date_or_none(data.get("prev_last_completed")),
            user_id=data.get("user_id"),
            user_name=data.get("user_name") or "System",
            note=data.get("note"),
            forced=bool(data.get("forced", False)),
            created_at=data.get("created_at", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "completed_on": self.completed_on.isoformat(),
            "occurrence_date": self.occurrence_date.isoformat(),
            "user_id": self.user_id,
            "user_name": self.user_name,
            "note": self.note,
            "forced": self.forced,
            "prev_next_due": self.prev_next_due.isoformat(),
            "prev_last_completed": _iso_or_none(self.prev_last_completed),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class Occurrence:
    date: date
    status: OccurrenceStatus

    def to_dict(self) -> dict[str, Any]:
        return {"date": self.date.isoformat(), "status": self.status}
