"""Fixtures for Home Assistant integration tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.boligloggen.const import (
    CONF_DESELECTED,
    CONF_LANGUAGE,
    CONF_PROFILE,
    CONF_SELECTED,
    DOMAIN,
)
from custom_components.boligloggen.planner import PropertyProfile, load_catalog, suggest

FROZEN_NOW = "2026-11-22 12:00:00+01:00"

HOUSE_PROFILE: dict[str, Any] = {
    "name": "Enebolig",
    "address": "Eksempelveien 1",
    "type": "house",
    "build_year": 1985,
    "age_band": None,
    "attributes": {
        "heating": ["wood_stove", "heat_pump"],
        "ventilation": "natural",
        "cladding": "wood",
        "bathroom_count": 2,
        "garden": True,
        "driveway": "pavers",
        "deck": "wood",
        "garage": "garage_with_door",
        "water": "public",
        "cabin_winter_use": None,
        "cabin_water": None,
    },
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom_components in all integration tests."""


@pytest.fixture
async def hass_member_user(hass: HomeAssistant) -> MockUser:
    """A regular (non-admin) household member with normal permissions."""
    group = await hass.auth.async_get_group(GROUP_ID_USER)
    assert group is not None
    return MockUser(name="Kari", groups=[group]).add_to_hass(hass)


@pytest.fixture(autouse=True)
async def _frozen_time(hass: HomeAssistant, freezer: Any) -> None:
    await hass.config.async_set_time_zone("Europe/Oslo")
    freezer.move_to(FROZEN_NOW)


def entry_data(profile: dict[str, Any], keys: list[str] | None = None) -> dict[str, Any]:
    from datetime import date

    prof = PropertyProfile.from_dict(profile)
    all_keys = [s.key for s in suggest(load_catalog(), prof, date(2026, 11, 22))]
    selected = keys if keys is not None else all_keys
    return {
        CONF_PROFILE: prof.to_dict(),
        CONF_SELECTED: selected,
        CONF_DESELECTED: [k for k in all_keys if k not in selected],
        CONF_LANGUAGE: "nb",
    }


SetupEntry = Callable[..., Awaitable[MockConfigEntry]]


@pytest.fixture
def setup_entry(hass: HomeAssistant) -> SetupEntry:
    async def _setup(
        profile: dict[str, Any] | None = None, keys: list[str] | None = None
    ) -> MockConfigEntry:
        profile = profile or HOUSE_PROFILE
        entry = MockConfigEntry(
            domain=DOMAIN, title=profile["name"], data=entry_data(profile, keys)
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return _setup
