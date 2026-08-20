"""Binary sensors for LumaForge."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LumaForgeConfigEntry
from .entity import LumaForgeEntity

DESCRIPTION = BinarySensorEntityDescription(
    key="connectivity",
    translation_key="connectivity",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LumaForgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the connectivity sensor."""
    async_add_entities([LumaForgeConnectivitySensor(entry)])


class LumaForgeConnectivitySensor(LumaForgeEntity, BinarySensorEntity):
    """Represent API/network connectivity."""

    entity_description = DESCRIPTION

    def __init__(self, entry: LumaForgeConfigEntry) -> None:
        super().__init__(entry, DESCRIPTION.key)

    @property
    def is_on(self) -> bool:
        """Return whether the device reports a connected network."""
        connected = self.coordinator.data.status.connected
        if connected is None:
            connected = self.coordinator.data.info.connected
        return connected is not False
