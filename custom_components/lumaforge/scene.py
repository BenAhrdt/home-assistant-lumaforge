"""Device-stored LumaForge scenes."""

from __future__ import annotations

from homeassistant.components.scene import Scene
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
    known: dict[str, LumaForgeSceneEntity] = {}

    async def sync() -> None:
        await async_sync_entities(
            hass,
            async_add_entities,
            known,
            (scene.scene_id for scene in entry.runtime_data.data.scenes),
            lambda scene_id: LumaForgeSceneEntity(entry, scene_id),
        )

    await sync()
    entry.async_on_unload(
        entry.runtime_data.async_add_listener(lambda: schedule_sync(hass, sync))
    )


class LumaForgeSceneEntity(LumaForgeEntity, Scene):
    """Represent a scene stored on LumaForge."""

    _attr_translation_key = "stored_scene"

    def __init__(self, entry: LumaForgeConfigEntry, scene_id: str) -> None:
        super().__init__(entry, f"scene_{scene_id}")
        self.scene_id = scene_id

    @property
    def translation_placeholders(self) -> dict[str, str]:
        scene = next(
            (
                item
                for item in self.coordinator.data.scenes
                if item.scene_id == self.scene_id
            ),
            None,
        )
        return {"name": scene.name if scene else self.scene_id}

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.client.websocket_connected

    async def async_activate(self, **kwargs: object) -> None:
        await self.coordinator.client.async_play_scene(self.scene_id)
