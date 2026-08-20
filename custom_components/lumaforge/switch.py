"""Enable switches for device-internal automations."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
    known: dict[str, LumaForgeAutomationSwitch] = {}
    registry = er.async_get(hass)
    for automation in entry.runtime_data.data.automations:
        old_entity_id = registry.async_get_entity_id(
            "switch",
            "lumaforge",
            f"{entry.unique_id}_automation_{automation.automation_id}_enabled",
        )
        if old_entity_id is not None:
            registry.async_remove(old_entity_id)

    async def sync() -> None:
        await async_sync_entities(
            hass,
            async_add_entities,
            known,
            (
                item.automation_id
                for item in entry.runtime_data.data.automations
                if item.enabled is not None
            ),
            lambda automation_id: LumaForgeAutomationSwitch(entry, automation_id),
        )

    await sync()
    entry.async_on_unload(
        entry.runtime_data.async_add_listener(lambda: schedule_sync(hass, sync))
    )


class LumaForgeAutomationSwitch(LumaForgeEntity, SwitchEntity):
    """Persist an automation's enabled field through the full-list endpoint."""

    def __init__(self, entry: LumaForgeConfigEntry, automation_id: str) -> None:
        super().__init__(entry, f"{automation_id}_enabled")
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
        name = self.automation.name if self.automation else self.automation_id
        return f"{name} enabled"

    @property
    def is_on(self) -> bool | None:
        return self.automation.enabled if self.automation else None

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.coordinator.async_set_automation_enabled(self.automation_id, True)

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.coordinator.async_set_automation_enabled(self.automation_id, False)
