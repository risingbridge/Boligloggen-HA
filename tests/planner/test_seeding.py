"""Plan seeding, per-bathroom expansion, plan diff and example-profile snapshots."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from planner import (
    PropertyProfile,
    Schedule,
    custom_task,
    load_catalog,
    normalize_language,
    plan_diff,
    seed_tasks,
    suggest,
)

from .helpers import profile

TODAY = date(2026, 11, 22)
NOW = "2026-11-22T12:00:00+00:00"
SNAPSHOTS = Path(__file__).parent / "snapshots"
CATALOG = load_catalog()

EXAMPLE_PROFILES: dict[str, dict[str, Any]] = {
    # House from 1985 with wood stove + heat pump (the brief's §5 example).
    "house_1985": {
        "name": "Enebolig Trondheim",
        "address": "Eksempelveien 1, 7000 Trondheim",
        "type": "house",
        "build_year": 1985,
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
        },
    },
    # New apartment: ~6 questions, few tasks.
    "apartment_new": {
        "name": "Leilighet Oslo",
        "type": "apartment",
        "build_year": 2022,
        "attributes": {
            "heating": ["electric"],
            "ventilation": "unknown",
            "bathroom_count": 1,
        },
    },
    # Winter-closed cabin with its own well.
    "cabin_winter_closed": {
        "name": "Hytta",
        "type": "cabin",
        "build_year": None,
        "age_band": "30to50",
        "attributes": {
            "heating": ["wood_stove", "electric"],
            "ventilation": "natural",
            "cladding": "wood",
            "bathroom_count": 1,
            "garden": False,
            "driveway": "gravel",
            "deck": "wood",
            "garage": "none",
            "water": "own_well",
            "cabin_winter_use": "closed",
            "cabin_water": "summer",
        },
    },
}


def _plan_snapshot(name: str) -> dict[str, Any]:
    prof = PropertyProfile.from_dict(EXAMPLE_PROFILES[name])
    suggestions = suggest(CATALOG, prof, TODAY)
    tasks = seed_tasks(suggestions, lang="nb", setup_date=TODAY, now_iso=NOW)
    return {
        "profile": name,
        "today": TODAY.isoformat(),
        "tasks": [
            {
                "key": t.key,
                "title": t.title,
                "category": t.category,
                "schedule": t.schedule.to_dict(),
                "due_soon_days": t.due_soon_days,
                "next_due": t.next_due.isoformat(),
            }
            for t in tasks
        ],
    }


@pytest.mark.parametrize("name", sorted(EXAMPLE_PROFILES))
def test_example_profile_snapshots(name: str) -> None:
    """Snapshots are reviewed by hand. Regenerate with ``UPDATE_SNAPSHOTS=1 pytest``."""
    actual = _plan_snapshot(name)
    path = SNAPSHOTS / f"{name}.json"
    if os.environ.get("UPDATE_SNAPSHOTS") or not path.exists():
        path.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == actual


def _keys(name: str) -> set[str]:
    prof = PropertyProfile.from_dict(EXAMPLE_PROFILES[name])
    return {s.key for s in suggest(CATALOG, prof, TODAY)}


def test_house_1985_expected_template_set() -> None:
    keys = _keys("house_1985")
    assert {
        "chimney_stove_inspection",
        "heat_pump_filter",
        "natural_vents_check",
        "paint_wood_cladding",
        "pavers_weeds_sand",
        "wood_deck_oil",
        "garage_door_service",
        "electrical_inspection",
        "drainage_check",
        "leaf_raking",
        "clean_drains#1",
        "clean_drains#2",
    } <= keys
    assert not keys & {
        "ventilation_filter_change",
        "well_water_sample",
        "cabin_season_close",
        "bleed_radiators",
        "asphalt_seal_cracks",
        "clean_drains",
    }


def test_apartment_new_expected_template_set() -> None:
    keys = _keys("apartment_new")
    # New building + unknown ventilation → balanced.
    assert "ventilation_filter_change" in keys
    assert not keys & {
        "clean_gutters",
        "roof_inspection",
        "paint_wood_cladding",
        "electrical_inspection",
        "drainage_check",
        "outdoor_tap_winterize",
    }
    assert len(keys) <= 15


def test_cabin_expected_template_set() -> None:
    keys = _keys("cabin_winter_closed")
    assert {
        "cabin_drain_water",
        "cabin_fill_water",
        "cabin_season_close",
        "cabin_season_open",
        "well_water_sample",
        "well_pump_check",
        "gravel_top_up",
        "chimney_stove_inspection",
        "drainage_check",
        "electrical_inspection",
    } <= keys
    assert "leaf_raking" not in keys


def test_cabin_without_water_skips_water_tasks() -> None:
    prof = profile("cabin", cabin_winter_use="closed", cabin_water="none")
    keys = {s.key for s in suggest(CATALOG, prof, TODAY)}
    assert "cabin_season_close" in keys
    assert "cabin_drain_water" not in keys


def test_cabin_only_tasks_never_for_houses() -> None:
    prof = profile("house", cabin_winter_use="closed", cabin_water="summer")
    assert not any(s.template.category == "cabin" for s in suggest(CATALOG, prof, TODAY))


def test_per_bathroom_expansion() -> None:
    prof = profile("house", bathroom_count=3)
    drains = [s for s in suggest(CATALOG, prof, TODAY) if s.template.id == "clean_drains"]
    assert [s.key for s in drains] == ["clean_drains#1", "clean_drains#2", "clean_drains#3"]
    assert drains[1].title("nb") == "Rens sluk – bad 2"
    assert drains[1].title("en") == "Clean floor drain – bathroom 2"


def test_seeded_task_fields() -> None:
    prof = PropertyProfile.from_dict(EXAMPLE_PROFILES["house_1985"])
    tasks = {
        t.key: t
        for t in seed_tasks(suggest(CATALOG, prof, TODAY), lang="en", setup_date=TODAY, now_iso=NOW)
    }
    smoke = tasks["smoke_alarm_check"]
    assert smoke.next_due == date(2026, 12, 1)
    assert smoke.due_soon_days == 14  # template override
    assert smoke.title == "Test smoke alarms and replace battery"
    paint = tasks["paint_wood_cladding"]
    assert paint.next_due == date(2033, 11, 22)
    assert paint.due_soon_days == 90
    assert tasks["heat_pump_filter"].due_soon_days == 7  # default for 3 months
    assert len({t.id for t in tasks.values()}) == len(tasks)


def test_custom_task_defaults() -> None:
    task = custom_task(
        title="Sjekk båten",
        category="outdoor",
        schedule=Schedule.interval(6, "months"),
        setup_date=TODAY,
        now_iso=NOW,
    )
    assert task.template_id is None and task.key is None
    assert task.due_soon_days == 14
    assert task.next_due == date(2027, 5, 22)


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("nb", "nb"),
        ("no", "nb"),
        ("nn", "nb"),
        ("en", "en"),
        ("en-GB", "en"),
        ("de", "nb"),
        (None, "nb"),
    ],
)
def test_normalize_language(lang: str | None, expected: str) -> None:
    assert normalize_language(lang) == expected


# --- plan diff ------------------------------------------------------------------


def test_plan_diff_after_profile_edit() -> None:
    old = profile("house", heating=["wood_stove"], bathroom_count=1, driveway="gravel")
    tasks = seed_tasks(suggest(CATALOG, old, TODAY), lang="nb", setup_date=TODAY, now_iso=NOW)
    custom = custom_task(
        title="Egendefinert",
        category="indoor",
        schedule=Schedule.interval(1, "years"),
        setup_date=TODAY,
        now_iso=NOW,
    )
    tasks.append(custom)

    new = profile("house", heating=["heat_pump"], bathroom_count=2, driveway="gravel")
    diff = plan_diff(CATALOG, new, tasks, TODAY)
    added = {s.key for s in diff.additions}
    removed = {t.key for t in diff.removals}
    assert {"heat_pump_filter", "clean_drains#2", "wet_room_sealant_check#2"} <= added
    assert removed == {"chimney_stove_inspection", "stove_gasket_check"}
    assert custom not in diff.removals


def test_plan_diff_never_brings_back_archived_templates() -> None:
    prof = profile("house", heating=["heat_pump"])
    tasks = seed_tasks(suggest(CATALOG, prof, TODAY), lang="nb", setup_date=TODAY, now_iso=NOW)
    tasks = [t.evolve(status="archived") if t.key == "heat_pump_filter" else t for t in tasks]
    diff = plan_diff(CATALOG, prof, tasks, TODAY)
    assert diff.additions == ()
    assert diff.removals == ()


def test_plan_diff_ignores_archived_tasks_for_removal() -> None:
    prof = profile("house", heating=["heat_pump"])
    tasks = seed_tasks(suggest(CATALOG, prof, TODAY), lang="nb", setup_date=TODAY, now_iso=NOW)
    tasks = [t.evolve(status="archived") if t.key == "heat_pump_filter" else t for t in tasks]
    diff = plan_diff(CATALOG, profile("house", heating=["electric"]), tasks, TODAY)
    assert "heat_pump_filter" not in {t.key for t in diff.removals}
