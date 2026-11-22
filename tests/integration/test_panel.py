"""Admin panel: registration, served module, and the admin-only catalog command."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

from homeassistant.components.frontend import DATA_PANELS
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.boligloggen import panel
from custom_components.boligloggen.const import DOMAIN

from .conftest import SetupEntry


async def test_panel_skipped_without_frontend(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    await setup_entry(keys=["smoke_alarm_check"])
    assert DOMAIN not in hass.data.get(DATA_PANELS, {})


async def test_panel_registered_admin_only(hass: HomeAssistant) -> None:
    hass.config.components.add("frontend")
    hass.http = Mock(async_register_static_paths=AsyncMock())
    assert await panel.async_setup_panel(hass)

    registered = hass.data[DATA_PANELS][panel.PANEL_URL_PATH]
    assert registered.require_admin is True
    assert registered.sidebar_title == "Boligloggen"
    custom = registered.config["_panel_custom"]
    assert custom["name"] == "boligloggen-panel"
    assert custom["module_url"].startswith("/boligloggen_static/boligloggen-panel.js?v=")

    (paths,), _ = hass.http.async_register_static_paths.call_args
    assert paths[0].url_path == "/boligloggen_static"
    served = Path(paths[0].path) / panel.PANEL_FILE
    assert served.is_file()
    # The module defines the element the panel config names.
    assert 'customElements.define("boligloggen-panel"' in served.read_text(encoding="utf-8")


async def test_catalog_command(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await setup_entry(keys=["smoke_alarm_check", "clean_drains#1"])
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "boligloggen/catalog", "config_entry_id": entry.entry_id}
    )
    items = {i["key"]: i for i in (await client.receive_json())["result"]}
    assert "smoke_alarm_check" not in items  # already in the plan
    assert "clean_drains#1" not in items
    assert items["clean_drains#2"]["title"] == "Rens sluk – bad 2"
    assert items["clean_drains#2"]["template_id"] == "clean_drains"
    assert items["heat_pump_filter"]["matches"] is True
    assert items["heat_pump_filter"]["schedule"] == {
        "type": "interval",
        "every": 3,
        "unit": "months",
    }
    assert items["heat_pump_filter"]["schedule_text"]
    assert "cabin_season_close" not in items
    assert all(i["matches"] for i in items.values())

    await client.send_json_auto_id(
        {"type": "boligloggen/catalog", "config_entry_id": entry.entry_id, "show_all": True}
    )
    items = {i["key"]: i for i in (await client.receive_json())["result"]}
    assert items["cabin_season_close"]["matches"] is False

    # A key from the catalog can be passed straight to add_task.
    await hass.services.async_call(
        DOMAIN,
        "add_task",
        {
            "config_entry_id": entry.entry_id,
            "template_id": ["clean_drains#2", "cabin_season_close"],
        },
        blocking=True,
    )
    await client.send_json_auto_id(
        {"type": "boligloggen/catalog", "config_entry_id": entry.entry_id, "show_all": True}
    )
    keys = {i["key"] for i in (await client.receive_json())["result"]}
    assert "clean_drains#2" not in keys and "cabin_season_close" not in keys


async def test_catalog_command_requires_admin(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    entry = await setup_entry(keys=[])
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id(
        {"type": "boligloggen/catalog", "config_entry_id": entry.entry_id}
    )
    msg: dict[str, Any] = await client.receive_json()
    assert msg["success"] is False
    assert msg["error"]["code"] == "unauthorized"
    # The read-only commands stay available to everyone.
    await client.send_json_auto_id({"type": "boligloggen/properties"})
    assert (await client.receive_json())["success"] is True
