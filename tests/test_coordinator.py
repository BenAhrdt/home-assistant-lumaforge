"""Tests for the LumaForge coordinator."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.lumaforge.api import (
    LumaForgeAutomationState,
    LumaForgeConnectionError,
    LumaForgeData,
    LumaForgeScene,
    LumaForgeUpdateStatus,
    parse_automations,
)
from custom_components.lumaforge.const import OFFLINE_UPDATE_INTERVAL, UPDATE_INTERVAL
from custom_components.lumaforge.coordinator import LumaForgeCoordinator

from .conftest import INFO, OTA_INFO, SEQUENCE_INFO, STATUS


async def test_coordinator_update(hass: HomeAssistant) -> None:
    """Coordinator returns combined API data."""
    client = MagicMock()
    client.async_get_data = AsyncMock(return_value=LumaForgeData(INFO, STATUS))
    coordinator = LumaForgeCoordinator(hass, client)
    data = await coordinator._async_update_data()
    assert data.info.device_id == "lf-51bf60200d1e"
    assert data.status.cpu_percent == 4.2


def test_ota_platform_requires_capability(hass: HomeAssistant) -> None:
    client = MagicMock()
    client.supported_resources = set()
    coordinator = LumaForgeCoordinator(hass, client)
    coordinator.async_set_updated_data(LumaForgeData(INFO, STATUS))
    assert Platform.UPDATE not in coordinator.platforms

    coordinator.async_set_updated_data(LumaForgeData(OTA_INFO, STATUS))
    assert Platform.UPDATE in coordinator.platforms


async def test_coordinator_unavailable(hass: HomeAssistant) -> None:
    """Communication errors become update failures."""
    client = MagicMock()
    client.async_get_data = AsyncMock(side_effect=LumaForgeConnectionError)
    coordinator = LumaForgeCoordinator(hass, client)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.update_interval == OFFLINE_UPDATE_INTERVAL


async def test_offline_probe_then_complete_recovery(hass: HomeAssistant) -> None:
    """Probe only info while offline and reload everything after it returns."""
    client = MagicMock()
    client.async_get_info = AsyncMock(side_effect=[LumaForgeConnectionError, INFO])
    client.async_get_data = AsyncMock(
        side_effect=[LumaForgeConnectionError, LumaForgeData(INFO, STATUS)]
    )
    coordinator = LumaForgeCoordinator(hass, client)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    client.async_get_data.assert_awaited_once()

    data = await coordinator._async_update_data()
    assert data.info.device_id == INFO.device_id
    assert client.async_get_info.await_count == 2
    assert client.async_get_data.await_count == 2
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_established_websocket_disconnect_triggers_probe(
    hass: HomeAssistant,
) -> None:
    client = MagicMock()
    coordinator = LumaForgeCoordinator(hass, client)
    coordinator.async_set_updated_data(LumaForgeData(INFO, STATUS))
    coordinator.async_request_refresh = AsyncMock()

    await coordinator._async_websocket_event({"type": "connected"})
    coordinator.async_request_refresh.reset_mock()
    await coordinator._async_websocket_event({"type": "disconnected"})

    coordinator.async_request_refresh.assert_awaited_once()


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


async def test_authoritative_automation_state_and_reconnect(
    hass: HomeAssistant,
) -> None:
    client = MagicMock()
    client.async_get_data = AsyncMock(return_value=LumaForgeData(SEQUENCE_INFO, STATUS))
    coordinator = LumaForgeCoordinator(hass, client)
    coordinator.async_set_updated_data(LumaForgeData(SEQUENCE_INFO, STATUS))

    await coordinator._async_websocket_event(
        {
            "type": "automation.state",
            "state": "running",
            "automationId": "auto",
            "stepIndex": 0,
            "sceneId": "scene",
            "elapsedSeconds": 1.5,
        }
    )

    assert coordinator.automation_state == LumaForgeAutomationState(
        "running", "auto", 0, "scene", 1.5
    )
    assert coordinator.automation_state_received_at is not None

    await coordinator._async_websocket_event(
        {"type": "automation.state", "state": "stopped", "elapsedSeconds": 0}
    )
    assert coordinator.automation_state == LumaForgeAutomationState(
        "stopped", None, None, None, 0
    )

    await coordinator._async_websocket_event({"type": "disconnected"})
    assert coordinator.automation_state is None
    assert coordinator.automation_state_received_at is None

    await coordinator._async_websocket_event({"type": "connected"})
    assert coordinator.automation_state is None
    client.async_get_data.assert_awaited_once()

    await coordinator._async_websocket_event(
        {
            "type": "automation.state",
            "state": "running",
            "automationId": "auto",
            "stepIndex": 1,
            "sceneId": "other",
            "elapsedSeconds": 0,
        }
    )
    assert coordinator.automation_state.scene_id == "other"


async def test_system_and_update_status_websocket(hass: HomeAssistant) -> None:
    client = MagicMock()
    coordinator = LumaForgeCoordinator(hass, client)
    coordinator.async_set_updated_data(LumaForgeData(OTA_INFO, STATUS))

    await coordinator._async_websocket_event(
        {
            "type": "system.status",
            "version": "0.2.0-alpha.4",
            "cpuPercent": 18.4,
            "firmwareUsedBytes": 75,
            "firmwareCapacityBytes": 100,
        }
    )
    await coordinator._async_websocket_event(
        {
            "type": "update.status",
            "state": "downloading",
            "currentVersion": "0.2.0-alpha.3",
            "latestVersion": "0.2.0-alpha.4",
            "progress": 62,
        }
    )

    assert coordinator.data.status.version == "0.2.0-alpha.4"
    assert coordinator.data.status.cpu_percent == 18.4
    assert coordinator.data.status.memory_total_bytes == STATUS.memory_total_bytes
    assert coordinator.system_status_received_at is not None
    assert coordinator.update_status.progress == 62
    assert coordinator.update_status_received_at is not None


async def test_ota_reconnect_confirms_installed_version(hass: HomeAssistant) -> None:
    client = MagicMock()
    client.async_get_data = AsyncMock(
        return_value=LumaForgeData(OTA_INFO, replace(STATUS, version="0.2.0-alpha.4"))
    )
    coordinator = LumaForgeCoordinator(hass, client)
    coordinator.async_set_updated_data(LumaForgeData(OTA_INFO, STATUS))
    coordinator.update_status = LumaForgeUpdateStatus(
        "restarting",
        "0.2.0-alpha.3",
        "0.2.0-alpha.4",
        None,
        None,
        None,
        None,
    )
    coordinator.ota_restart_expected = True

    data = await coordinator._async_update_data()

    coordinator.async_set_updated_data(data)
    assert coordinator.installed_firmware_version == "0.2.0-alpha.4"
    assert coordinator.update_status.state == "up_to_date"
    assert coordinator.ota_restart_expected is False


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
