"""Persistent storage for one property (config entry)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, SCHEMA_VERSION, STORAGE_MINOR_VERSION, STORAGE_VERSION


def empty_feedback() -> dict[str, list[str]]:
    return {"deselected_at_review": [], "added_later": [], "removed_later": []}


class BoligloggenStore(Store[dict[str, Any]]):
    """``Store`` with a migration hook.

    Layout (``schema_version`` 1)::

        {schema_version, catalog_version, language, profile, tasks[], log[],
         onboarding_feedback{deselected_at_review, added_later, removed_later}}
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        super().__init__(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}",
            minor_version=STORAGE_MINOR_VERSION,
            atomic_writes=True,
        )

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate older layouts. Add steps here when the schema changes."""
        data = dict(old_data)
        # Defensive normalisation (minor version bumps add optional keys).
        data.setdefault("schema_version", SCHEMA_VERSION)
        data.setdefault("tasks", [])
        data.setdefault("log", [])
        feedback = data.setdefault("onboarding_feedback", empty_feedback())
        for key, value in empty_feedback().items():
            feedback.setdefault(key, value)
        if old_major_version > STORAGE_VERSION:
            raise NotImplementedError("Cannot downgrade Boligloggen storage")
        return data
