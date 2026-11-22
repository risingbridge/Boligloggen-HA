"""Base entities for Boligloggen."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CATEGORY_ICONS, DOMAIN, MANUFACTURER
from .coordinator import BoligloggenCoordinator, unique_id_for
from .planner import Task


def device_info(coordinator: BoligloggenCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry_id)},
        name=coordinator.profile.name,
        entry_type=DeviceEntryType.SERVICE,
        manufacturer=MANUFACTURER,
        model=coordinator.profile.type,
    )


class BoligloggenEntity(Entity):
    """Entity bound to a property coordinator; refreshes on every change."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: BoligloggenCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_device_info = device_info(coordinator)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_update))
        self._update_from_coordinator()

    @callback
    def _handle_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh cached attributes from the coordinator."""


class BoligloggenTaskEntity(BoligloggenEntity):
    """Entity representing one task."""

    def __init__(self, coordinator: BoligloggenCoordinator, task: Task, kind: str) -> None:
        super().__init__(coordinator)
        self.task_id = task.id
        self._attr_unique_id = unique_id_for(coordinator.entry_id, task.id, kind)
        self._attr_icon = CATEGORY_ICONS.get(task.category, "mdi:wrench")

    @property
    def task(self) -> Task | None:
        return self.coordinator.tasks.get(self.task_id)

    @property
    def available(self) -> bool:
        task = self.task
        return task is not None and task.is_active

    @callback
    def _handle_update(self) -> None:
        # Archived tasks are removed via the entity registry; don't write state
        # for an entity that is being removed.
        if self.task is None or not self.task.is_active:
            return
        super()._handle_update()

    @callback
    def _update_from_coordinator(self) -> None:
        if (task := self.task) is not None:
            self._attr_icon = CATEGORY_ICONS.get(task.category, "mdi:wrench")


def setup_task_entities(
    coordinator: BoligloggenCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[BoligloggenCoordinator, Task], Entity],
) -> Callable[[], None]:
    """Add entities for active tasks now and whenever tasks are added/restored."""
    known: set[str] = set()

    @callback
    def sync() -> None:
        active = {t.id: t for t in coordinator.active_tasks}
        known.intersection_update(active)
        new = [task for task_id, task in active.items() if task_id not in known]
        if new:
            known.update(t.id for t in new)
            async_add_entities([factory(coordinator, t) for t in new])

    sync()
    return coordinator.async_add_listener(sync)
