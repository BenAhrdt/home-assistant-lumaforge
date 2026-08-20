"""Tests for the LumaForge coordinator."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.lumaforge.api import (
    LumaForgeConnectionError,
    LumaForgeData,
    LumaForgeScene,
    parse_automations,
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


async def test_websocket_update_with_payload(hass: HomeAssistant) -> None:
    """Apply a validated simulator event payload without a REST request."""
    client = MagicMock()
    coordinator = LumaForgeCoordinator(hass, client)
    coordinator.async_set_updated_data(LumaForgeData(INFO, STATUS))

    await coordinator._async_websocket_event(
        {"type": "scenes.updated", "payload": [{"id": "new", "name": "New"}]}
    )

    assert coordinator.data.scenes[0].scene_id == "new"
    client.async_get_scenes.assert_not_called()


@pytest.mark.parametrize(
    ("event_type", "payload", "field", "identifier"),
    [
        ("zones.updated", [{"id": "z", "name": "Zone", "leds": [1]}], "zones", "z"),
        (
            "automations.updated",
            [{"id": "a", "name": "Auto", "sceneId": "s", "enabled": True}],
            "automations",
            "a",
        ),
    ],
)
async def test_other_websocket_payload_updates(
    hass: HomeAssistant,
    event_type: str,
    payload: list[dict],
    field: str,
    identifier: str,
) -> None:
    client = MagicMock()
    coordinator = LumaForgeCoordinator(hass, client)
    coordinator.async_set_updated_data(LumaForgeData(INFO, STATUS))

    await coordinator._async_websocket_event({"type": event_type, "payload": payload})

    item = getattr(coordinator.data, field)[0]
    assert getattr(item, f"{field.removesuffix('s')}_id") == identifier


async def test_websocket_update_without_payload(hass: HomeAssistant) -> None:
    """Reload an ESP32 event without a payload through REST."""
    client = MagicMock()
    client.async_get_scenes = AsyncMock(
        return_value=(LumaForgeScene("fresh", "Fresh", (), {}),)
    )
    coordinator = LumaForgeCoordinator(hass, client)
    coordinator.async_set_updated_data(LumaForgeData(INFO, STATUS))

    await coordinator._async_websocket_event({"type": "scenes.updated"})

    assert coordinator.data.scenes[0].scene_id == "fresh"
    client.async_get_scenes.assert_awaited_once()


async def test_parallel_automation_updates_preserve_changes(
    hass: HomeAssistant,
) -> None:
    """Serialize full-list writes and re-read before each mutation."""
    raw = [
        {"id": "one", "name": "One", "sceneId": "s1", "enabled": False},
        {"id": "two", "name": "Two", "sceneId": "s2", "enabled": False},
    ]
    client = MagicMock()

    async def get_automations():
        return parse_automations(raw)

    async def put_automations(payload):
        raw[:] = payload
        return parse_automations(raw)

    client.async_get_automations = AsyncMock(side_effect=get_automations)
    client.async_put_automations = AsyncMock(side_effect=put_automations)
    coordinator = LumaForgeCoordinator(hass, client)
    coordinator.async_set_updated_data(LumaForgeData(INFO, STATUS))

    await asyncio.gather(
        coordinator.async_set_automation_enabled("one", True),
        coordinator.async_set_automation_enabled("two", True),
    )

    assert all(item["enabled"] for item in raw)
