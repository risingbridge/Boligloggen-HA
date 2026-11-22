"""The shipped notification blueprint sends notifications for Boligloggen events."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockUser, async_mock_service

from custom_components.boligloggen.const import DOMAIN

from .conftest import SetupEntry

BLUEPRINT = (
    Path(__file__).resolve().parents[2]
    / "blueprints"
    / "automation"
    / "boligloggen"
    / "notify_due.yaml"
)


async def _setup_automation(hass: HomeAssistant, entry_id: str, **inputs: Any) -> None:
    target = Path(hass.config.path("blueprints", "automation", "boligloggen"))
    await hass.async_add_executor_job(lambda: target.mkdir(parents=True, exist_ok=True))
    await hass.async_add_executor_job(shutil.copy, BLUEPRINT, target / "notify_due.yaml")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "boligloggen_notify",
                "use_blueprint": {
                    "path": "boligloggen/notify_due.yaml",
                    "input": {"property": entry_id, "notify_action": "notify.test", **inputs},
                },
            }
        },
    )
    await hass.async_block_till_done()


async def test_blueprint_notifies_on_events(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_member_user: MockUser
) -> None:
    entry = await setup_entry(keys=["clean_drains#1"])
    calls = async_mock_service(hass, "notify", "test")
    await _setup_automation(hass, entry.entry_id, send_completed=True)

    hass.bus.async_fire(
        "boligloggen_task_overdue",
        {
            "config_entry_id": entry.entry_id,
            "property_name": "Enebolig",
            "title": "Rens sluk",
            "next_due": "2026-11-01",
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["title"] == "Enebolig"
    assert "«Rens sluk» har forfalt" in calls[0].data["message"]

    # Other properties are ignored.
    hass.bus.async_fire(
        "boligloggen_task_overdue", {"config_entry_id": "other", "title": "X", "next_due": ""}
    )
    await hass.async_block_till_done()
    assert len(calls) == 1

    # A real completion by a member triggers a "completed" notification.
    task = entry.runtime_data.active_tasks[0]
    await hass.services.async_call(
        DOMAIN,
        "complete_task",
        {"config_entry_id": entry.entry_id, "task_id": task.id, "note": "Gjort"},
        blocking=True,
        context=Context(user_id=hass_member_user.id),
    )
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert "Kari fullførte «Rens sluk – bad 1»: Gjort" in calls[1].data["message"]


async def test_blueprint_respects_toggles(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    entry = await setup_entry(keys=["clean_drains#1"])
    calls = async_mock_service(hass, "notify", "test")
    await _setup_automation(hass, entry.entry_id, send_due_soon=False)
    hass.bus.async_fire(
        "boligloggen_task_due_soon",
        {"config_entry_id": entry.entry_id, "property_name": "E", "title": "X", "next_due": ""},
    )
    await hass.async_block_till_done()
    assert calls == []
