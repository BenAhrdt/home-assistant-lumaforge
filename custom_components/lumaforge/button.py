"""Buttons for scene stop and device-internal automations."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
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

    async def sync() -> None:
        wanted = [
            f"automation:{item.automation_id}"
            for item in entry.runtime_data.data.automations
        ]
        if entry.runtime_data.data.scenes:
            wanted.append("scene_stop")

        def factory(item_id: str) -> ButtonEntity:
            if item_id == "scene_stop":
                return LumaForgeStopSceneButton(entry)
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
        super().__init__(entry, f"automation_{automation_id}_run")
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
        return f"{self.automation.name if self.automation else self.automation_id} run"

    async def async_press(self) -> None:
        automation = self.automation
        if automation is None or automation.scene_id is None:
            raise ValueError(f"Automation {self.automation_id} has no valid scene")
        if not any(
            scene.scene_id == automation.scene_id
            for scene in self.coordinator.data.scenes
        ):
            raise ValueError(f"Unknown scene: {automation.scene_id}")
        await self.coordinator.client.async_play_scene(automation.scene_id)
