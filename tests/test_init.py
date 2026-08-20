"""Tests for config entry lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lumaforge import async_setup_entry, async_unload_entry
from custom_components.lumaforge.api import LumaForgeData
from custom_components.lumaforge.const import DOMAIN

from .conftest import INFO, STATUS


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """Set up runtime data and fully unload platforms."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=INFO.device_id,
        data={"host": "192.168.2.123", "port": 80},
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.lumaforge.api.LumaForgeApiClient.async_get_data",
            new_callable=AsyncMock,
            return_value=LumaForgeData(INFO, STATUS),
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ) as forward,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new_callable=AsyncMock,
            return_value=True,
        ) as unload,
    ):
        assert await async_setup_entry(hass, entry)
        forward.assert_awaited_once()
        assert entry.runtime_data.data.info.device_id == INFO.device_id
        assert await async_unload_entry(hass, entry)
        unload.assert_awaited_once()
