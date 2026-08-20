"""Fixtures for LumaForge tests."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.lumaforge.api import LumaForgeInfo, LumaForgeStatus

pytest_plugins = "pytest_homeassistant_custom_component"

INFO = LumaForgeInfo(
    device_id="lf-51bf60200d1e",
    device_name="Garage",
    model="esp32",
    firmware_version="0.2.0-alpha.1",
    api_version=1,
    hostname="lumaforge-51bf60",
    connected=True,
    ip_address="192.168.2.123",
    rssi=-55,
    capabilities=("led_output", "scenes", "zones"),
)
SEQUENCE_INFO = replace(
    INFO,
    capabilities=(*INFO.capabilities, "automations", "automation_sequences"),
)
STATUS = LumaForgeStatus(
    connected=True,
    ip_address="192.168.2.123",
    rssi=-55,
    cpu_percent=4.2,
    memory_used_bytes=120000,
    memory_total_bytes=327680,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in every test."""
    yield


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Mock the API client."""
    with patch(
        "custom_components.lumaforge.config_flow.LumaForgeApiClient.async_get_info",
        new_callable=AsyncMock,
        return_value=INFO,
    ) as mock:
        yield mock
