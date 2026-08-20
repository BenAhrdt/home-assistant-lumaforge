"""Diagnostic sensors for LumaForge."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfDataSize,
    UnitOfSignalStrength,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LumaForgeConfigEntry
from .api import LumaForgeData
from .entity import LumaForgeEntity


@dataclass(frozen=True, kw_only=True)
class LumaForgeSensorDescription(SensorEntityDescription):
    """Describe a LumaForge sensor."""

    value_fn: Callable[[LumaForgeData], Any]
    attributes_fn: Callable[[LumaForgeData], dict[str, Any]] | None = None


SENSORS: tuple[LumaForgeSensorDescription, ...] = (
    LumaForgeSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=UnitOfSignalStrength.DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.status.rssi if data.status.rssi is not None else data.info.rssi
        ),
    ),
    LumaForgeSensorDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.cpu_percent,
    ),
    LumaForgeSensorDescription(
        key="memory_used",
        translation_key="memory_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfDataSize.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.memory_used_bytes,
    ),
    LumaForgeSensorDescription(
        key="memory_total",
        translation_key="memory_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfDataSize.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.memory_total_bytes,
    ),
    LumaForgeSensorDescription(
        key="memory_usage",
        translation_key="memory_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            round(
                data.status.memory_used_bytes / data.status.memory_total_bytes * 100, 1
            )
            if data.status.memory_used_bytes is not None
            and data.status.memory_total_bytes not in (None, 0)
            else None
        ),
    ),
    LumaForgeSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.ip_address or data.info.ip_address,
    ),
    LumaForgeSensorDescription(
        key="hostname",
        translation_key="hostname",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.info.hostname,
    ),
    LumaForgeSensorDescription(
        key="device_id",
        translation_key="device_id",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.info.device_id,
    ),
    LumaForgeSensorDescription(
        key="device_name",
        translation_key="device_name",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.info.device_name,
    ),
    LumaForgeSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.info.firmware_version,
    ),
    LumaForgeSensorDescription(
        key="api_version",
        translation_key="api_version",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.info.api_version,
    ),
    LumaForgeSensorDescription(
        key="model",
        translation_key="model",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.info.model,
    ),
    LumaForgeSensorDescription(
        key="capabilities",
        translation_key="capabilities",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: len(data.info.capabilities),
        attributes_fn=lambda data: {"capabilities": list(data.info.capabilities)},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LumaForgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LumaForge sensors."""
    async_add_entities(LumaForgeSensor(entry, description) for description in SENSORS)


class LumaForgeSensor(LumaForgeEntity, SensorEntity):
    """Represent one LumaForge diagnostic value."""

    entity_description: LumaForgeSensorDescription

    def __init__(
        self, entry: LumaForgeConfigEntry, description: LumaForgeSensorDescription
    ) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attributes_fn
        return fn(self.coordinator.data) if fn else None
