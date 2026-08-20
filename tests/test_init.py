"""Tests for config entry lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lumaforge import async_setup_entry, async_unload_entry
from custom_components.lumaforge.api import LumaForgeData
from custom_components.lumaforge.const import DOMAIN

from .conftest import INFO, OTA_INFO, STATUS


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
        assert entry.runtime_data.client._ws_task is None
        assert await async_unload_entry(hass, entry)
        unload.assert_awaited_once()
        assert entry.runtime_data.client._ws_task is None


async def test_ota_setup_and_unload_closes_websocket(hass: HomeAssistant) -> None:
    """OTA entries load UpdateEntity support and leave no client task."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=OTA_INFO.device_id,
        data={"host": "192.168.2.123", "port": 80},
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.lumaforge.api.LumaForgeApiClient.async_get_data",
            new_callable=AsyncMock,
            return_value=LumaForgeData(OTA_INFO, STATUS),
        ),
        patch(
            "custom_components.lumaforge.api.LumaForgeApiClient.async_start_websocket",
            new_callable=AsyncMock,
        ) as start_ws,
        patch(
            "custom_components.lumaforge.api.LumaForgeApiClient.async_close",
            new_callable=AsyncMock,
        ) as close,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ) as forward,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        assert await async_setup_entry(hass, entry)
        assert Platform.UPDATE in forward.await_args.args[1]
        start_ws.assert_awaited_once()
        assert await async_unload_entry(hass, entry)
        close.assert_awaited_once()
