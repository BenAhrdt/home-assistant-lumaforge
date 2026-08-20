"""Tests for native LumaForge firmware updates."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.exceptions import HomeAssistantError

from custom_components.lumaforge.api import (
    LumaForgeData,
    LumaForgeUpdateStatus,
)
from custom_components.lumaforge.update import (
    LumaForgeFirmwareUpdate,
    async_setup_entry,
)

from .conftest import OTA_INFO, STATUS


def update_entry(state: str = "available", **changes) -> MagicMock:
    entry = MagicMock()
    entry.unique_id = OTA_INFO.device_id
    coordinator = entry.runtime_data
    coordinator.data = LumaForgeData(OTA_INFO, replace(STATUS, version="0.2.0-alpha.3"))
    coordinator.last_update_success = True
    coordinator.supports_ota_update = True
    coordinator.client.websocket_connected = True
    coordinator.client.async_install_update = AsyncMock()
    values = {
        "current_version": "0.2.0-alpha.3",
        "latest_version": "0.2.0-alpha.4",
        "release_url": "https://example.test/v0.2.0-alpha.4",
        "size_bytes": 1166144,
        "progress": None,
        "error": None,
    }
    values.update(changes)
    coordinator.update_status = LumaForgeUpdateStatus(state, **values)
    coordinator.update_status_received_at = datetime.now(UTC)
    coordinator.installed_firmware_version = "0.2.0-alpha.3"
    return entry


async def test_update_entity_created_only_for_capability(hass) -> None:
    entry = update_entry()
    added = []
    await async_setup_entry(hass, entry, added.extend)
    assert len(added) == 1

    entry.runtime_data.supports_ota_update = False
    added.clear()
    await async_setup_entry(hass, entry, added.extend)
    assert added == []


def test_update_entity_versions_and_metadata() -> None:
    entity = LumaForgeFirmwareUpdate(update_entry())

    assert entity.unique_id.endswith("_firmware")
    assert entity.available
    assert entity.installed_version == "0.2.0-alpha.3"
    assert entity.latest_version == "0.2.0-alpha.4"
    assert entity.release_url == "https://example.test/v0.2.0-alpha.4"
    assert entity.supported_features & UpdateEntityFeature.INSTALL
    assert entity.supported_features & UpdateEntityFeature.PROGRESS


@pytest.mark.parametrize(
    ("installed", "latest", "expected"),
    [
        ("0.2.0-alpha.3", "0.2.0-alpha.4", STATE_ON),
        ("0.2.0-alpha.4", "0.2.0-beta.1", STATE_ON),
        ("0.2.0-beta.1", "0.2.0", STATE_ON),
        ("0.2.0", "0.2.0-beta.1", STATE_OFF),
    ],
)
def test_update_entity_uses_semantic_prerelease_order(
    installed: str, latest: str, expected: str
) -> None:
    entry = update_entry(current_version=installed, latest_version=latest)
    entry.runtime_data.installed_firmware_version = installed
    assert LumaForgeFirmwareUpdate(entry).state == expected


@pytest.mark.parametrize(
    ("state", "in_progress", "progress", "offers_update"),
    [
        ("idle", False, None, False),
        ("checking", True, None, False),
        ("available", False, None, True),
        ("up_to_date", False, None, False),
        ("downloading", True, 62, True),
        ("installing", True, None, True),
        ("restarting", True, None, True),
        ("failed", False, None, False),
    ],
)
def test_update_entity_state_mapping(
    state: str, in_progress: bool, progress: float | None, offers_update: bool
) -> None:
    latest = "0.2.0-alpha.3" if state == "up_to_date" else "0.2.0-alpha.4"
    entity = LumaForgeFirmwareUpdate(
        update_entry(
            state,
            latest_version=latest,
            progress=progress,
            error="checksum_mismatch" if state == "failed" else None,
        )
    )

    assert entity.in_progress is in_progress
    assert entity.update_percentage == progress
    assert (entity.latest_version != entity.installed_version) is offers_update
    if state == "failed":
        assert "checksum" in entity.release_summary


async def test_update_entity_installs_only_confirmed_latest() -> None:
    entry = update_entry()
    entity = LumaForgeFirmwareUpdate(entry)

    await entity.async_install(None, False)
    entry.runtime_data.client.async_install_update.assert_awaited_once_with(
        "0.2.0-alpha.4"
    )

    with pytest.raises(HomeAssistantError, match="Only the device-confirmed"):
        await entity.async_install("0.2.0-alpha.2", False)


async def test_update_entity_rejects_unconfirmed_install() -> None:
    entity = LumaForgeFirmwareUpdate(update_entry("idle"))
    with pytest.raises(HomeAssistantError, match="No confirmed"):
        await entity.async_install(None, False)
