"""Inclusion rule tests (brief §7)."""

from __future__ import annotations

from datetime import date

import pytest
from planner import matches
from planner.models import PropertyProfile

from .helpers import profile

TODAY = date(2026, 11, 22)


def test_empty_rule_always_matches() -> None:
    assert matches({}, profile("apartment"), TODAY)


@pytest.mark.parametrize(
    ("rule", "prof", "expected"),
    [
        ({"types_any": ["cabin"]}, profile("cabin"), True),
        ({"types_any": ["cabin"]}, profile("house"), False),
        ({"types_any": ["house", "townhouse"]}, profile("townhouse"), True),
        ({"types_exclude": ["apartment"]}, profile("apartment"), False),
        ({"types_exclude": ["apartment"]}, profile("house"), True),
        ({"heating_any": ["wood_stove"]}, profile(heating=["heat_pump", "wood_stove"]), True),
        ({"heating_any": ["wood_stove"]}, profile(heating=["electric"]), False),
        ({"heating_any": ["wood_stove"]}, profile(heating=[]), False),
        ({"ventilation_any": ["balanced"]}, profile(ventilation="balanced"), True),
        ({"ventilation_any": ["balanced"]}, profile(ventilation="natural"), False),
        ({"cladding_any": ["wood", "mixed"]}, profile(cladding="mixed"), True),
        ({"cladding_any": ["wood"]}, profile(cladding=None), False),
        ({"driveway_any": ["pavers"]}, profile(driveway="pavers"), True),
        ({"driveway_any": ["pavers"]}, profile(driveway="none"), False),
        ({"deck_any": ["wood"]}, profile(deck="wood"), True),
        ({"deck_any": ["wood"]}, profile(deck="composite_or_stone"), False),
        ({"garage_any": ["garage_with_door"]}, profile(garage="carport"), False),
        ({"garage_any": ["garage_with_door", "carport"]}, profile(garage="carport"), True),
        ({"requires_garden": True}, profile(garden=True), True),
        ({"requires_garden": True}, profile(garden=False), False),
        ({"requires_garden": False}, profile(garden=False), True),
        ({"requires_own_well": True}, profile(water="own_well"), True),
        ({"requires_own_well": True}, profile(water="public"), False),
        ({"requires_own_well": False}, profile(water="public"), True),
        ({"cabin_winter_use_any": ["closed"]}, profile("cabin", cabin_winter_use="closed"), True),
        ({"cabin_winter_use_any": ["closed"]}, profile("house"), False),
        ({"cabin_water_any": ["summer"]}, profile("cabin", cabin_water="summer"), True),
        ({"cabin_water_any": ["summer"]}, profile("cabin", cabin_water="none"), False),
        ({"min_age_years": 30}, profile(build_year=1996), True),  # exactly 30
        ({"min_age_years": 30}, profile(build_year=1997), False),
        ({"max_age_years": 10}, profile(build_year=2016), True),
        ({"max_age_years": 10}, profile(build_year=2015), False),
    ],
)
def test_each_key(rule: dict[str, object], prof: PropertyProfile, expected: bool) -> None:
    assert matches(rule, prof, TODAY) is expected


def test_and_semantics_across_keys() -> None:
    rule = {"cladding_any": ["wood"], "types_exclude": ["apartment"]}
    assert matches(rule, profile("house", cladding="wood"), TODAY)
    assert not matches(rule, profile("apartment", cladding="wood"), TODAY)
    assert not matches(rule, profile("house", cladding="brick"), TODAY)


def test_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        matches({"nope": 1}, profile(), TODAY)


@pytest.mark.parametrize(
    ("build_year", "expected"),
    [(TODAY.year - 5, "balanced"), (TODAY.year - 14, "balanced"), (TODAY.year - 15, "exhaust")],
)
def test_unknown_ventilation_defaults_by_age(build_year: int, expected: str) -> None:
    prof = profile(build_year=build_year, ventilation="unknown")
    assert prof.effective_ventilation(TODAY) == expected
    assert matches({"ventilation_any": [expected]}, prof, TODAY)


@pytest.mark.parametrize(
    ("band", "age"), [("lt10", 0), ("10to30", 10), ("30to50", 30), ("gt50", 50)]
)
def test_age_band_uses_lower_bound(band: str, age: int) -> None:
    prof = profile(build_year=None, age_band=band)
    assert prof.age_years(TODAY) == age
    assert matches({"min_age_years": age}, prof, TODAY)
    assert not matches({"min_age_years": age + 1}, prof, TODAY)


def test_build_year_wins_over_age_band() -> None:
    prof = profile(build_year=2020, age_band="gt50")
    assert prof.age_years(TODAY) == 6


def test_age_band_drives_unknown_ventilation() -> None:
    assert profile(build_year=None, age_band="lt10").effective_ventilation(TODAY) == "balanced"
    assert profile(build_year=None, age_band="10to30").effective_ventilation(TODAY) == "balanced"
    assert profile(build_year=None, age_band="30to50").effective_ventilation(TODAY) == "exhaust"
