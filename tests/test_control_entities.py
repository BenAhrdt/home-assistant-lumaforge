"""Tests for LumaForge control entities and dynamic reconciliation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.light import LightEntityFeature

from custom_components.lumaforge.api import (
    LumaForgeAutomation,
    LumaForgeAutomationState,
    LumaForgeAutomationStep,
    LumaForgeData,
    LumaForgeScene,
    LumaForgeZone,
)
from custom_components.lumaforge.button import (
    LumaForgeAutomationButton,
    LumaForgeNextAutomationButton,
    LumaForgeStopAutomationButton,
)
from custom_components.lumaforge.dynamic import async_sync_entities
from custom_components.lumaforge.light import LumaForgeZoneLight
from custom_components.lumaforge.scene import LumaForgeSceneEntity
from custom_components.lumaforge.sensor import LumaForgeAutomationStatusSensor

from .conftest import INFO, SEQUENCE_INFO, STATUS


def control_entry(data: LumaForgeData) -> MagicMock:
    entry = MagicMock()
    entry.unique_id = INFO.device_id
    entry.runtime_data.data = data
    entry.runtime_data.last_update_success = True
    entry.runtime_data.client.websocket_connected = True
    entry.runtime_data.client.async_play_scene = AsyncMock()
    entry.runtime_data.client.async_set_preview = AsyncMock()
    entry.runtime_data.client.async_start_automation = AsyncMock()
    entry.runtime_data.client.async_stop_automation = AsyncMock()
    entry.runtime_data.client.async_next_automation_step = AsyncMock()
    entry.runtime_data.zone_states = {}
    entry.runtime_data.automation_state = None
    entry.runtime_data.automation_state_received_at = None
    entry.runtime_data.set_zone_optimistic_state = MagicMock()
    return entry


async def test_scene_rename_keeps_identity_and_activates() -> None:
    scene = LumaForgeScene("stable", "Old name", (), {})
    entry = control_entry(LumaForgeData(INFO, STATUS, scenes=(scene,)))
    entity = LumaForgeSceneEntity(entry, scene.scene_id)
    assert entity.unique_id.endswith("scene_stable")
    assert entity.translation_key == "stored_scene"
    assert entity.translation_placeholders == {"name": "Old name"}

    entry.runtime_data.data = LumaForgeData(
        INFO, STATUS, scenes=(LumaForgeScene("stable", "New name", (), {}),)
    )
    assert entity.translation_placeholders == {"name": "New name"}
    await entity.async_activate()
    entry.runtime_data.client.async_play_scene.assert_awaited_once_with("stable")


async def test_zone_light_uses_zone_selection() -> None:
    zone = LumaForgeZone("z1", "Bench", (1, 2), {})
    entry = control_entry(LumaForgeData(INFO, STATUS, zones=(zone,)))
    entity = LumaForgeZoneLight(entry, zone.zone_id)

    assert entity.translation_placeholders == {"name": "Bench"}
    assert entity.supported_features == LightEntityFeature.EFFECT
    assert entity.effect_list == ["solid", "blink", "pulse", "wipe", "chase", "rainbow"]

    await entity.async_turn_on(rgb_color=(255, 136, 0), brightness=128, effect="solid")

    entry.runtime_data.client.async_set_preview.assert_awaited_once_with(
        (1, 2), "#ff8800", 128 / 255, "solid", 1.0, "forward"
    )
    entry.runtime_data.set_zone_optimistic_state.assert_called_once()


async def test_automation_button_starts_native_sequence() -> None:
    scene = LumaForgeScene("scene", "Scene", (), {})
    automation = LumaForgeAutomation(
        "auto",
        "Timer",
        "scene",
        False,
        {},
        (LumaForgeAutomationStep("scene", "manual", None),),
    )
    entry = control_entry(
        LumaForgeData(INFO, STATUS, scenes=(scene,), automations=(automation,))
    )
    entity = LumaForgeAutomationButton(entry, automation.automation_id)

    assert entity.translation_placeholders == {"name": "Timer"}
    await entity.async_press()

    assert entity.unique_id.endswith("_auto_start")
    entry.runtime_data.client.async_start_automation.assert_awaited_once_with("auto")


async def test_automation_runtime_controls_and_status() -> None:
    scenes = (
        LumaForgeScene("one", "First scene", (), {}),
        LumaForgeScene("two", "Second scene", (), {}),
    )
    automation = LumaForgeAutomation(
        "auto",
        "Sequence",
        "one",
        True,
        {},
        (
            LumaForgeAutomationStep("one", "scene_finished", None),
            LumaForgeAutomationStep("two", "after_delay", 5),
        ),
    )
    entry = control_entry(
        LumaForgeData(SEQUENCE_INFO, STATUS, scenes=scenes, automations=(automation,))
    )
    entry.runtime_data.automation_state = LumaForgeAutomationState(
        "running", "auto", 1, "two", 2.5
    )
    stop = LumaForgeStopAutomationButton(entry)
    next_step = LumaForgeNextAutomationButton(entry)
    status = LumaForgeAutomationStatusSensor(entry)

    assert stop.available
    assert next_step.available
    assert status.native_value == "running"
    assert status.extra_state_attributes["automation_name"] == "Sequence"
    assert status.extra_state_attributes["scene_name"] == "Second scene"
    assert status.extra_state_attributes["step_number"] == 2
    assert status.extra_state_attributes["step_count"] == 2
    assert status.extra_state_attributes["duration_seconds"] == 5

    await stop.async_press()
    await next_step.async_press()
    entry.runtime_data.client.async_stop_automation.assert_awaited_once()
    entry.runtime_data.client.async_next_automation_step.assert_awaited_once()


async def test_dynamic_add_remove_without_duplicates(hass) -> None:
    """Repeated snapshots add once and remove deleted live entities."""
    known = {}
    added = []

    def factory(item_id):
        entity = MagicMock()
        entity.item_id = item_id
        entity.entity_id = None
        entity.async_remove = AsyncMock()
        return entity

    await async_sync_entities(hass, added.extend, known, ["one", "two"], factory)
    await async_sync_entities(hass, added.extend, known, ["one", "two"], factory)
    removed = known["one"]
    await async_sync_entities(hass, added.extend, known, ["two", "three"], factory)

    assert [entity.item_id for entity in added] == ["one", "two", "three"]
    removed.async_remove.assert_awaited_once()
