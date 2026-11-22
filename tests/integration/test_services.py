"""Services: targets, completion guard, undo, admin permissions (admin / member / system)."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockUser

from custom_components.boligloggen.const import DOMAIN

from .conftest import SetupEntry


def _task(entry: Any, key: str) -> Any:
    return next(t for t in entry.runtime_data.tasks.values() if t.key == key)


def _eid(hass: HomeAssistant, entry: Any, key: str, kind: str = "sensor") -> str:
    domain = "sensor" if kind == "sensor" else "button"
    eid = er.async_get(hass).async_get_entity_id(
        domain, DOMAIN, f"{entry.entry_id}_{_task(entry, key).id}_{kind}"
    )
    assert eid
    return eid


async def _call(
    hass: HomeAssistant,
    service: str,
    data: dict[str, Any],
    user: MockUser | None = None,
    response: bool = False,
) -> Any:
    return await hass.services.async_call(
        DOMAIN,
        service,
        data,
        blocking=True,
        context=Context(user_id=user.id if user else None),
        return_response=response,
    )


async def test_complete_by_entity_or_ids_with_note_and_date(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_member_user: MockUser
) -> None:
    entry = await setup_entry()
    response = await _call(
        hass,
        "complete_task",
        {
            "entity_id": _eid(hass, entry, "heat_pump_filter"),
            "note": "Byttet",
            "completed_on": "2026-11-20",
        },
        hass_member_user,
        response=True,
    )
    log = response["log_entry"]
    assert log["note"] == "Byttet"
    assert log["completed_on"] == "2026-11-20"
    assert log["user_name"] == "Kari"
    assert _task(entry, "heat_pump_filter").next_due.isoformat() == "2027-02-20"

    # By config_entry_id + task_id, via the button entity's id as well.
    task = _task(entry, "clean_drains#1")
    await _call(
        hass,
        "complete_task",
        {"config_entry_id": entry.entry_id, "task_id": task.id},
        hass_member_user,
    )
    await _call(
        hass,
        "complete_task",
        {"entity_id": _eid(hass, entry, "clean_drains#2", "button")},
        hass_member_user,
    )
    assert len(entry.runtime_data.log) == 3


async def test_complete_validation_errors(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    entry = await setup_entry()
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass,
            "complete_task",
            {"entity_id": _eid(hass, entry, "heat_pump_filter"), "completed_on": "2026-12-24"},
        )
    assert err.value.translation_key == "completed_on_in_future"
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "complete_task", {})
    assert err.value.translation_key == "task_target_required"
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "complete_task", {"entity_id": "sensor.enebolig_next_task"})
    assert err.value.translation_key == "not_a_task_entity"
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "complete_task", {"config_entry_id": "nope", "task_id": "x"})
    assert err.value.translation_key == "property_not_found"


async def test_fixed_task_guard_and_force(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_member_user: MockUser
) -> None:
    entry = await setup_entry()
    target = {"entity_id": _eid(hass, entry, "wood_deck_oil")}  # due 1 June 2027
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "complete_task", target, hass_member_user)
    assert err.value.translation_key == "not_due_yet"
    assert err.value.translation_placeholders["date"] == "2027-05-11"  # 21 days before

    await _call(hass, "complete_task", {**target, "force": True}, hass_member_user)
    assert entry.runtime_data.log[-1].forced is True
    assert _task(entry, "wood_deck_oil").next_due.isoformat() == "2028-06-01"

    # Fixed task inside its window needs no force.
    await _call(
        hass,
        "complete_task",
        {"entity_id": _eid(hass, entry, "smoke_alarm_check")},
        hass_member_user,
    )


async def test_undo_permissions(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    hass_admin_user: MockUser,
    hass_member_user: MockUser,
) -> None:
    entry = await setup_entry()
    target = {"entity_id": _eid(hass, entry, "heat_pump_filter")}
    before = _task(entry, "heat_pump_filter")
    await _call(hass, "complete_task", target, hass_admin_user)

    # A member can't undo someone else's completion…
    with pytest.raises(Unauthorized):
        await _call(hass, "undo_completion", target, hass_member_user)
    # …but an admin can.
    await _call(hass, "undo_completion", target, hass_admin_user)
    assert _task(entry, "heat_pump_filter").next_due == before.next_due
    assert _task(entry, "heat_pump_filter").last_completed == before.last_completed
    assert entry.runtime_data.log == []

    # The member can undo their own.
    await _call(hass, "complete_task", target, hass_member_user)
    await _call(hass, "undo_completion", target, hass_member_user)
    assert entry.runtime_data.log == []

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "undo_completion", target, hass_admin_user)
    assert err.value.translation_key == "nothing_to_undo"


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("add_task", {"template_id": "bleed_radiators"}),
        ("update_task", {"title": "X"}),
        ("remove_task", {}),
        ("restore_task", {}),
    ],
)
async def test_admin_services_reject_non_admin(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    hass_member_user: MockUser,
    service: str,
    data: dict[str, Any],
) -> None:
    entry = await setup_entry()
    task = _task(entry, "heat_pump_filter")
    payload = {"config_entry_id": entry.entry_id, "task_id": task.id, **data}
    if service == "add_task":
        payload.pop("task_id")
    with pytest.raises(Unauthorized):
        await _call(hass, service, payload, hass_member_user)


async def test_admin_and_system_can_edit_plan(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_admin_user: MockUser
) -> None:
    entry = await setup_entry(keys=["smoke_alarm_check", "clean_drains#1"])
    coordinator = entry.runtime_data

    # Admin adds a catalog task; system (no user) adds a custom task.
    resp = await _call(
        hass,
        "add_task",
        {"config_entry_id": entry.entry_id, "template_id": "bleed_radiators"},
        hass_admin_user,
        response=True,
    )
    assert len(resp["task_ids"]) == 1
    resp = await _call(
        hass,
        "add_task",
        {
            "config_entry_id": entry.entry_id,
            "title": "Service på bilen",
            "category": "outdoor",
            "schedule_type": "interval",
            "every": 1,
            "unit": "years",
        },
        response=True,
    )
    custom_id = resp["task_ids"][0]
    assert coordinator.tasks[custom_id].template_id is None
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await _call(
            hass, "add_task", {"config_entry_id": entry.entry_id, "title": ""}, hass_admin_user
        )

    resp = await _call(
        hass,
        "update_task",
        {
            "config_entry_id": entry.entry_id,
            "task_id": custom_id,
            "schedule_type": "fixed",
            "dates": ["04-15"],
            "due_soon_days": 5,
        },
        hass_admin_user,
        response=True,
    )
    assert resp["task"]["schedule"] == {"type": "fixed", "dates": [{"month": 4, "day": 15}]}
    assert resp["task"]["due_soon_days"] == 5

    resp = await _call(
        hass,
        "update_task",
        {"config_entry_id": entry.entry_id, "task_id": custom_id, "next_due": "2026-12-24"},
        hass_admin_user,
        response=True,
    )
    assert resp["task"]["next_due"] == "2026-12-24"

    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass,
            "update_task",
            {
                "config_entry_id": entry.entry_id,
                "task_id": custom_id,
                "schedule_type": "fixed",
                "dates": "02-30",
            },
            hass_admin_user,
        )
    assert err.value.translation_key == "invalid_date"

    await _call(
        hass,
        "remove_task",
        {"config_entry_id": entry.entry_id, "task_id": custom_id},
        hass_admin_user,
    )
    await hass.async_block_till_done()
    assert coordinator.tasks[custom_id].status == "archived"
    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{custom_id}_sensor"
        )
        is None
    )
    # Archived task can't be completed.
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass, "complete_task", {"config_entry_id": entry.entry_id, "task_id": custom_id}
        )
    assert err.value.translation_key == "task_archived"

    await _call(hass, "restore_task", {"config_entry_id": entry.entry_id, "task_id": custom_id})
    await hass.async_block_till_done()
    assert coordinator.tasks[custom_id].status == "active"
    assert (
        hass.states.get(
            er.async_get(hass).async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_{custom_id}_sensor"
            )
        )
        is not None
    )


async def test_add_per_bathroom_template_by_id(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    entry = await setup_entry(keys=["clean_drains#1"])
    resp = await _call(
        hass,
        "add_task",
        {"config_entry_id": entry.entry_id, "template_id": "clean_drains"},
        response=True,
    )
    assert len(resp["task_ids"]) == 1
    assert entry.runtime_data.tasks[resp["task_ids"][0]].key == "clean_drains#2"
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass, "add_task", {"config_entry_id": entry.entry_id, "template_id": "no_such_template"}
        )
    assert err.value.translation_key == "unknown_template"
