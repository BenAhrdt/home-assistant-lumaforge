"""Tests for targeted LED services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.lumaforge.api import (
    LumaForgeAutomation,
    LumaForgeAutomationState,
    LumaForgeAutomationStep,
    LumaForgeData,
    LumaForgeLayout,
    LumaForgeZone,
)
from custom_components.lumaforge.const import DATA_COORDINATORS, DOMAIN
from custom_components.lumaforge.services import async_setup_services

from .conftest import SEQUENCE_INFO, STATUS


def add_coordinator(hass: HomeAssistant) -> MagicMock:
    """Add one service-targetable coordinator."""
    coordinator = MagicMock()
    coordinator.data = LumaForgeData(
        SEQUENCE_INFO,
        STATUS,
        LumaForgeLayout({}, frozenset(range(5)), {"out": frozenset(range(5))}),
        (LumaForgeZone("zone", "Zone", (1, 2), {}),),
        automations=(
            LumaForgeAutomation(
                "auto",
                "Sequence",
                "scene",
                True,
                {},
                (LumaForgeAutomationStep("scene", "manual", None),),
            ),
        ),
    )
    coordinator.client.async_set_preview = AsyncMock()
    coordinator.client.async_start_automation = AsyncMock()
    coordinator.client.async_stop_automation = AsyncMock()
    coordinator.client.async_next_automation_step = AsyncMock()
    coordinator.client.websocket_connected = True
    coordinator.supports_automation_sequences = True
    coordinator.automation_state = LumaForgeAutomationState(
        "running", "auto", 0, "scene", 0
    )
    hass.data[DOMAIN] = {DATA_COORDINATORS: {"entry": coordinator}}
    return coordinator


async def test_led_and_range_services(hass: HomeAssistant) -> None:
    coordinator = add_coordinator(hass)
    await async_setup_services(hass)

    await hass.services.async_call(
        DOMAIN,
        "set_led",
        {"config_entry_id": "entry", "led_index": 2, "color": [90, 165, 225]},
        blocking=True,
    )
    coordinator.client.async_set_preview.assert_awaited_with(
        (2,), "#5aa5e1", 1.0, "solid", 1.0, "forward"
    )

    await hass.services.async_call(
        DOMAIN,
        "set_led_range",
        {
            "config_entry_id": "entry",
            "output_id": "out",
            "start_index": 1,
            "end_index": 3,
            "color": [255, 0, 0],
        },
        blocking=True,
    )
    coordinator.client.async_set_preview.assert_awaited_with(
        (1, 2, 3), "#ff0000", 1.0, "solid", 1.0, "forward"
    )


async def test_apply_zone_and_invalid_index(hass: HomeAssistant) -> None:
    coordinator = add_coordinator(hass)
    await async_setup_services(hass)
    await hass.services.async_call(
        DOMAIN,
        "apply_to_zone",
        {"config_entry_id": "entry", "zone_id": "zone", "color": [1, 2, 3]},
        blocking=True,
    )
    coordinator.client.async_set_preview.assert_awaited_with(
        (1, 2), "#010203", 1.0, "solid", 1.0, "forward"
    )

    with pytest.raises(ServiceValidationError, match="Invalid LED"):
        await hass.services.async_call(
            DOMAIN,
            "set_led",
            {"config_entry_id": "entry", "led_index": 99, "color": [1, 2, 3]},
            blocking=True,
        )


async def test_native_automation_services(hass: HomeAssistant) -> None:
    coordinator = add_coordinator(hass)
    await async_setup_services(hass)

    await hass.services.async_call(
        DOMAIN,
        "start_automation",
        {"config_entry_id": "entry", "automation_id": "auto"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "next_automation_step", {"config_entry_id": "entry"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "stop_automation", {"config_entry_id": "entry"}, blocking=True
    )

    coordinator.client.async_start_automation.assert_awaited_once_with("auto")
    coordinator.client.async_next_automation_step.assert_awaited_once()
    coordinator.client.async_stop_automation.assert_awaited_once()


async def test_automation_services_reject_legacy_firmware(
    hass: HomeAssistant,
) -> None:
    coordinator = add_coordinator(hass)
    coordinator.supports_automation_sequences = False
    await async_setup_services(hass)

    with pytest.raises(ServiceValidationError, match="does not support"):
        await hass.services.async_call(
            DOMAIN,
            "start_automation",
            {"config_entry_id": "entry", "automation_id": "auto"},
            blocking=True,
        )
