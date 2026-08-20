"""Native firmware update entity for LumaForge."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LumaForgeConfigEntry
from .api import LumaForgeError
from .entity import LumaForgeEntity

_ACTIVE_STATES = frozenset(("checking", "downloading", "installing", "restarting"))
_OFFER_STATES = frozenset(("available", "downloading", "installing", "restarting"))
_ERROR_MESSAGES = {
    "manifest_connection_failed": "Unable to reach the firmware manifest",
    "invalid_manifest": "The firmware manifest is invalid",
    "download_failed": "The firmware download failed",
    "checksum_mismatch": "The downloaded firmware checksum does not match",
    "install_failed": "The firmware installation failed",
    "update unavailable": "The requested firmware update is unavailable",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LumaForgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OTA only for devices that explicitly advertise it."""
    if entry.runtime_data.supports_ota_update:
        async_add_entities([LumaForgeFirmwareUpdate(entry)])


class LumaForgeFirmwareUpdate(LumaForgeEntity, UpdateEntity):
    """Install firmware selected and verified by the device itself."""

    _attr_translation_key = "firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_title = "LumaForge"

    def __init__(self, entry: LumaForgeConfigEntry) -> None:
        super().__init__(entry, "firmware")

    @property
    def available(self) -> bool:
        return bool(
            super().available
            and self.coordinator.supports_ota_update
            and self.coordinator.client.websocket_connected
        )

    @property
    def installed_version(self) -> str | None:
        status = self.coordinator.update_status
        return (
            status.current_version
            if status and status.current_version
            else self.coordinator.installed_firmware_version
        )

    @property
    def latest_version(self) -> str | None:
        status = self.coordinator.update_status
        installed = self.installed_version
        if status is None:
            return installed
        if status.state in _OFFER_STATES:
            return status.latest_version or installed
        if status.state == "up_to_date":
            return status.latest_version or installed
        return installed

    @property
    def release_url(self) -> str | None:
        status = self.coordinator.update_status
        return status.release_url if status else None

    @property
    def release_summary(self) -> str | None:
        status = self.coordinator.update_status
        if status is None:
            return None
        if status.state == "failed":
            return _ERROR_MESSAGES.get(status.error or "", status.error)
        if status.size_bytes is not None:
            return f"Device-verified firmware image: {status.size_bytes} bytes"
        return None

    @property
    def in_progress(self) -> bool:
        status = self.coordinator.update_status
        return bool(status and status.state in _ACTIVE_STATES)

    @property
    def update_percentage(self) -> float | None:
        status = self.coordinator.update_status
        return status.progress if status and status.state == "downloading" else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.coordinator.update_status
        return {
            "update_state": status.state if status else "idle",
            "error": status.error if status else None,
            "size_bytes": status.size_bytes if status else None,
            "last_update": (
                self.coordinator.update_status_received_at.isoformat()
                if self.coordinator.update_status_received_at
                else None
            ),
        }

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Tell the device to install exactly its confirmed latest release."""
        if backup:
            raise HomeAssistantError("Firmware backup is not supported")
        status = self.coordinator.update_status
        latest = status.latest_version if status else None
        if status is None or status.state != "available" or latest is None:
            raise HomeAssistantError("No confirmed firmware update is available")
        requested = version or latest
        if requested != latest:
            raise HomeAssistantError(
                f"Only the device-confirmed latest version {latest} can be installed"
            )
        try:
            await self.coordinator.client.async_install_update(latest)
        except LumaForgeError as err:
            raise HomeAssistantError(str(err)) from err
