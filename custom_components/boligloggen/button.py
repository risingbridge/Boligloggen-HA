""" "Done" button per task."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoligloggenConfigEntry
from .const import DONE_LABEL, KIND_BUTTON
from .coordinator import BoligloggenCoordinator
from .entity import BoligloggenTaskEntity, setup_task_entities
from .planner import Task


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoligloggenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    entry.async_on_unload(
        setup_task_entities(entry.runtime_data, async_add_entities, TaskDoneButton)
    )


class TaskDoneButton(BoligloggenTaskEntity, ButtonEntity):
    """Pressing completes the task today as the calling user."""

    def __init__(self, coordinator: BoligloggenCoordinator, task: Task) -> None:
        super().__init__(coordinator, task, KIND_BUTTON)
        self._attr_name = self._label(task)
        self._attr_icon = "mdi:check"

    def _label(self, task: Task) -> str:
        return f"{task.title} – {DONE_LABEL.get(self.coordinator.language, 'done')}"

    @callback
    def _update_from_coordinator(self) -> None:
        if (task := self.task) is not None:
            self._attr_name = self._label(task)
            self._attr_extra_state_attributes = {"task_id": task.id}

    async def async_press(self) -> None:
        # Entity service calls set the call context on the entity before the
        # method runs (helpers/service.py → entity.async_set_context).
        await self.coordinator.async_complete(self.task_id, context=self._context)
