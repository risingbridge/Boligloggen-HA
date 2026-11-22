"""Export / import over the websocket API (admin panel backend)."""

from __future__ import annotations

import copy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_capture_events
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.boligloggen.const import DOMAIN, EVENT_TASK_DUE_SOON, EVENT_TASK_OVERDUE

from .conftest import HOUSE_PROFILE, SetupEntry


def _task(entry: Any, key: str) -> Any:
    return next(t for t in entry.runtime_data.tasks.values() if t.key == key)


async def _ws(client: Any, **msg: Any) -> dict[str, Any]:
    await client.send_json_auto_id(msg)
    result: dict[str, Any] = await client.receive_json()
    return result


def _sensor(hass: HomeAssistant, entry: Any, task_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{task_id}_sensor"
    )


async def test_export_then_restore_backup_keeps_entities(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await setup_entry(keys=["smoke_alarm_check", "heat_pump_filter", "clean_drains#1"])
    smoke = _task(entry, "smoke_alarm_check")
    pump = _task(entry, "heat_pump_filter")
    await hass.services.async_call(
        DOMAIN,
        "complete_task",
        {"config_entry_id": entry.entry_id, "task_id": smoke.id, "note": "OK"},
        blocking=True,
    )
    client = await hass_ws_client(hass)

    msg = await _ws(client, type="boligloggen/export", config_entry_id=entry.entry_id)
    backup = msg["result"]
    assert backup["format"] == "boligloggen-export"
    assert backup["format_version"] == 1
    assert backup["integration_version"]
    assert backup["property"]["profile"]["name"] == "Enebolig"
    assert len(backup["property"]["tasks"]) == 3
    assert backup["property"]["log"][0]["note"] == "OK"
    smoke_entity = _sensor(hass, entry, smoke.id)

    # Change the plan after the backup: remove a task, add one, undo the completion.
    coordinator = entry.runtime_data
    coordinator.async_archive([pump.id])
    await hass.services.async_call(
        DOMAIN,
        "add_task",
        {"config_entry_id": entry.entry_id, "template_id": "leaf_raking"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "undo_completion", {"config_entry_id": entry.entry_id, "task_id": smoke.id}
    )
    await hass.async_block_till_done()
    added = _task(entry, "leaf_raking")
    assert _sensor(hass, entry, added.id)

    # Restore the backup.
    msg = await _ws(client, type="boligloggen/import", config_entry_id=entry.entry_id, data=backup)
    assert msg["success"], msg
    assert msg["result"] == {
        "name": "Enebolig",
        "tasks": 3,
        "active_tasks": 3,
        "log_entries": 1,
        "history_imported": True,
    }
    await hass.async_block_till_done()
    assert {t.key for t in coordinator.active_tasks} == {
        "smoke_alarm_check",
        "heat_pump_filter",
        "clean_drains#1",
    }
    assert coordinator.log[0].note == "OK"
    # Same task ids → same entity IDs; the task added after the backup is gone.
    assert _sensor(hass, entry, smoke.id) == smoke_entity
    assert _sensor(hass, entry, pump.id) is not None
    assert hass.states.get(_sensor(hass, entry, pump.id) or "") is not None
    assert _sensor(hass, entry, added.id) is None
    # Persisted.
    saved = coordinator.data_to_save()
    assert len(saved["tasks"]) == 3 and len(saved["log"]) == 1


async def test_import_into_other_property_without_history(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_ws_client: WebSocketGenerator
) -> None:
    due_soon = async_capture_events(hass, EVENT_TASK_DUE_SOON)
    overdue = async_capture_events(hass, EVENT_TASK_OVERDUE)
    house = await setup_entry(keys=["smoke_alarm_check", "window_washing"])
    await hass.services.async_call(
        DOMAIN,
        "complete_task",
        {
            "config_entry_id": house.entry_id,
            "task_id": _task(house, "window_washing").id,
            "force": True,
        },
        blocking=True,
    )
    cabin_profile = {**HOUSE_PROFILE, "name": "Hytta", "type": "cabin"}
    cabin = await setup_entry(profile=cabin_profile, keys=[])
    client = await hass_ws_client(hass)
    backup = (await _ws(client, type="boligloggen/export", config_entry_id=house.entry_id))[
        "result"
    ]
    # An overdue task in the file must not fire events on import.
    backup["property"]["tasks"][0]["next_due"] = "2026-10-01"
    backup["property"]["tasks"][0]["last_notified_state"] = "ok"

    msg = await _ws(
        client,
        type="boligloggen/import",
        config_entry_id=cabin.entry_id,
        data=backup,
        include_history=False,
    )
    assert msg["success"], msg
    await hass.async_block_till_done()
    coordinator = cabin.runtime_data
    assert coordinator.profile.name == "Enebolig"
    assert {t.key for t in coordinator.active_tasks} == {"smoke_alarm_check", "window_washing"}
    assert coordinator.log == []  # history not imported
    assert msg["result"]["history_imported"] is False
    for task in coordinator.active_tasks:
        assert _sensor(hass, cabin, task.id)
    assert due_soon == [] and overdue == []
    # The device and entry are renamed with the imported profile.
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, cabin.entry_id)})
    assert device is not None and device.name == "Enebolig"
    assert cabin.title == "Enebolig"
    # The source property is untouched.
    assert len(house.runtime_data.log) == 1


async def test_invalid_import_changes_nothing(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await setup_entry(keys=["smoke_alarm_check"])
    client = await hass_ws_client(hass)
    backup = (await _ws(client, type="boligloggen/export", config_entry_id=entry.entry_id))[
        "result"
    ]
    before = copy.deepcopy(entry.runtime_data.data_to_save())

    msg = await _ws(
        client, type="boligloggen/import", config_entry_id=entry.entry_id, data={"tasks": []}
    )
    assert msg["error"]["code"] == "not_boligloggen_file"

    broken = copy.deepcopy(backup)
    broken["property"]["tasks"][0]["category"] = "garden"
    msg = await _ws(client, type="boligloggen/import", config_entry_id=entry.entry_id, data=broken)
    assert msg["error"]["code"] == "invalid_content"
    assert "tasks[0].category" in msg["error"]["message"]

    newer = {**backup, "format_version": 2}
    msg = await _ws(client, type="boligloggen/import", config_entry_id=entry.entry_id, data=newer)
    assert msg["error"]["code"] == "unsupported_version"

    assert entry.runtime_data.data_to_save() == before


async def test_export_and_import_require_admin(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    entry = await setup_entry(keys=["smoke_alarm_check"])
    client = await hass_ws_client(hass, hass_read_only_access_token)
    msg = await _ws(client, type="boligloggen/export", config_entry_id=entry.entry_id)
    assert msg["error"]["code"] == "unauthorized"
    msg = await _ws(client, type="boligloggen/import", config_entry_id=entry.entry_id, data={})
    assert msg["error"]["code"] == "unauthorized"
