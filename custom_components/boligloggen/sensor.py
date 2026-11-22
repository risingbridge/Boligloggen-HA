"""Sensors: one per task, plus per-property aggregates."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoligloggenConfigEntry
from .const import KIND_SENSOR
from .coordinator import BoligloggenCoordinator
from .entity import BoligloggenEntity, BoligloggenTaskEntity, setup_task_entities
from .planner import Task, describe_schedule, task_status

AGGREGATE_LIST_LIMIT = 10


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoligloggenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            NextTaskSensor(coordinator),
            StatusCountSensor(coordinator, "overdue"),
            StatusCountSensor(coordinator, "due_soon"),
            LastCompletedSensor(coordinator),
        ]
    )
    entry.async_on_unload(setup_task_entities(coordinator, async_add_entities, TaskSensor))


class TaskSensor(BoligloggenTaskEntity, SensorEntity):
    """State: the next due date of the task."""

    _attr_device_class = SensorDeviceClass.DATE
    _unrecorded_attributes = frozenset({"description", "schedule"})

    def __init__(self, coordinator: BoligloggenCoordinator, task: Task) -> None:
        super().__init__(coordinator, task, KIND_SENSOR)
        self._attr_name = task.title

    @callback
    def _update_from_coordinator(self) -> None:
        super()._update_from_coordinator()
        task = self.task
        if task is None:
            return
        self._attr_name = task.title
        self._attr_native_value = task.next_due
        today = self.coordinator.today()
        last = self.coordinator.latest_entry(task.id)
        self._attr_extra_state_attributes = {
            "task_id": task.id,
            "status": task_status(task, today),
            "category": task.category,
            "schedule_type": task.schedule.type,
            "schedule": {
                "text": describe_schedule(task.schedule, self.coordinator.language),
                **task.schedule.to_dict(),
            },
            "due_soon_days": task.due_soon_days,
            "days_until_due": (task.next_due - today).days,
            "last_completed": task.last_completed.isoformat() if task.last_completed else None,
            "last_completed_by": last.user_name if last else None,
            "description": task.description,
            "template_id": task.template_id,
        }


def _brief(task: Task) -> dict[str, Any]:
    return {"task_id": task.id, "title": task.title, "next_due": task.next_due.isoformat()}


class NextTaskSensor(BoligloggenEntity, SensorEntity):
    _attr_translation_key = "next_task"
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator: BoligloggenCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_next_task"

    @callback
    def _update_from_coordinator(self) -> None:
        tasks = sorted(self.coordinator.active_tasks, key=lambda t: (t.next_due, t.title))
        if not tasks:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return
        task = tasks[0]
        self._attr_native_value = task.title
        self._attr_extra_state_attributes = {
            "task_id": task.id,
            "next_due": task.next_due.isoformat(),
            "status": task_status(task, self.coordinator.today()),
        }


class StatusCountSensor(BoligloggenEntity, SensorEntity):
    """Number of tasks with a given status; ``tasks`` lists them (not recorded)."""

    _unrecorded_attributes = frozenset({"tasks"})

    def __init__(self, coordinator: BoligloggenCoordinator, status: str) -> None:
        super().__init__(coordinator)
        self.status = status
        self._attr_translation_key = status
        self._attr_unique_id = f"{coordinator.entry_id}_{status}"
        self._attr_icon = "mdi:alert-circle" if status == "overdue" else "mdi:clock-alert"
        self._attr_native_unit_of_measurement = None

    @callback
    def _update_from_coordinator(self) -> None:
        today: date = self.coordinator.today()
        tasks = sorted(
            (t for t in self.coordinator.active_tasks if task_status(t, today) == self.status),
            key=lambda t: t.next_due,
        )
        self._attr_native_value = len(tasks)
        self._attr_extra_state_attributes = {
            "tasks": [_brief(t) for t in tasks[:AGGREGATE_LIST_LIMIT]]
        }


class LastCompletedSensor(BoligloggenEntity, SensorEntity):
    _attr_translation_key = "last_completed"
    _attr_icon = "mdi:check-circle"

    def __init__(self, coordinator: BoligloggenCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_last_completed"

    @callback
    def _update_from_coordinator(self) -> None:
        entry = self.coordinator.latest_entry()
        if entry is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return
        task = self.coordinator.tasks.get(entry.task_id)
        self._attr_native_value = task.title if task else None
        self._attr_extra_state_attributes = {
            "task_id": entry.task_id,
            "user_name": entry.user_name,
            "completed_on": entry.completed_on.isoformat(),
            "note": entry.note,
        }
