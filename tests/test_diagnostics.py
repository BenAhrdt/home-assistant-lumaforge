"""Tests for LumaForge diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.lumaforge.api import LumaForgeData
from custom_components.lumaforge.diagnostics import async_get_config_entry_diagnostics

from .conftest import INFO, STATUS


async def test_diagnostics_redaction(hass: HomeAssistant) -> None:
    """Private network identifiers are redacted."""
    entry = MagicMock()
    entry.data = {"host": "192.168.2.123", "port": 80}
    entry.runtime_data.data = LumaForgeData(INFO, STATUS)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["config_entry"]["host"] == "**REDACTED**"
    assert result["data"]["info"]["hostname"] == "**REDACTED**"
    assert result["data"]["status"]["ip_address"] == "**REDACTED**"
