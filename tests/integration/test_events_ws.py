"""Daily scan events (once per transition, across restarts), logbook, calendar, websocket."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockUser,
    async_capture_events,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.boligloggen.const import (
    DOMAIN,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_DUE_SOON,
    EVENT_TASK_OVERDUE,
)

from .conftest import SetupEntry


def _task(entry: Any, key: str) -> Any:
    return next(t for t in entry.runtime_data.tasks.values() if t.key == key)


async def _advance_to(hass: HomeAssistant, freezer: Any, when: str) -> None:
    target = dt_util.as_utc(datetime.fromisoformat(when))
    freezer.move_to(target)
    async_fire_time_changed(hass, target)
    await hass.async_block_till_done()


async def test_due_events_fire_once_per_transition_across_restarts(
    hass: HomeAssistant, setup_entry: SetupEntry, freezer: Any, hass_storage: dict[str, Any]
) -> None:
    due_soon = async_capture_events(hass, EVENT_TASK_DUE_SOON)
    overdue = async_capture_events(hass, EVENT_TASK_OVERDUE)
    # Seeded 22 Nov: smoke alarm (1 Dec) is already due_soon → seeding must not fire.
    entry = await setup_entry(keys=["smoke_alarm_check", "window_washing"])
    assert due_soon == [] and overdue == []

    # Restart: startup scan compares against persisted state → still nothing.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert due_soon == [] and overdue == []

    # 2 Dec 00:05 → smoke alarm becomes overdue: fired once.
    await _advance_to(hass, freezer, "2026-12-02T00:05:00+01:00")
    assert [e.data["title"] for e in overdue] == ["Test røykvarslere og bytt batteri"]
    assert overdue[0].data["status"] == "overdue"
    assert overdue[0].data["entity_id"].startswith("sensor.enebolig_")

    # Next day's scan, and a restart, don't re-fire.
    await _advance_to(hass, freezer, "2026-12-03T00:05:00+01:00")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(overdue) == 1
    stored = hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"]["tasks"]
    assert {
        t["last_notified_state"] for t in stored if t["template_id"] == "smoke_alarm_check"
    } == {"overdue"}

    # Window washing (15 Apr, 14 days) enters due_soon on 1 Apr.
    await _advance_to(hass, freezer, "2027-04-01T00:05:00+02:00")
    assert [e.data["title"] for e in due_soon] == ["Vask vinduer"]
    await _advance_to(hass, freezer, "2027-04-02T00:05:00+02:00")
    assert len(due_soon) == 1


async def test_completion_resets_notified_state_without_firing(
    hass: HomeAssistant, setup_entry: SetupEntry, freezer: Any
) -> None:
    due_soon = async_capture_events(hass, EVENT_TASK_DUE_SOON)
    overdue = async_capture_events(hass, EVENT_TASK_OVERDUE)
    entry = await setup_entry(keys=["smoke_alarm_check"])
    task = _task(entry, "smoke_alarm_check")
    await hass.services.async_call(
        DOMAIN,
        "complete_task",
        {"config_entry_id": entry.entry_id, "task_id": task.id},
        blocking=True,
    )
    assert _task(entry, "smoke_alarm_check").last_notified_state == "ok"
    await _advance_to(hass, freezer, "2026-12-02T00:05:00+01:00")
    assert overdue == [] and due_soon == []
    # The next year's window fires again.
    await _advance_to(hass, freezer, "2027-11-17T00:05:00+01:00")
    assert len(due_soon) == 1


async def test_logbook_describes_completion(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_member_user: MockUser
) -> None:
    entry = await setup_entry(keys=["clean_drains#1"])
    events = async_capture_events(hass, EVENT_TASK_COMPLETED)
    task = _task(entry, "clean_drains#1")
    await hass.services.async_call(
        DOMAIN,
        "complete_task",
        {"config_entry_id": entry.entry_id, "task_id": task.id},
        blocking=True,
        context=Context(user_id=hass_member_user.id),
    )
    await hass.async_block_till_done()

    # The logbook component needs frontend + recorder; exercise our platform directly.
    from custom_components.boligloggen import logbook

    registered: dict[str, Any] = {}
    logbook.async_describe_events(
        hass, lambda domain, event_type, fn: registered.update({event_type: (domain, fn)})
    )
    domain, describe = registered[EVENT_TASK_COMPLETED]
    assert domain == DOMAIN
    event = events[0]
    described = describe(event)
    assert described["name"] == "Kari"
    assert described["message"] == "fullførte «Rens sluk – bad 1»"
    assert described["entity_id"].startswith("sensor.enebolig_rens_sluk")


async def test_calendar_events(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    entry = await setup_entry(keys=["window_washing", "heat_pump_filter"])
    state = hass.states.get("calendar.enebolig_maintenance_plan")
    assert state is not None
    assert state.attributes["message"] == "Rens filter i varmepumpe"  # 22 Feb next
    entity = hass.data["calendar"].get_entity("calendar.enebolig_maintenance_plan")
    start = dt_util.as_utc(datetime(2027, 1, 1, tzinfo=dt_util.get_default_time_zone()))
    events = await entity.async_get_events(hass, start, start + timedelta(days=365))
    summary = [(e.start.isoformat(), e.summary) for e in events]
    assert ("2027-04-15", "Vask vinduer") in summary
    assert ("2027-09-15", "Vask vinduer") in summary
    assert [s for d, s in summary if s.startswith("Rens filter")] == [
        "Rens filter i varmepumpe"
    ] * 4
    assert entry.entry_id


async def test_websocket_commands(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    entry = await setup_entry(keys=["window_washing", "heat_pump_filter", "smoke_alarm_check"])
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "boligloggen/properties"})
    msg = await client.receive_json()
    assert msg["result"] == [
        {"config_entry_id": entry.entry_id, "name": "Enebolig", "type": "house"}
    ]

    await client.send_json_auto_id({"type": "boligloggen/tasks", "config_entry_id": entry.entry_id})
    msg = await client.receive_json()
    tasks = {t["template_id"]: t for t in msg["result"]}
    assert tasks["smoke_alarm_check"]["due_status"] == "due_soon"
    assert tasks["smoke_alarm_check"]["sensor_entity_id"].startswith("sensor.")
    assert tasks["smoke_alarm_check"]["button_entity_id"].startswith("button.")

    # Complete two tasks, then check year plan and log.
    for key in ("smoke_alarm_check", "heat_pump_filter"):
        await hass.services.async_call(
            DOMAIN,
            "complete_task",
            {"config_entry_id": entry.entry_id, "task_id": _task(entry, key).id},
            blocking=True,
        )

    await client.send_json_auto_id(
        {"type": "boligloggen/year_plan", "config_entry_id": entry.entry_id, "year": 2026}
    )
    plan = {p["title"]: p for p in (await client.receive_json())["result"]}
    smoke = plan["Test røykvarslere og bytt batteri"]
    assert smoke["schedule_type"] == "fixed"
    assert smoke["occurrences"] == [{"date": "2026-12-01", "status": "done"}]
    pump = plan["Rens filter i varmepumpe"]
    assert pump["schedule_type"] == "interval"
    assert pump["occurrences"] == [{"date": "2026-11-22", "status": "done"}]

    await client.send_json_auto_id(
        {"type": "boligloggen/year_plan", "config_entry_id": entry.entry_id, "year": 2027}
    )
    plan = {p["title"]: p for p in (await client.receive_json())["result"]}
    assert [o["date"] for o in plan["Rens filter i varmepumpe"]["occurrences"]] == [
        "2027-02-22",
        "2027-05-22",
        "2027-08-22",
        "2027-11-22",
    ]
    assert [o["status"] for o in plan["Vask vinduer"]["occurrences"]] == ["upcoming", "upcoming"]

    await client.send_json_auto_id(
        {"type": "boligloggen/log", "config_entry_id": entry.entry_id, "limit": 1}
    )
    page = (await client.receive_json())["result"]
    assert [e["title"] for e in page["entries"]] == ["Rens filter i varmepumpe"]
    await client.send_json_auto_id(
        {
            "type": "boligloggen/log",
            "config_entry_id": entry.entry_id,
            "limit": 1,
            "before": page["next_before"],
        }
    )
    page = (await client.receive_json())["result"]
    assert [e["title"] for e in page["entries"]] == ["Test røykvarslere og bytt batteri"]
    assert page["next_before"] is None

    await client.send_json_auto_id(
        {"type": "boligloggen/year_plan", "config_entry_id": "missing", "year": 2026}
    )
    msg = await client.receive_json()
    assert msg["success"] is False
    assert msg["error"]["code"] == "not_found"


async def test_diagnostics_redacts_and_includes_feedback(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    from custom_components.boligloggen.diagnostics import async_get_config_entry_diagnostics

    entry = await setup_entry(keys=["smoke_alarm_check"])
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["profile"]["address"] == "**REDACTED**"
    assert "heat_pump_filter" in diag["onboarding_feedback"]["deselected_at_review"]
    assert diag["summary"]["active_tasks"] == 1
