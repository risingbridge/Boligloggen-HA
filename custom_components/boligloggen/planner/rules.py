"""Inclusion rule matching.

All keys present in a rule must match (AND). Within a list any value
matches (ANY). An empty rule always matches.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from . import models as m
from .models import PropertyProfile

Matcher = Callable[[PropertyProfile, Any, date], bool]


def _in(attr: Callable[[PropertyProfile, date], Any]) -> Matcher:
    return lambda p, value, today: attr(p, today) in value


MATCHERS: dict[str, Matcher] = {
    "types_any": _in(lambda p, _: p.type),
    "types_exclude": lambda p, value, _: p.type not in value,
    "heating_any": lambda p, value, _: bool(set(p.attributes.heating) & set(value)),
    "ventilation_any": _in(lambda p, today: p.effective_ventilation(today)),
    "cladding_any": _in(lambda p, _: p.attributes.cladding),
    "driveway_any": _in(lambda p, _: p.attributes.driveway),
    "deck_any": _in(lambda p, _: p.attributes.deck),
    "garage_any": _in(lambda p, _: p.attributes.garage),
    "requires_garden": lambda p, value, _: p.attributes.garden == value,
    "requires_own_well": lambda p, value, _: (p.attributes.water == "own_well") == value,
    "cabin_winter_use_any": _in(lambda p, _: p.attributes.cabin_winter_use),
    "cabin_water_any": _in(lambda p, _: p.attributes.cabin_water),
    "min_age_years": lambda p, value, today: p.age_years(today) >= value,
    "max_age_years": lambda p, value, today: p.age_years(today) <= value,
}

#: Allowed values for list-valued keys (used by catalog validation).
LIST_KEY_ENUMS: dict[str, tuple[Any, ...]] = {
    "types_any": m.PROPERTY_TYPES,
    "types_exclude": m.PROPERTY_TYPES,
    "heating_any": m.HEATING,
    "ventilation_any": tuple(v for v in m.VENTILATION if v != "unknown"),
    "cladding_any": m.CLADDING,
    "driveway_any": m.DRIVEWAY,
    "deck_any": m.DECK,
    "garage_any": m.GARAGE,
    "cabin_winter_use_any": m.CABIN_WINTER_USE,
    "cabin_water_any": m.CABIN_WATER,
}
BOOL_KEYS: frozenset[str] = frozenset({"requires_garden", "requires_own_well"})
INT_KEYS: frozenset[str] = frozenset({"min_age_years", "max_age_years"})


def matches(rule: dict[str, Any], profile: PropertyProfile, today: date) -> bool:
    for key, value in rule.items():
        matcher = MATCHERS.get(key)
        if matcher is None:
            raise KeyError(f"Unknown inclusion rule key: {key}")
        if not matcher(profile, value, today):
            return False
    return True
