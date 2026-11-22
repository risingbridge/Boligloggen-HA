"""Load the bundled catalog once (in the executor) and cache it."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .planner import Catalog, load_catalog

CATALOG_KEY: HassKey[Catalog] = HassKey(f"{DOMAIN}_catalog")


async def async_get_catalog(hass: HomeAssistant) -> Catalog:
    if (catalog := hass.data.get(CATALOG_KEY)) is None:
        catalog = await hass.async_add_executor_job(load_catalog)
        hass.data[CATALOG_KEY] = catalog
    return catalog
