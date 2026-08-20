"""Tests for the LumaForge config flow."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lumaforge.const import CONF_PORT, DOMAIN


def discovery(properties: dict) -> ZeroconfServiceInfo:
    """Build discovery information."""
    return ZeroconfServiceInfo(
        ip_address=ip_address("192.168.2.123"),
        ip_addresses=[ip_address("192.168.2.123")],
        port=80,
        hostname="lumaforge.local.",
        type="_lumaforge._tcp.local.",
        name="Garage._lumaforge._tcp.local.",
        properties=properties,
    )


@pytest.mark.parametrize(
    "properties", [{"id": "lf-51bf60200d1e"}, {b"id": b"lf-51bf60200d1e"}]
)
async def test_zeroconf_success(
    hass: HomeAssistant, mock_api: AsyncMock, properties: dict
) -> None:
    """Discover and confirm a device with string or byte TXT records."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery(properties),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"name": "Garage"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "lf-51bf60200d1e"
    assert result["data"] == {CONF_HOST: "192.168.2.123", CONF_PORT: 80}


async def test_id_mismatch(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery({"id": "wrong"}),
    )
    assert result["reason"] == "id_mismatch"


async def test_rediscovery_updates_host(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="lf-51bf60200d1e",
        data={CONF_HOST: "old", CONF_PORT: 80},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery({"id": "lf-51bf60200d1e"}),
    )
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.2.123"


async def test_user_setup_is_discovery_only(hass: HomeAssistant) -> None:
    """Manual setup does not ask users for internal connection data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_only"
