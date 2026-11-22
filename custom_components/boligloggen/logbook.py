"""Describe Boligloggen events in the logbook."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook.const import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, EVENT_TASK_COMPLETED, KIND_SENSOR
from .planner import normalize_language

_MESSAGES = {
    "nb": "fullførte «{title}»",
    "en": "completed “{title}”",
}


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, Any]]], None],
) -> None:
    @callback
    def describe(event: Event) -> dict[str, Any]:
        data = event.data
        entry = hass.config_entries.async_get_entry(data.get("config_entry_id", ""))
        coordinator = getattr(entry, "runtime_data", None) if entry else None
        lang = getattr(coordinator, "language", None) or normalize_language(hass.config.language)
        entity_id = er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{data.get('config_entry_id')}_{data.get('task_id')}_{KIND_SENSOR}"
        )
        result: dict[str, Any] = {
            LOGBOOK_ENTRY_NAME: data.get("user_name") or "System",
            LOGBOOK_ENTRY_MESSAGE: _MESSAGES[lang].format(title=data.get("title", "")),
        }
        if entity_id:
            result[LOGBOOK_ENTRY_ENTITY_ID] = entity_id
        return result

    async_describe_event(DOMAIN, EVENT_TASK_COMPLETED, describe)
