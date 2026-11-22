"""Setup, device, entities, completion as HA users, and persistence across restarts."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockUser,
    async_capture_events,
)

from custom_components.boligloggen.const import DOMAIN, EVENT_TASK_COMPLETED

from .conftest import SetupEntry


def task_by_key(entry: MockConfigEntry, key: str) -> Any:
    return next(t for t in entry.runtime_data.tasks.values() if t.key == key)


def entity_id(hass: HomeAssistant, entry: MockConfigEntry, key: str, kind: str) -> str:
    task = task_by_key(entry, key)
    domain = "sensor" if kind == "sensor" else "button"
    eid = er.async_get(hass).async_get_entity_id(
        domain, DOMAIN, f"{entry.entry_id}_{task.id}_{kind}"
    )
    assert eid is not None
    return eid


async def test_setup_creates_service_device_and_entities(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    entry = await setup_entry()
    coordinator = entry.runtime_data
    n_tasks = len(coordinator.active_tasks)
    assert n_tasks == 32

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.name == "Enebolig"
    assert device.manufacturer == "Boligloggen"

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert all(e.device_id == device.id for e in entities)
    by_domain: dict[str, int] = {}
    for e in entities:
        by_domain[e.domain] = by_domain.get(e.domain, 0) + 1
    assert by_domain == {"sensor": n_tasks + 4, "button": n_tasks, "calendar": 1}

    # Aggregate sensors get English object ids from translation keys.
    for object_id in ("next_task", "overdue", "due_soon", "last_completed"):
        assert hass.states.get(f"sensor.enebolig_{object_id}") is not None

    smoke = hass.states.get(entity_id(hass, entry, "smoke_alarm_check", "sensor"))
    assert smoke is not None
    assert smoke.state == "2026-12-01"
    assert smoke.attributes["status"] == "due_soon"
    assert smoke.attributes["days_until_due"] == 9
    assert smoke.attributes["schedule"]["text"] == "Årlig 1. des"
    assert smoke.attributes["category"] == "safety"
    assert smoke.attributes["icon"] == "mdi:shield-check"
    assert smoke.attributes["device_class"] == "date"

    next_task = hass.states.get("sensor.enebolig_next_task")
    assert next_task.attributes["next_due"] == "2026-12-01"  # tie broken by title
    assert next_task.state == "Kontroller brannslukker og brannteppe"
    due_soon = hass.states.get("sensor.enebolig_due_soon")
    assert int(due_soon.state) == len(due_soon.attributes["tasks"]) >= 2


async def test_review_feedback_recorded_in_store(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_storage: dict[str, Any]
) -> None:
    entry = await setup_entry(keys=["smoke_alarm_check", "clean_drains#1"])
    stored = hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"]
    assert len(stored["tasks"]) == 2
    feedback = stored["onboarding_feedback"]
    assert "clean_drains#2" in feedback["deselected_at_review"]
    assert "clean_drains#1" not in feedback["deselected_at_review"]
    assert "heat_pump_filter" in feedback["deselected_at_review"]
    assert stored["profile"]["name"] == "Enebolig"


async def test_button_press_records_user_and_survives_restart(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    hass_admin_user: MockUser,
    hass_member_user: MockUser,
    hass_storage: dict[str, Any],
) -> None:
    entry = await setup_entry()
    events = async_capture_events(hass, EVENT_TASK_COMPLETED)

    drains = entity_id(hass, entry, "clean_drains#1", "button")
    smoke = entity_id(hass, entry, "smoke_alarm_check", "button")
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": drains},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": smoke},
        blocking=True,
        context=Context(user_id=hass_member_user.id),
    )
    await hass.async_block_till_done()

    drains_sensor = entity_id(hass, entry, "clean_drains#1", "sensor")
    smoke_sensor = entity_id(hass, entry, "smoke_alarm_check", "sensor")
    assert hass.states.get(drains_sensor).attributes["last_completed_by"] == hass_admin_user.name
    assert hass.states.get(smoke_sensor).attributes["last_completed_by"] == (hass_member_user.name)
    assert hass.states.get(drains_sensor).state == "2027-02-22"
    assert hass.states.get(smoke_sensor).state == "2027-12-01"
    last = hass.states.get("sensor.enebolig_last_completed")
    assert last.state == "Test røykvarslere og bytt batteri"
    assert last.attributes["user_name"] == hass_member_user.name

    assert [e.data["user_name"] for e in events] == [hass_admin_user.name, hass_member_user.name]
    assert events[1].data["occurrence_date"] == "2026-12-01"
    assert events[1].data["property_name"] == "Enebolig"

    # Restart: unload + setup again, state is read back from the Store.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    stored = hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"]
    assert [e["user_id"] for e in stored["log"]] == [hass_admin_user.id, hass_member_user.id]
    assert hass.states.get(drains_sensor).attributes["last_completed_by"] == hass_admin_user.name
    assert hass.states.get(smoke_sensor).state == "2027-12-01"


async def test_button_press_without_user_is_logged_as_system(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    entry = await setup_entry()
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, entry, "clean_drains#1", "button")},
        blocking=True,
    )
    assert entry.runtime_data.log[-1].user_name == "System"
    assert entry.runtime_data.log[-1].user_id is None


async def test_button_press_on_fixed_task_outside_window_is_rejected(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    entry = await setup_entry()
    button = entity_id(hass, entry, "wood_deck_oil", "button")  # due 1 June
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    assert err.value.translation_key == "not_due_yet"
    assert entry.runtime_data.log == []


async def test_unload_and_remove_entry_deletes_store(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_storage: dict[str, Any]
) -> None:
    entry = await setup_entry()
    key = f"{DOMAIN}.{entry.entry_id}"
    assert key in hass_storage
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage


async def test_orphaned_entities_removed_on_setup(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    entry = await setup_entry(keys=["smoke_alarm_check"])
    registry = er.async_get(hass)
    orphan = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_deadbeef_sensor", config_entry=entry
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(orphan.entity_id) is None


async def test_store_migration_hook_normalises_old_data(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_storage: dict[str, Any]
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gammel",
        data={
            "profile": {
                "name": "Gammel",
                "type": "apartment",
                "build_year": 2000,
                "attributes": {},
            },
            "selected_template_ids": [],
            "deselected_template_ids": [],
            "language": "nb",
        },
    )
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
        "version": 1,
        "minor_version": 0,
        "key": f"{DOMAIN}.{entry.entry_id}",
        "data": {
            "profile": {
                "name": "Gammel",
                "type": "apartment",
                "build_year": 2000,
                "attributes": {},
            },
            "tasks": [],
        },
    }
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data
    assert coordinator.log == []
    assert coordinator.feedback["added_later"] == []
