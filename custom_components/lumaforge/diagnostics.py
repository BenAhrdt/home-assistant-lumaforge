"""Diagnostics support for LumaForge."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import LumaForgeConfigEntry

TO_REDACT = {"host", "hostname", "ip_address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LumaForgeConfigEntry
) -> dict[str, Any]:
    """Return redacted config entry and last coordinator data."""
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "data": async_redact_data(asdict(entry.runtime_data.data), TO_REDACT),
    }
