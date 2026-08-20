"""Tests for LumaForge entities."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.lumaforge.api import LumaForgeData, LumaForgeStatus
from custom_components.lumaforge.binary_sensor import LumaForgeConnectivitySensor
from custom_components.lumaforge.sensor import SENSORS, LumaForgeSensor

from .conftest import INFO, STATUS


def entry_with_data(data: LumaForgeData) -> MagicMock:
    """Create a minimal typed-entry stand-in."""
    entry = MagicMock()
    entry.unique_id = data.info.device_id
    entry.runtime_data.data = data
    entry.runtime_data.last_update_success = True
    entry.runtime_data.client.base_url = "http://192.168.2.123:80"
    return entry


def test_entity_values_unique_ids_and_device_info() -> None:
    """Entities expose stable IDs, values, and one shared device."""
    entry = entry_with_data(LumaForgeData(INFO, STATUS))
    entities = [LumaForgeSensor(entry, description) for description in SENSORS]
    cpu = next(
        entity for entity in entities if entity.entity_description.key == "cpu_usage"
    )
    memory = next(
        entity for entity in entities if entity.entity_description.key == "memory_usage"
    )
    assert cpu.unique_id == "lf-51bf60200d1e_cpu_usage"
    assert cpu.native_value == 4.2
    assert memory.native_value == 36.6
    assert cpu.device_info["identifiers"] == {("lumaforge", "lf-51bf60200d1e")}
    assert cpu.device_info["sw_version"] == "0.2.0-alpha.1"


def test_missing_optional_values() -> None:
    """Missing dynamic values produce unknown states without exceptions."""
    status = LumaForgeStatus(None, None, None, None, None, None)
    entry = entry_with_data(LumaForgeData(INFO, status))
    entities = [LumaForgeSensor(entry, description) for description in SENSORS]
    cpu = next(
        entity for entity in entities if entity.entity_description.key == "cpu_usage"
    )
    memory = next(
        entity for entity in entities if entity.entity_description.key == "memory_usage"
    )
    connectivity = LumaForgeConnectivitySensor(entry)
    assert cpu.native_value is None
    assert memory.native_value is None
    assert connectivity.is_on is True


def test_connectivity_reports_disconnected_after_failed_update() -> None:
    """The connectivity entity stays available to report an outage."""
    entry = entry_with_data(LumaForgeData(INFO, STATUS))
    entry.runtime_data.last_update_success = False
    entity = LumaForgeConnectivitySensor(entry)
    assert entity.available is True
    assert entity.is_on is False
