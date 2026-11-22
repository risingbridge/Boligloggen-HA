"""Boligloggen – a tailored home maintenance plan inside Home Assistant.

Standalone: no cloud, no network calls. One config entry = one property.
"""

from __future__ import annotations

from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType

from .catalog_loader import async_get_catalog
from .const import DOMAIN, MANUFACTURER, PLATFORMS, SCAN_HOUR, SCAN_MINUTE
from .coordinator import BoligloggenCoordinator
from .store import BoligloggenStore

type BoligloggenConfigEntry = ConfigEntry[BoligloggenCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services and websocket commands once for the integration."""
    from .services import async_setup_services
    from .websocket import async_setup_websocket

    async_setup_services(hass)
    async_setup_websocket(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BoligloggenConfigEntry) -> bool:
    catalog = await async_get_catalog(hass)
    coordinator = BoligloggenCoordinator(hass, entry, catalog)
    await coordinator.async_load()
    entry.runtime_data = coordinator

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=coordinator.profile.name,
        manufacturer=MANUFACTURER,
        model=coordinator.profile.type,
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    coordinator.async_remove_orphaned_entities()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _daily_scan(_now: datetime) -> None:
        coordinator.async_scan()

    entry.async_on_unload(
        async_track_time_change(hass, _daily_scan, hour=SCAN_HOUR, minute=SCAN_MINUTE, second=0)
    )
    # Startup scan: compares against the persisted last_notified_state, so a
    # restart never re-fires events for transitions already announced.
    coordinator.async_scan()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BoligloggenConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.store.async_save(entry.runtime_data.data_to_save())
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the property's stored plan and log when the entry is removed."""
    await BoligloggenStore(hass, entry.entry_id).async_remove()
