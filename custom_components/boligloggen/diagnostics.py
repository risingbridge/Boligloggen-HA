"""Diagnostics download: profile, plan summary and onboarding feedback.

Lets test households share how well the generated plan fitted (brief §14.4).
Addresses and user names are redacted.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BoligloggenConfigEntry

TO_REDACT = {"address", "name", "user_name", "user_id", "note", "title", "description"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BoligloggenConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    tasks = list(coordinator.tasks.values())
    return {
        "catalog_version": coordinator.catalog_version,
        "language": coordinator.language,
        "profile": async_redact_data(coordinator.profile.to_dict(), TO_REDACT),
        "onboarding_feedback": coordinator.feedback,
        "summary": {
            "active_tasks": len(coordinator.active_tasks),
            "archived_tasks": len(coordinator.archived_tasks),
            "custom_tasks": sum(1 for t in tasks if t.template_id is None),
            "log_entries": len(coordinator.log),
            "by_category": dict(Counter(t.category for t in coordinator.active_tasks)),
        },
        "active_template_keys": sorted(t.key for t in coordinator.active_tasks if t.key),
        "archived_template_keys": sorted(t.key for t in coordinator.archived_tasks if t.key),
    }
