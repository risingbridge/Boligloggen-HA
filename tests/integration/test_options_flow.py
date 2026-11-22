"""Options flow: all six plan-editing actions."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.boligloggen.const import DOMAIN

from .conftest import HOUSE_PROFILE, SetupEntry


async def _menu(hass: HomeAssistant, entry_id: str, action: str) -> Any:
    result = await hass.config_entries.options.async_init(entry_id)
    assert result["type"] is FlowResultType.MENU
    assert set(result["menu_options"]) == {
        "add_catalog",
        "add_custom",
        "edit_task",
        "remove_task",
        "restore_task",
        "profile",
    }
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": action}
    )


async def _submit(hass: HomeAssistant, result: Any, data: dict[str, Any]) -> Any:
    return await hass.config_entries.options.async_configure(result["flow_id"], data)


def _options(result: Any, field: str) -> list[str]:
    schema = result["data_schema"].schema
    key = next(k for k in schema if str(k) == field)
    return [o["value"] for o in schema[key].config["options"]]


def _by_key(entry: Any, key: str) -> Any:
    return next(t for t in entry.runtime_data.tasks.values() if t.key == key)


async def test_add_from_catalog_and_show_all(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    entry = await setup_entry(keys=["smoke_alarm_check"])
    result = await _menu(hass, entry.entry_id, "add_catalog")
    matched = _options(result, "templates")
    assert "heat_pump_filter" in matched and "smoke_alarm_check" not in matched
    assert "cabin_season_close" not in matched

    # Toggle "show all" without choosing → form re-renders with non-matching templates.
    result = await _submit(hass, result, {"show_all": True, "templates": []})
    assert result["type"] is FlowResultType.FORM
    assert "cabin_season_close" in _options(result, "templates")

    result = await _submit(
        hass, result, {"show_all": True, "templates": ["heat_pump_filter", "cabin_season_close"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    keys = {t.key for t in entry.runtime_data.active_tasks}
    assert keys == {"smoke_alarm_check", "heat_pump_filter", "cabin_season_close"}
    assert entry.runtime_data.feedback["added_later"] == ["heat_pump_filter", "cabin_season_close"]
    # Entities appear dynamically.
    task = _by_key(entry, "heat_pump_filter")
    assert er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, f"{entry.entry_id}_{task.id}_button"
    )


async def test_add_custom_task(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    entry = await setup_entry(keys=[])
    result = await _menu(hass, entry.entry_id, "add_custom")
    base = {
        "title": "Sjekk båten",
        "description": "",
        "category": "outdoor",
        "every": 1,
        "unit": "years",
        "dates": "",
    }
    result = await _submit(hass, result, {**base, "schedule_type": "fixed", "dates": "31.2"})
    assert result["errors"] == {"dates": "invalid_date"}
    result = await _submit(hass, result, {**base, "schedule_type": "fixed", "dates": "1.5, 10-01"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    task = entry.runtime_data.active_tasks[0]
    assert task.template_id is None
    assert task.schedule.to_dict() == {
        "type": "fixed",
        "dates": [{"month": 5, "day": 1}, {"month": 10, "day": 1}],
    }
    assert task.next_due.isoformat() == "2027-05-01"
    assert task.due_soon_days == 14  # shortest gap is 5 months → ≤ 6 months
    await hass.async_block_till_done()


async def test_edit_task_last_done_recomputes_next_due(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    entry = await setup_entry(keys=["heat_pump_filter"])
    task = entry.runtime_data.active_tasks[0]
    result = await _menu(hass, entry.entry_id, "edit_task")
    result = await _submit(hass, result, {"task_id": task.id})
    assert result["step_id"] == "edit_task_fields"
    form = {
        "title": "Rens varmepumpefilter",
        "description": "",
        "category": "heating",
        "schedule_type": "interval",
        "every": 3,
        "unit": "months",
        "dates": "",
        "due_soon_days": 10,
        "last_completed": "2026-10-01",
        "next_due": task.next_due.isoformat(),
    }
    result = await _submit(hass, result, form)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    updated = entry.runtime_data.tasks[task.id]
    assert updated.title == "Rens varmepumpefilter"
    assert updated.last_completed.isoformat() == "2026-10-01"
    assert updated.next_due.isoformat() == "2027-01-01"
    assert updated.due_soon_days == 10
    await hass.async_block_till_done()


async def test_remove_and_restore(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    entry = await setup_entry(keys=["smoke_alarm_check", "heat_pump_filter"])
    task = _by_key(entry, "heat_pump_filter")
    registry = er.async_get(hass)
    sensor_uid = f"{entry.entry_id}_{task.id}_sensor"

    result = await _menu(hass, entry.entry_id, "remove_task")
    result = await _submit(hass, result, {"task_ids": [task.id]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.tasks[task.id].status == "archived"
    assert registry.async_get_entity_id("sensor", DOMAIN, sensor_uid) is None
    assert entry.runtime_data.feedback["removed_later"] == ["heat_pump_filter"]

    result = await _menu(hass, entry.entry_id, "restore_task")
    assert _options(result, "task_ids") == [task.id]
    result = await _submit(hass, result, {"task_ids": [task.id]})
    await hass.async_block_till_done()
    assert entry.runtime_data.tasks[task.id].status == "active"
    assert registry.async_get_entity_id("sensor", DOMAIN, sensor_uid) is not None
    assert entry.runtime_data.feedback["removed_later"] == []

    result = await _menu(hass, entry.entry_id, "restore_task")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_archived"


async def test_edit_profile_shows_diff_and_archived_do_not_return(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    entry = await setup_entry()
    coordinator = entry.runtime_data
    # Archive a still-matching task first: it must not be suggested again.
    coordinator.async_archive([_by_key(entry, "leaf_raking").id])

    result = await _menu(hass, entry.entry_id, "profile")
    assert result["step_id"] == "profile"
    result = await _submit(
        hass, result, {"name": "Nytt navn", "address": "", "type": "house", "build_year": 1985}
    )
    result = await _submit(
        hass,
        result,
        {
            "heating": ["hydronic"],
            "ventilation": "natural",
            "cladding": "wood",
            "bathroom_count": "3",
        },
    )
    result = await _submit(
        hass,
        result,
        {
            "garden": "yes",
            "driveway": "pavers",
            "deck": "wood",
            "garage": "garage_with_door",
            "water": "public",
        },
    )
    assert result["step_id"] == "profile_review"
    add = set(_options(result, "add"))
    remove_ids = _options(result, "remove")
    remove = {coordinator.tasks[i].key for i in remove_ids}
    assert add == {
        "bleed_radiators",
        "hydronic_pressure_check",
        "clean_drains#3",
        "wet_room_sealant_check#3",
    }
    assert remove == {
        "chimney_stove_inspection",
        "stove_gasket_check",
        "heat_pump_filter",
        "heat_pump_outdoor_rinse",
        "heat_pump_condensate_drain",
    }
    assert "leaf_raking" not in add

    # Accept the additions, keep the stove tasks.
    keep = {_by_key(entry, "chimney_stove_inspection").id, _by_key(entry, "stove_gasket_check").id}
    result = await _submit(
        hass, result, {"add": sorted(add), "remove": [i for i in remove_ids if i not in keep]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    active = {t.key for t in coordinator.active_tasks}
    assert add <= active
    assert "chimney_stove_inspection" in active and "heat_pump_filter" not in active
    assert coordinator.profile.name == "Nytt navn"
    assert coordinator.profile.attributes.heating == ("hydronic",)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device.name == "Nytt navn"
    assert entry.title == "Nytt navn"


async def test_edit_profile_prefills_current_values(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    entry = await setup_entry()
    result = await _menu(hass, entry.entry_id, "profile")
    result = await _submit(
        hass,
        result,
        {**{k: HOUSE_PROFILE[k] for k in ("name", "type")}, "address": "", "build_year": 1985},
    )
    schema = result["data_schema"].schema
    defaults = {str(k): k.default() for k in schema if callable(getattr(k, "default", None))}
    assert defaults["heating"] == ["wood_stove", "heat_pump"]
    assert defaults["bathroom_count"] == "2"
