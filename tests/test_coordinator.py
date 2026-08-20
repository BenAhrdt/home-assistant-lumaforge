"""Tests for the LumaForge coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.lumaforge.api import (
    LumaForgeConnectionError,
    LumaForgeData,
)
from custom_components.lumaforge.coordinator import LumaForgeCoordinator

from .conftest import INFO, STATUS


async def test_coordinator_update(hass: HomeAssistant) -> None:
    """Coordinator returns combined API data."""
    client = MagicMock()
    client.async_get_data = AsyncMock(return_value=LumaForgeData(INFO, STATUS))
    coordinator = LumaForgeCoordinator(hass, client)
    data = await coordinator._async_update_data()
    assert data.info.device_id == "lf-51bf60200d1e"
    assert data.status.cpu_percent == 4.2


async def test_coordinator_unavailable(hass: HomeAssistant) -> None:
    """Communication errors become update failures."""
    client = MagicMock()
    client.async_get_data = AsyncMock(side_effect=LumaForgeConnectionError)
    coordinator = LumaForgeCoordinator(hass, client)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
