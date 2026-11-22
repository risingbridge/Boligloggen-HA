"""Onboarding config flow paths per property type."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.boligloggen.const import DOMAIN

BASIC = {"name": "Hjemme", "address": "Gata 1", "type": "house", "build_year": 1985}
BUILDING = {
    "heating": ["wood_stove", "heat_pump"],
    "ventilation": "natural",
    "cladding": "wood",
    "bathroom_count": "2",
}
OUTDOOR = {
    "garden": "yes",
    "driveway": "pavers",
    "deck": "wood",
    "garage": "garage_with_door",
    "water": "public",
}


async def _start(hass: HomeAssistant) -> dict[str, Any]:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def _configure(hass: HomeAssistant, result: dict[str, Any], data: dict[str, Any]) -> Any:
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


def _option_values(result: dict[str, Any], field: str) -> list[str]:
    schema = result["data_schema"].schema
    key = next(k for k in schema if str(k) == field)
    return [o["value"] for o in schema[key].config["options"]]


async def test_house_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await _start(hass)
    result = await _configure(hass, result, BASIC)
    assert result["step_id"] == "building"
    result = await _configure(hass, result, BUILDING)
    assert result["step_id"] == "outdoor"
    result = await _configure(hass, result, OUTDOOR)
    assert result["step_id"] == "review"
    keys = _option_values(result, "tasks")
    assert "clean_drains#2" in keys and "chimney_stove_inspection" in keys
    assert result["description_placeholders"]["count"] == str(len(keys))

    deselect = {"heat_pump_filter", "clean_drains#2"}
    selected = [k for k in keys if k not in deselect]
    result = await _configure(hass, result, {"tasks": selected})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hjemme"
    data = result["data"]
    assert data["profile"]["attributes"]["bathroom_count"] == 2
    assert data["profile"]["attributes"]["garden"] is True
    assert set(data["selected_template_ids"]) == set(selected)
    assert set(data["deselected_template_ids"]) == deselect
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert len(entry.runtime_data.active_tasks) == len(selected)
    assert set(entry.runtime_data.feedback["deselected_at_review"]) == deselect


async def test_apartment_skips_outdoor_and_cladding(hass: HomeAssistant) -> None:
    result = await _start(hass)
    result = await _configure(hass, result, {**BASIC, "type": "apartment", "build_year": 2022})
    assert result["step_id"] == "building"
    fields = {str(k) for k in result["data_schema"].schema}
    assert fields == {"heating", "ventilation", "bathroom_count"}
    result = await _configure(
        hass, result, {"heating": ["electric"], "ventilation": "unknown", "bathroom_count": "1"}
    )
    assert result["step_id"] == "review"
    keys = _option_values(result, "tasks")
    assert "ventilation_filter_change" in keys  # unknown + new → balanced
    assert "clean_gutters" not in keys
    result = await _configure(hass, result, {"tasks": keys})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["profile"]["attributes"]["cladding"] is None


async def test_cabin_flow_includes_cabin_step(hass: HomeAssistant) -> None:
    result = await _start(hass)
    result = await _configure(
        hass, result, {"name": "Hytta", "type": "cabin", "age_band": "30to50"}
    )
    result = await _configure(hass, result, {**BUILDING, "bathroom_count": "1"})
    assert result["step_id"] == "outdoor"
    result = await _configure(
        hass, result, {**OUTDOOR, "garden": "no", "driveway": "gravel", "water": "own_well"}
    )
    assert result["step_id"] == "cabin"
    result = await _configure(hass, result, {"cabin_winter_use": "closed", "cabin_water": "summer"})
    assert result["step_id"] == "review"
    keys = _option_values(result, "tasks")
    assert {"cabin_drain_water", "well_water_sample", "gravel_top_up"} <= set(keys)
    result = await _configure(hass, result, {"tasks": keys})
    profile = result["data"]["profile"]
    assert profile["build_year"] is None and profile["age_band"] == "30to50"
    assert profile["attributes"]["cabin_winter_use"] == "closed"


async def test_townhouse_shows_outdoor_without_cabin(hass: HomeAssistant) -> None:
    result = await _start(hass)
    result = await _configure(hass, result, {**BASIC, "type": "townhouse"})
    result = await _configure(hass, result, BUILDING)
    assert result["step_id"] == "outdoor"
    result = await _configure(
        hass,
        result,
        {"garden": "no", "driveway": "none", "deck": "none", "garage": "none", "water": "public"},
    )
    assert result["step_id"] == "review"
    assert "leaf_raking" not in _option_values(result, "tasks")


async def test_age_required(hass: HomeAssistant) -> None:
    result = await _start(hass)
    result = await _configure(hass, result, {"name": "X", "type": "house"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "age_required"}


async def test_build_year_wins_over_age_band(hass: HomeAssistant) -> None:
    result = await _start(hass)
    result = await _configure(
        hass, result, {"name": "X", "type": "apartment", "build_year": 2000, "age_band": "gt50"}
    )
    result = await _configure(
        hass, result, {"heating": [], "ventilation": "balanced", "bathroom_count": "1"}
    )
    result = await _configure(hass, result, {"tasks": []})
    assert result["data"]["profile"]["age_band"] is None
    assert result["data"]["selected_template_ids"] == []
