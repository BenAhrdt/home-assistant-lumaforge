"""Data coordinator for LumaForge."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    LumaForgeApiClient,
    LumaForgeAutomation,
    LumaForgeData,
    LumaForgeError,
    parse_automations,
    parse_layout,
    parse_scenes,
    parse_zones,
)
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


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
        self.loaded_platforms: list[Platform] = []

    @property
    def platforms(self) -> list[Platform]:
        """Return platforms backed by endpoints confirmed during setup."""
        resources = self.client.supported_resources
        platforms = [Platform.BINARY_SENSOR, Platform.SENSOR]
        if "scenes" in resources or "automations" in resources:
            platforms.append(Platform.BUTTON)
        if "scenes" in resources:
            platforms.append(Platform.SCENE)
        if "zones" in resources:
            platforms.append(Platform.LIGHT)
        if "automations" in resources:
            platforms.append(Platform.SWITCH)
        return platforms

    async def _async_update_data(self) -> LumaForgeData:
        try:
            return await self.client.async_get_data()
        except LumaForgeError as err:
            raise UpdateFailed(str(err)) from err

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
            self.zone_states.clear()
            self.async_update_listeners()
            return
        if event_type == "connected":
            await self.async_request_refresh()
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
