"""Base entity for LumaForge."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LumaForgeConfigEntry
from .const import DOMAIN, MANUFACTURER
from .coordinator import LumaForgeCoordinator


class LumaForgeEntity(CoordinatorEntity[LumaForgeCoordinator]):
    """Base class shared by all LumaForge entities."""

    _attr_has_entity_name = True

    def __init__(self, entry: LumaForgeConfigEntry, key: str) -> None:
        super().__init__(entry.runtime_data)
        self._attr_unique_id = f"{entry.unique_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return current device registry information."""
        info = self.coordinator.data.info
        return DeviceInfo(
            identifiers={(DOMAIN, info.device_id)},
            name=info.device_name,
            manufacturer=MANUFACTURER,
            model=info.model,
            sw_version=info.firmware_version,
            serial_number=info.device_id,
            configuration_url=f"{self.coordinator.client.base_url}/",
        )
