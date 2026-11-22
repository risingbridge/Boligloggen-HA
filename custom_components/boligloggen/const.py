"""Constants for the Boligloggen integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "boligloggen"
MANUFACTURER: Final = "Boligloggen"

STORAGE_VERSION: Final = 1
STORAGE_MINOR_VERSION: Final = 1
SCHEMA_VERSION: Final = 1

PLATFORMS: Final = ["sensor", "button", "calendar"]

# Config entry data keys
CONF_PROFILE: Final = "profile"
CONF_SELECTED: Final = "selected_template_ids"
CONF_DESELECTED: Final = "deselected_template_ids"
CONF_LANGUAGE: Final = "language"

# Events
EVENT_TASK_COMPLETED: Final = "boligloggen_task_completed"
EVENT_TASK_DUE_SOON: Final = "boligloggen_task_due_soon"
EVENT_TASK_OVERDUE: Final = "boligloggen_task_overdue"

# Daily scan time (local)
SCAN_HOUR: Final = 0
SCAN_MINUTE: Final = 5

SYSTEM_USER_NAME: Final = "System"

# Entity kinds used in unique ids: f"{entry_id}_{task_id}_{kind}"
KIND_SENSOR: Final = "sensor"
KIND_BUTTON: Final = "button"
AGGREGATE_KINDS: Final = ("next_task", "overdue", "due_soon", "last_completed")

CATEGORY_ICONS: Final = {
    "safety": "mdi:shield-check",
    "indoor": "mdi:sofa",
    "wet_room": "mdi:shower",
    "heating": "mdi:fire",
    "ventilation": "mdi:fan",
    "exterior": "mdi:home-roof",
    "outdoor": "mdi:pine-tree",
    "cabin": "mdi:home-variant",
    "seasonal": "mdi:calendar-sync",
}

CATEGORY_LABELS: Final = {
    "nb": {
        "safety": "Sikkerhet",
        "indoor": "Innendørs",
        "wet_room": "Våtrom",
        "heating": "Oppvarming",
        "ventilation": "Ventilasjon",
        "exterior": "Utvendig",
        "outdoor": "Uteområde",
        "cabin": "Hytte",
        "seasonal": "Sesong",
    },
    "en": {
        "safety": "Safety",
        "indoor": "Indoor",
        "wet_room": "Wet room",
        "heating": "Heating",
        "ventilation": "Ventilation",
        "exterior": "Exterior",
        "outdoor": "Outdoor",
        "cabin": "Cabin",
        "seasonal": "Seasonal",
    },
}

DONE_LABEL: Final = {"nb": "utført", "en": "done"}
