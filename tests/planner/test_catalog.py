"""Catalog loading and validation."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from planner import CatalogError, load_catalog, parse_catalog
from planner.catalog import DEFAULT_CATALOG_PATH
from planner.models import CATEGORIES

VALID: dict[str, Any] = {
    "version": 1,
    "templates": [
        {
            "id": "a_task",
            "category": "safety",
            "title": {"nb": "A", "en": "A"},
            "schedule": {"type": "fixed", "dates": [{"month": 2, "day": 29}]},
        }
    ],
}


def _with(**template_changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(VALID)
    data["templates"][0].update(template_changes)
    return data


def test_bundled_catalog_is_valid() -> None:
    catalog = load_catalog()
    assert 30 <= len(catalog) <= 50
    assert catalog.version == 1
    assert {t.category for t in catalog} <= set(CATEGORIES)
    for template in catalog:
        assert template.title["nb"] and template.title["en"]
        assert template.description.get("nb") and template.description.get("en")


def test_bundled_catalog_covers_required_mappings() -> None:
    ids = {t.id for t in load_catalog()}
    required = {
        "smoke_alarm_check",
        "fire_extinguisher_check",
        "clean_drains",
        "wet_room_sealant_check",
        "kitchen_hood_filter",
        "water_leak_check",
        "chimney_stove_inspection",
        "heat_pump_filter",
        "heat_pump_outdoor_rinse",
        "heat_pump_condensate_drain",
        "bleed_radiators",
        "hydronic_pressure_check",
        "ventilation_filter_change",
        "exhaust_fan_clean",
        "natural_vents_check",
        "paint_wood_cladding",
        "wood_cladding_inspection",
        "render_check",
        "clean_gutters",
        "roof_inspection",
        "drainage_check",
        "windows_doors_check",
        "electrical_inspection",
        "water_heater_assessment",
        "leaf_raking",
        "asphalt_seal_cracks",
        "pavers_weeds_sand",
        "gravel_top_up",
        "concrete_crack_check",
        "wood_deck_oil",
        "composite_deck_clean",
        "garage_door_service",
        "well_water_sample",
        "well_pump_check",
        "cabin_drain_water",
        "cabin_fill_water",
        "cabin_season_close",
        "cabin_season_open",
    }
    assert required <= ids


def test_bundled_catalog_is_plain_json_with_schema_reference() -> None:
    raw = json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
    assert raw["$schema"] == "./catalog.schema.json"
    assert (DEFAULT_CATALOG_PATH.parent / "catalog.schema.json").exists()


def test_minimal_valid_catalog_parses() -> None:
    catalog = parse_catalog(VALID)
    template = catalog.get("a_task")
    assert template is not None
    assert template.include == {}
    assert template.per_bathroom is False


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"bogus": 1}, "unknown key 'bogus'"),
        ({"category": "kitchen"}, "invalid category"),
        ({"id": "Bad-Id"}, "lower_snake_case"),
        ({"title": {"nb": "Bare norsk"}}, "missing 'en'"),
        ({"title": {"nb": "x", "en": "x", "de": "x"}}, "unknown language 'de'"),
        ({"schedule": {"type": "fixed", "dates": [{"month": 2, "day": 30}]}}, "invalid day 30"),
        ({"schedule": {"type": "fixed", "dates": [{"month": 4, "day": 31}]}}, "invalid day 31"),
        ({"schedule": {"type": "fixed", "dates": [{"month": 13}]}}, "invalid month 13"),
        ({"schedule": {"type": "fixed", "dates": []}}, "non-empty list"),
        ({"schedule": {"type": "interval", "every": 0, "unit": "years"}}, "positive integer"),
        ({"schedule": {"type": "interval", "every": 1, "unit": "weeks"}}, "unit must be"),
        ({"schedule": {"type": "weekly"}}, "schedule.type must be"),
        ({"due_soon_days": -1}, "due_soon_days"),
        ({"per_bathroom": "yes"}, "per_bathroom must be a boolean"),
        ({"include": {"heating_any": ["coal"]}}, "invalid values ['coal']"),
        ({"include": {"types_any": []}}, "non-empty list"),
        ({"include": {"ventilation_any": ["unknown"]}}, "invalid values ['unknown']"),
        ({"include": {"requires_garden": "yes"}}, "must be a boolean"),
        ({"include": {"min_age_years": "20"}}, "non-negative integer"),
        ({"include": {"has_pool": True}}, "unknown key 'has_pool'"),
    ],
)
def test_invalid_templates_are_rejected(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(CatalogError) as err:
        parse_catalog(_with(**changes))
    assert message in str(err.value)


def test_duplicate_ids_are_rejected() -> None:
    data = copy.deepcopy(VALID)
    data["templates"].append(copy.deepcopy(data["templates"][0]))
    with pytest.raises(CatalogError, match="duplicate id"):
        parse_catalog(data)


def test_missing_required_key() -> None:
    data = copy.deepcopy(VALID)
    del data["templates"][0]["schedule"]
    with pytest.raises(CatalogError, match="missing 'schedule'"):
        parse_catalog(data)


def test_root_validation() -> None:
    with pytest.raises(CatalogError):
        parse_catalog([])
    with pytest.raises(CatalogError):
        parse_catalog({"version": 1, "templates": []})
    with pytest.raises(CatalogError, match="version"):
        parse_catalog({**VALID, "version": 0})
