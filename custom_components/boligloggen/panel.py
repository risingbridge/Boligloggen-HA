"""Admin-only sidebar panel for editing the maintenance plan.

The panel is a single dependency-free JavaScript module in ``frontend/``. It reads
through the websocket API and writes only through the integration's services, so
it gets exactly the same validation and admin checks as automations and scripts.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_URL_PATH = DOMAIN
PANEL_COMPONENT = "boligloggen-panel"
PANEL_ICON = "mdi:hammer-wrench"
PANEL_TITLE = "Boligloggen"
STATIC_URL = f"/{DOMAIN}_static"
FRONTEND_DIR = Path(__file__).parent / "frontend"
PANEL_FILE = "boligloggen-panel.js"


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


async def async_setup_panel(hass: HomeAssistant) -> bool:
    """Serve the panel module and register the sidebar entry (admins only).

    Skipped when the frontend isn't loaded (e.g. headless test setups). Returns
    whether the panel was registered.
    """
    if "frontend" not in hass.config.components or hass.http is None:
        _LOGGER.debug("Frontend not loaded; not registering the Boligloggen panel")
        return False

    # Imported lazily: panel_custom depends on frontend.
    from homeassistant.components import panel_custom

    # Content hash in the URL: browsers and the companion app pick up a new
    # panel version after an update without a manual cache clear.
    version = await hass.async_add_executor_job(_file_hash, FRONTEND_DIR / PANEL_FILE)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=True)]
    )
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/{PANEL_FILE}?v={version}",
        require_admin=True,
        config={"domain": DOMAIN},
    )
    return True
