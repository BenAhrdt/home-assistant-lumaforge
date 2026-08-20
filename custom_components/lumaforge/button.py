"""Buttons for scene stop and device-internal automations."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LumaForgeConfigEntry
from .dynamic import async_sync_entities, schedule_sync
from .entity import LumaForgeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LumaForgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    known: dict[str, ButtonEntity] = {}

    registry = er.async_get(hass)
    for automation in entry.runtime_data.data.automations:
        old_entity_id = registry.async_get_entity_id(
            "button",
            "lumaforge",
            f"{entry.unique_id}_automation_{automation.automation_id}_run",
        )
        if old_entity_id is not None:
            registry.async_remove(old_entity_id)

    async def sync() -> None:
        wanted = []
        if entry.runtime_data.supports_automation_sequences:
            wanted.extend(
                f"automation:{item.automation_id}"
                for item in entry.runtime_data.data.automations
            )
            wanted.extend(("automation_stop", "automation_next"))
        if entry.runtime_data.data.scenes:
            wanted.append("scene_stop")

        def factory(item_id: str) -> ButtonEntity:
            if item_id == "scene_stop":
                return LumaForgeStopSceneButton(entry)
            if item_id == "automation_stop":
                return LumaForgeStopAutomationButton(entry)
            if item_id == "automation_next":
                return LumaForgeNextAutomationButton(entry)
            return LumaForgeAutomationButton(entry, item_id.removeprefix("automation:"))

        await async_sync_entities(hass, async_add_entities, known, wanted, factory)

    await sync()
    entry.async_on_unload(
        entry.runtime_data.async_add_listener(lambda: schedule_sync(hass, sync))
    )


class LumaForgeControlButton(LumaForgeEntity, ButtonEntity):
    @property
    def available(self) -> bool:
        return super().available and self.coordinator.client.websocket_connected


class LumaForgeStopSceneButton(LumaForgeControlButton):
    _attr_translation_key = "stop_scene"

    def __init__(self, entry: LumaForgeConfigEntry) -> None:
        super().__init__(entry, "stop_scene")

    async def async_press(self) -> None:
        await self.coordinator.client.async_stop_scene()


class LumaForgeAutomationButton(LumaForgeControlButton):
    def __init__(self, entry: LumaForgeConfigEntry, automation_id: str) -> None:
        super().__init__(entry, f"{automation_id}_start")
        self.automation_id = automation_id

    @property
    def automation(self):
        return next(
            (
                item
                for item in self.coordinator.data.automations
                if item.automation_id == self.automation_id
            ),
            None,
        )

    @property
    def name(self) -> str:
        return (
            f"{self.automation.name if self.automation else self.automation_id} start"
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        state = self.coordinator.automation_state
        running = bool(
            state
            and state.state == "running"
            and state.automation_id == self.automation_id
        )
        return {
            "running": running,
            "current_step": state.step_index if running else None,
            "current_scene": state.scene_id if running else None,
        }

    async def async_press(self) -> None:
        automation = self.automation
        if automation is None:
            raise ValueError(f"Unknown automation: {self.automation_id}")
        await self.coordinator.client.async_start_automation(self.automation_id)


class LumaForgeAutomationRuntimeButton(LumaForgeControlButton):
    """Base button that is useful only while a sequence is active."""

    @property
    def available(self) -> bool:
        state = self.coordinator.automation_state
        return bool(super().available and state and state.state == "running")


class LumaForgeStopAutomationButton(LumaForgeAutomationRuntimeButton):
    _attr_translation_key = "stop_automation"

    def __init__(self, entry: LumaForgeConfigEntry) -> None:
        super().__init__(entry, "automation_stop")

    async def async_press(self) -> None:
        await self.coordinator.client.async_stop_automation()


class LumaForgeNextAutomationButton(LumaForgeAutomationRuntimeButton):
    _attr_translation_key = "next_automation_step"

    def __init__(self, entry: LumaForgeConfigEntry) -> None:
        super().__init__(entry, "automation_next")

    async def async_press(self) -> None:
        await self.coordinator.client.async_next_automation_step()
