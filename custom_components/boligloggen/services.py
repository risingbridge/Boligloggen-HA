"""Services for completing and editing tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, KIND_BUTTON, KIND_SENSOR
from .planner import Schedule
from .planner.models import CATEGORIES as _CATEGORIES
from .schedule_input import ScheduleInputError, build_schedule

if TYPE_CHECKING:
    from .coordinator import BoligloggenCoordinator

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_TASK_ID = "task_id"

SERVICE_COMPLETE = "complete_task"
SERVICE_UNDO = "undo_completion"
SERVICE_ADD = "add_task"
SERVICE_UPDATE = "update_task"
SERVICE_REMOVE = "remove_task"
SERVICE_RESTORE = "restore_task"

_TARGET: dict[vol.Marker, Any] = {
    vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Optional(ATTR_TASK_ID): cv.string,
}
_SCHEDULE_FIELDS: dict[vol.Marker, Any] = {
    vol.Optional("schedule_type"): vol.In(["fixed", "interval"]),
    vol.Optional("every"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional("unit"): vol.In(["months", "years"]),
    vol.Optional("dates"): vol.Any(cv.string, [cv.string]),
}
_TASK_FIELDS: dict[vol.Marker, Any] = {
    vol.Optional("title"): cv.string,
    vol.Optional("description"): cv.string,
    vol.Optional("category"): vol.In(_CATEGORIES),
    vol.Optional("due_soon_days"): vol.All(vol.Coerce(int), vol.Range(min=0, max=3650)),
    **_SCHEDULE_FIELDS,
}

COMPLETE_SCHEMA = vol.Schema(
    {
        **_TARGET,
        vol.Optional("note"): cv.string,
        vol.Optional("completed_on"): cv.date,
        vol.Optional("force", default=False): cv.boolean,
    }
)
TARGET_SCHEMA = vol.Schema(_TARGET)
ADD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional("template_id"): vol.Any(cv.string, [cv.string]),
        **_TASK_FIELDS,
    }
)
UPDATE_SCHEMA = vol.Schema(
    {
        **_TARGET,
        **_TASK_FIELDS,
        vol.Optional("last_completed"): cv.date,
        vol.Optional("next_due"): cv.date,
    }
)
RESTORE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string, vol.Required(ATTR_TASK_ID): cv.string}
)


def _err(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def _coordinator(hass: HomeAssistant, entry_id: str) -> BoligloggenCoordinator:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        raise _err("property_not_found", config_entry_id=entry_id)
    coordinator: BoligloggenCoordinator = entry.runtime_data
    return coordinator


def resolve_task(hass: HomeAssistant, data: dict[str, Any]) -> tuple[BoligloggenCoordinator, str]:
    """Resolve ``entity_id`` (task sensor/button) or ``config_entry_id`` + ``task_id``."""
    if entity_id := data.get(ATTR_ENTITY_ID):
        entity = er.async_get(hass).async_get(entity_id)
        if entity is None or entity.platform != DOMAIN or entity.config_entry_id is None:
            raise _err("not_a_task_entity", entity_id=entity_id)
        prefix = f"{entity.config_entry_id}_"
        unique_id = entity.unique_id
        for kind in (KIND_SENSOR, KIND_BUTTON):
            suffix = f"_{kind}"
            if unique_id.startswith(prefix) and unique_id.endswith(suffix):
                found = unique_id[len(prefix) : -len(suffix)]
                if found:
                    return _coordinator(hass, entity.config_entry_id), found
        raise _err("not_a_task_entity", entity_id=entity_id)
    entry_id, task_id = data.get(ATTR_CONFIG_ENTRY_ID), data.get(ATTR_TASK_ID)
    if entry_id and task_id:
        return _coordinator(hass, str(entry_id)), str(task_id)
    raise _err("task_target_required")


async def async_require_admin(hass: HomeAssistant, call: ServiceCall) -> None:
    """System calls (no user) are trusted; non-admin users are rejected."""
    if call.context.user_id is None:
        return
    user = await hass.auth.async_get_user(call.context.user_id)
    if user is None:
        return
    if not user.is_admin:
        raise Unauthorized(context=call.context)


def _schedule_from(data: dict[str, Any], *, required: bool) -> Schedule | None:
    schedule_type = data.get("schedule_type")
    if schedule_type is None:
        if required:
            raise _err("schedule_required")
        return None
    try:
        return build_schedule(
            schedule_type, every=data.get("every"), unit=data.get("unit"), dates=data.get("dates")
        )
    except ScheduleInputError as err:
        raise err.as_service_error() from err


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def complete(call: ServiceCall) -> ServiceResponse:
        coordinator, task_id = resolve_task(hass, call.data)
        entry = await coordinator.async_complete(
            task_id,
            context=call.context,
            completed_on=call.data.get("completed_on"),
            note=call.data.get("note"),
            force=call.data["force"],
        )
        return {"log_entry": entry.to_dict()}

    async def undo(call: ServiceCall) -> ServiceResponse:
        coordinator, task_id = resolve_task(hass, call.data)
        entry = await coordinator.async_undo(task_id, context=call.context)
        return {"removed_log_entry": entry.to_dict()}

    async def add(call: ServiceCall) -> ServiceResponse:
        await async_require_admin(hass, call)
        coordinator = _coordinator(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        if template_ids := call.data.get("template_id"):
            keys = [template_ids] if isinstance(template_ids, str) else list(template_ids)
            # A per-bathroom template id without "#n" adds all its instances.
            expanded: list[str] = []
            for key in keys:
                template = coordinator.catalog.get(key)
                if template is not None and template.per_bathroom:
                    count = coordinator.profile.attributes.bathroom_count
                    expanded.extend(f"{key}#{n}" for n in range(1, count + 1))
                else:
                    expanded.append(key)
            tasks = coordinator.async_add_from_catalog(expanded)
        else:
            title = (call.data.get("title") or "").strip()
            if not title:
                raise _err("title_required")
            schedule = _schedule_from(call.data, required=True)
            assert schedule is not None
            tasks = [
                coordinator.async_add_custom(
                    title=title,
                    category=call.data.get("category", "indoor"),
                    schedule=schedule,
                    description=call.data.get("description", ""),
                    due_soon_days=call.data.get("due_soon_days"),
                )
            ]
        return {"task_ids": [t.id for t in tasks]}

    async def update(call: ServiceCall) -> ServiceResponse:
        await async_require_admin(hass, call)
        coordinator, task_id = resolve_task(hass, call.data)
        task = coordinator.async_update_task(
            task_id,
            title=call.data.get("title"),
            description=call.data.get("description"),
            category=call.data.get("category"),
            schedule=_schedule_from(call.data, required=False),
            due_soon_days=call.data.get("due_soon_days"),
            last_completed=call.data.get("last_completed"),
            next_due=call.data.get("next_due"),
        )
        return {"task": task.to_dict()}

    async def remove(call: ServiceCall) -> None:
        await async_require_admin(hass, call)
        coordinator, task_id = resolve_task(hass, call.data)
        coordinator.get_task(task_id)
        coordinator.async_archive([task_id])

    async def restore(call: ServiceCall) -> None:
        await async_require_admin(hass, call)
        coordinator = _coordinator(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        coordinator.async_restore([call.data[ATTR_TASK_ID]])

    register = hass.services.async_register
    register(DOMAIN, SERVICE_COMPLETE, complete, COMPLETE_SCHEMA, SupportsResponse.OPTIONAL)
    register(DOMAIN, SERVICE_UNDO, undo, TARGET_SCHEMA, SupportsResponse.OPTIONAL)
    register(DOMAIN, SERVICE_ADD, add, ADD_SCHEMA, SupportsResponse.OPTIONAL)
    register(DOMAIN, SERVICE_UPDATE, update, UPDATE_SCHEMA, SupportsResponse.OPTIONAL)
    register(DOMAIN, SERVICE_REMOVE, remove, TARGET_SCHEMA)
    register(DOMAIN, SERVICE_RESTORE, restore, RESTORE_SCHEMA)
