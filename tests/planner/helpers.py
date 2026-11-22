"""Shared helpers for planner tests."""

from __future__ import annotations

from datetime import date
from typing import Any

from planner import PropertyProfile, Schedule, Task

NOW = "2026-01-01T00:00:00+00:00"


def make_task(
    schedule: Schedule,
    next_due: date,
    *,
    due_soon_days: int = 14,
    last_completed: date | None = None,
    created_at: str = "2020-01-01T00:00:00+00:00",
) -> Task:
    return Task(
        id="t1",
        title="Test",
        category="indoor",
        schedule=schedule,
        due_soon_days=due_soon_days,
        next_due=next_due,
        last_completed=last_completed,
        created_at=created_at,
    )


def profile(type_: str = "house", build_year: int | None = 2000, **attrs: Any) -> PropertyProfile:
    age_band = attrs.pop("age_band", None)
    return PropertyProfile.from_dict(
        {
            "name": "Test",
            "type": type_,
            "build_year": build_year,
            "age_band": age_band,
            "attributes": attrs,
        }
    )
