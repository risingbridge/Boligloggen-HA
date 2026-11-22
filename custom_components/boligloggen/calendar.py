"""Read-only calendar of projected task occurrences (all-day events)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BoligloggenConfigEntry
from .coordinator import BoligloggenCoordinator
from .entity import BoligloggenEntity
from .planner import Task

LOOKAHEAD_DAYS = 400


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoligloggenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([BoligloggenCalendar(entry.runtime_data)])


def _event(task: Task, day: date, status: str) -> CalendarEvent:
    return CalendarEvent(
        start=day,
        end=day + timedelta(days=1),
        summary=f"✓ {task.title}" if status == "done" else task.title,
        description=task.description or None,
        uid=f"{task.id}_{day.isoformat()}",
    )


class BoligloggenCalendar(BoligloggenEntity, CalendarEntity):
    _attr_translation_key = "plan"
    _attr_icon = "mdi:calendar-month"

    def __init__(self, coordinator: BoligloggenCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_calendar"
        self._event: CalendarEvent | None = None

    @property
    def event(self) -> CalendarEvent | None:
        return self._event

    @callback
    def _update_from_coordinator(self) -> None:
        today = self.coordinator.today()
        upcoming = [
            item
            for item in self.coordinator.occurrences_between(
                today, today + timedelta(days=LOOKAHEAD_DAYS)
            )
            if item[2] != "done"
        ]
        # Overdue tasks stay "current" until done.
        overdue = [t for t in self.coordinator.active_tasks if t.next_due < today]
        if overdue:
            task = min(overdue, key=lambda t: t.next_due)
            self._event = _event(task, today, "overdue")
        elif upcoming:
            self._event = _event(*upcoming[0])
        else:
            self._event = None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start = dt_util.as_local(start_date).date()
        end = dt_util.as_local(end_date).date()
        return [_event(*item) for item in self.coordinator.occurrences_between(start, end)]
