"""Read-only websocket API for the future årshjul card."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.const import ERR_INVALID_FORMAT, ERR_NOT_FOUND
from homeassistant.components.websocket_api.decorators import websocket_command
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, KIND_BUTTON, KIND_SENSOR
from .planner import describe_schedule, task_status

if TYPE_CHECKING:
    from .coordinator import BoligloggenCoordinator

DEFAULT_LOG_LIMIT = 50
MAX_LOG_LIMIT = 500


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_properties)
    websocket_api.async_register_command(hass, ws_tasks)
    websocket_api.async_register_command(hass, ws_year_plan)
    websocket_api.async_register_command(hass, ws_log)


def _get(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> BoligloggenCoordinator | None:
    entry = hass.config_entries.async_get_entry(msg["config_entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        connection.send_error(msg["id"], ERR_NOT_FOUND, "Property not found")
        return None
    coordinator: BoligloggenCoordinator = entry.runtime_data
    return coordinator


@websocket_command({vol.Required("type"): "boligloggen/properties"})
@callback
def ws_properties(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    result = []
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        coordinator: BoligloggenCoordinator = entry.runtime_data
        result.append(
            {
                "config_entry_id": entry.entry_id,
                "name": coordinator.profile.name,
                "type": coordinator.profile.type,
            }
        )
    connection.send_result(msg["id"], result)


@websocket_command(
    {
        vol.Required("type"): "boligloggen/tasks",
        vol.Required("config_entry_id"): str,
        vol.Optional("include_archived", default=False): bool,
    }
)
@callback
def ws_tasks(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    if (coordinator := _get(hass, connection, msg)) is None:
        return
    today = coordinator.today()
    tasks = coordinator.tasks.values() if msg["include_archived"] else coordinator.active_tasks
    result = []
    for task in tasks:
        last = coordinator.latest_entry(task.id)
        result.append(
            {
                **task.to_dict(),
                "due_status": task_status(task, today),
                "days_until_due": (task.next_due - today).days,
                "schedule_text": describe_schedule(task.schedule, coordinator.language),
                "last_completed_by": last.user_name if last else None,
                "sensor_entity_id": coordinator.entity_id_for(task.id, KIND_SENSOR),
                "button_entity_id": coordinator.entity_id_for(task.id, KIND_BUTTON),
            }
        )
    connection.send_result(msg["id"], result)


@websocket_command(
    {
        vol.Required("type"): "boligloggen/year_plan",
        vol.Required("config_entry_id"): str,
        vol.Required("year"): vol.All(int, vol.Range(min=2000, max=2200)),
    }
)
@callback
def ws_year_plan(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    if (coordinator := _get(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], coordinator.year_plan(msg["year"]))


@websocket_command(
    {
        vol.Required("type"): "boligloggen/log",
        vol.Required("config_entry_id"): str,
        vol.Optional("limit", default=DEFAULT_LOG_LIMIT): vol.All(
            int, vol.Range(min=1, max=MAX_LOG_LIMIT)
        ),
        vol.Optional("before"): str,
        vol.Optional("task_id"): str,
    }
)
@callback
def ws_log(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """Newest first. ``before`` is a log entry id (cursor) or an ISO date.

    Returns ``{entries, next_before}``; ``next_before`` is ``None`` on the last page.
    """
    if (coordinator := _get(hass, connection, msg)) is None:
        return
    entries = list(reversed(coordinator.log))
    if task_id := msg.get("task_id"):
        entries = [e for e in entries if e.task_id == task_id]
    if before := msg.get("before"):
        ids = [e.id for e in entries]
        if before in ids:
            entries = entries[ids.index(before) + 1 :]
        else:
            try:
                cutoff = date.fromisoformat(before)
            except ValueError:
                connection.send_error(msg["id"], ERR_INVALID_FORMAT, "Bad cursor")
                return
            entries = [e for e in entries if e.completed_on < cutoff]
    page = entries[: msg["limit"]]
    titles = {t.id: t.title for t in coordinator.tasks.values()}
    connection.send_result(
        msg["id"],
        {
            "entries": [{**e.to_dict(), "title": titles.get(e.task_id)} for e in page],
            "next_before": page[-1].id if len(entries) > len(page) else None,
        },
    )
