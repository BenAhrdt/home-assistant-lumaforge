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
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfInformation,
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
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
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
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.memory_used_bytes,
    ),
    LumaForgeSensorDescription(
        key="memory_total",
        translation_key="memory_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
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
    entities: list[SensorEntity] = [
        LumaForgeSensor(entry, description) for description in SENSORS
    ]
    if entry.runtime_data.supports_automation_sequences:
        entities.append(LumaForgeAutomationStatusSensor(entry))
    async_add_entities(entities)


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


class LumaForgeAutomationStatusSensor(LumaForgeEntity, SensorEntity):
    """Expose the authoritative device-side automation runtime state."""

    _attr_translation_key = "automation_status"

    def __init__(self, entry: LumaForgeConfigEntry) -> None:
        super().__init__(entry, "automation_status")

    @property
    def available(self) -> bool:
        return bool(
            super().available
            and self.coordinator.client.websocket_connected
            and self.coordinator.automation_state is not None
        )

    @property
    def native_value(self) -> str | None:
        state = self.coordinator.automation_state
        return state.state if state else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.coordinator.automation_state
        if state is None:
            return {}
        automation = next(
            (
                item
                for item in self.coordinator.data.automations
                if item.automation_id == state.automation_id
            ),
            None,
        )
        scene = next(
            (
                item
                for item in self.coordinator.data.scenes
                if item.scene_id == state.scene_id
            ),
            None,
        )
        step = None
        if (
            automation is not None
            and state.step_index is not None
            and state.step_index < len(automation.steps)
        ):
            step = automation.steps[state.step_index]
        return {
            "automation_id": state.automation_id,
            "automation_name": automation.name if automation else None,
            "step_index": state.step_index,
            "step_number": state.step_index + 1
            if state.step_index is not None
            else None,
            "step_count": len(automation.steps) if automation else None,
            "scene_id": state.scene_id,
            "scene_name": scene.name if scene else None,
            "elapsed_seconds": state.elapsed_seconds,
            "advance": step.advance if step else None,
            "duration_seconds": step.duration_seconds if step else None,
            "last_update": (
                self.coordinator.automation_state_received_at.isoformat()
                if self.coordinator.automation_state_received_at
                else None
            ),
        }
