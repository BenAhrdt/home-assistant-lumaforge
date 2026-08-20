"""Data coordinator for LumaForge."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    LumaForgeApiClient,
    LumaForgeAutomation,
    LumaForgeAutomationState,
    LumaForgeData,
    LumaForgeError,
    LumaForgeUpdateStatus,
    parse_automation_state,
    parse_automations,
    parse_layout,
    parse_scenes,
    parse_status,
    parse_update_status,
    parse_zones,
)
from .const import DOMAIN, OFFLINE_UPDATE_INTERVAL, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

_ACTIVE_UPDATE_STATES = frozenset(
    ("checking", "downloading", "installing", "restarting")
)


class LumaForgeCoordinator(DataUpdateCoordinator[LumaForgeData]):
    """Poll a LumaForge device."""

    def __init__(self, hass: HomeAssistant, client: LumaForgeApiClient) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.automation_lock = asyncio.Lock()
        self.zone_states: dict[str, dict[str, Any]] = {}
        self.automation_state: LumaForgeAutomationState | None = None
        self.automation_state_received_at: datetime | None = None
        self.system_status_received_at: datetime | None = None
        self.update_status: LumaForgeUpdateStatus | None = None
        self.update_status_received_at: datetime | None = None
        self.ota_restart_expected = False
        self.loaded_platforms: list[Platform] = []
        self._offline = False
        self._websocket_connected = False

    @property
    def supports_automation_sequences(self) -> bool:
        """Return whether native multi-step commands are confirmed."""
        return "automation_sequences" in self.data.info.capabilities

    @property
    def supports_ota_update(self) -> bool:
        """Return whether native firmware OTA is confirmed."""
        return "ota_update" in self.data.info.capabilities

    @property
    def installed_firmware_version(self) -> str | None:
        """Prefer the freshest status version over the identity snapshot."""
        return self.data.status.version or self.data.info.firmware_version

    def _reconcile_update_status(self, installed: str | None) -> None:
        """Finish a stale OTA state once the target version is confirmed."""
        if self.update_status is None or installed is None:
            return
        self.update_status = replace(self.update_status, current_version=installed)
        if (
            self.update_status.state in _ACTIVE_UPDATE_STATES
            and installed == self.update_status.latest_version
        ):
            self.update_status = replace(
                self.update_status,
                state="up_to_date",
                progress=None,
                error=None,
            )
            self.update_status_received_at = datetime.now(UTC)
            self.ota_restart_expected = False

    def mark_update_failed(self, error: str) -> None:
        """End locally when an OTA command aborts without a terminal event."""
        if self.update_status is None:
            return
        self.update_status = replace(
            self.update_status,
            state="failed",
            progress=None,
            error=error,
        )
        self.update_status_received_at = datetime.now(UTC)
        self.ota_restart_expected = False
        self.async_update_listeners()

    @property
    def platforms(self) -> list[Platform]:
        """Return platforms backed by endpoints confirmed during setup."""
        resources = self.client.supported_resources
        platforms = [Platform.BINARY_SENSOR, Platform.SENSOR]
        if (
            self.supports_automation_sequences
            or "scenes" in resources
            or "automations" in resources
        ):
            platforms.append(Platform.BUTTON)
        if "scenes" in resources:
            platforms.append(Platform.SCENE)
        if "zones" in resources:
            platforms.append(Platform.LIGHT)
        if "automations" in resources:
            platforms.append(Platform.SWITCH)
        if self.supports_ota_update:
            platforms.append(Platform.UPDATE)
        return platforms

    async def _async_update_data(self) -> LumaForgeData:
        try:
            if self._offline:
                # While offline, probe only the lightweight identity endpoint. A
                # successful probe is followed immediately by a complete refresh.
                await self.client.async_get_info()
            data = await self.client.async_get_data()
        except LumaForgeError as err:
            self._offline = True
            self.update_interval = OFFLINE_UPDATE_INTERVAL
            raise UpdateFailed(str(err)) from err
        self._offline = False
        self.update_interval = UPDATE_INTERVAL
        installed = data.status.version or data.info.firmware_version
        self._reconcile_update_status(installed)
        return data

    async def async_start(self) -> None:
        """Start optional push updates after the first REST refresh."""
        await self.client.async_start_websocket(self._async_websocket_event)

    async def async_shutdown(self) -> None:
        """Stop all client background work."""
        await self.client.async_close()

    async def _async_websocket_event(self, event: dict[str, Any]) -> None:
        """Apply validated event payloads or refresh the affected resource."""
        event_type = event.get("type")
        if event_type == "disconnected":
            was_connected = self._websocket_connected
            self._websocket_connected = False
            self.zone_states.clear()
            self.automation_state = None
            self.automation_state_received_at = None
            self.async_update_listeners()
            if was_connected:
                await self.async_request_refresh()
            return
        if event_type == "connected":
            self._websocket_connected = True
            self.automation_state = None
            self.automation_state_received_at = None
            await self.async_request_refresh()
            return
        if event_type == "system.status":
            try:
                status = parse_status(event, self.data.status)
            except LumaForgeError as err:
                _LOGGER.debug("Ignoring invalid system status: %s", err)
                return
            self.system_status_received_at = datetime.now(UTC)
            self._reconcile_update_status(status.version)
            self.async_set_updated_data(replace(self.data, status=status))
            return
        if event_type == "update.status":
            try:
                self.update_status = parse_update_status(event)
            except LumaForgeError as err:
                _LOGGER.debug("Ignoring invalid update status: %s", err)
                return
            self.update_status_received_at = datetime.now(UTC)
            self.ota_restart_expected = self.update_status.state == "restarting"
            if self.update_status.state == "failed":
                _LOGGER.warning(
                    "LumaForge firmware update failed: %s",
                    self.update_status.error or "unknown error",
                )
            self.async_update_listeners()
            return
        if event_type == "automation.state":
            try:
                self.automation_state = parse_automation_state(event)
            except LumaForgeError as err:
                _LOGGER.debug("Ignoring invalid automation state: %s", err)
                return
            self.automation_state_received_at = datetime.now(UTC)
            self.async_update_listeners()
            return
        updates = {
            "layout.updated": ("layout", parse_layout, self.client.async_get_layout),
            "zones.updated": ("zones", parse_zones, self.client.async_get_zones),
            "scenes.updated": ("scenes", parse_scenes, self.client.async_get_scenes),
            "automations.updated": (
                "automations",
                parse_automations,
                self.client.async_get_automations,
            ),
        }
        update = updates.get(event_type)
        if update is None:
            return
        field_name, parser, getter = update
        try:
            value = parser(event["payload"]) if "payload" in event else await getter()
        except LumaForgeError as err:
            _LOGGER.debug("Unable to process %s event: %s", event_type, err)
            return
        self.async_set_updated_data(replace(self.data, **{field_name: value}))

    def set_zone_optimistic_state(self, zone_id: str, state: dict[str, Any]) -> None:
        """Remember only acknowledged Home Assistant zone commands."""
        self.zone_states[zone_id] = state
        self.async_update_listeners()

    async def async_set_automation_enabled(
        self, automation_id: str, enabled: bool
    ) -> LumaForgeAutomation:
        """Serialize full-list writes so concurrent changes are not lost."""
        async with self.automation_lock:
            current = await self.client.async_get_automations()
            if not any(item.automation_id == automation_id for item in current):
                raise ValueError(f"Unknown automation: {automation_id}")
            payload = []
            for item in current:
                raw = dict(item.raw)
                if item.automation_id == automation_id:
                    raw["enabled"] = enabled
                payload.append(raw)
            updated = await self.client.async_put_automations(payload)
            self.async_set_updated_data(replace(self.data, automations=updated))
            return next(item for item in updated if item.automation_id == automation_id)
