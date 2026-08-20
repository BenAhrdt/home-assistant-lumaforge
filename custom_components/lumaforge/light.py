"""Zone lights for LumaForge."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LumaForgeConfigEntry
from .const import DIRECTIONS, EFFECTS
from .dynamic import async_sync_entities, schedule_sync
from .entity import LumaForgeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LumaForgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    known: dict[str, LumaForgeZoneLight] = {}

    async def sync() -> None:
        await async_sync_entities(
            hass,
            async_add_entities,
            known,
            (zone.zone_id for zone in entry.runtime_data.data.zones),
            lambda zone_id: LumaForgeZoneLight(entry, zone_id),
        )

    await sync()
    entry.async_on_unload(
        entry.runtime_data.async_add_listener(lambda: schedule_sync(hass, sync))
    )


class LumaForgeZoneLight(LumaForgeEntity, LightEntity):
    """A zone using in-memory optimistic state after acknowledged commands."""

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = list(EFFECTS)

    def __init__(self, entry: LumaForgeConfigEntry, zone_id: str) -> None:
        super().__init__(entry, f"zone_{zone_id}")
        self.zone_id = zone_id
        self._speed = 1.0
        self._direction = DIRECTIONS[0]

    @property
    def optimistic_state(self) -> dict[str, Any] | None:
        return self.coordinator.zone_states.get(self.zone_id)

    @property
    def is_on(self) -> bool | None:
        return self.optimistic_state.get("on") if self.optimistic_state else None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self.optimistic_state.get("rgb") if self.optimistic_state else None

    @property
    def brightness(self) -> int | None:
        if self.optimistic_state:
            return self.optimistic_state.get("brightness")
        return None

    @property
    def effect(self) -> str | None:
        return self.optimistic_state.get("effect") if self.optimistic_state else None

    @property
    def zone(self):
        return next(
            (
                item
                for item in self.coordinator.data.zones
                if item.zone_id == self.zone_id
            ),
            None,
        )

    @property
    def name(self) -> str:
        return self.zone.name if self.zone else self.zone_id

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.client.websocket_connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.optimistic_state or {}
        return {
            "optimistic_state": self.optimistic_state is not None,
            "effect_speed": state.get("speed", self._speed),
            "effect_direction": state.get("direction", self._direction),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        zone = self.zone
        if zone is None or not zone.leds:
            raise ValueError(f"Unknown or empty zone: {self.zone_id}")
        rgb = kwargs.get(ATTR_RGB_COLOR, self.rgb_color or (255, 255, 255))
        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
        effect = kwargs.get(ATTR_EFFECT, self.effect or EFFECTS[0])
        await self.coordinator.client.async_set_preview(
            zone.leds,
            f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}",
            brightness / 255,
            effect,
            self._speed,
            self._direction,
        )
        self.coordinator.set_zone_optimistic_state(
            self.zone_id,
            {
                "on": True,
                "rgb": rgb,
                "brightness": brightness,
                "effect": effect,
                "speed": self._speed,
                "direction": self._direction,
            },
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        zone = self.zone
        if zone is None or not zone.leds:
            raise ValueError(f"Unknown or empty zone: {self.zone_id}")
        rgb = self.rgb_color or (255, 255, 255)
        await self.coordinator.client.async_set_preview(
            zone.leds,
            f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}",
            0.0,
            self.effect or EFFECTS[0],
            self._speed,
            self._direction,
        )
        state = dict(self.optimistic_state or {})
        state["on"] = False
        self.coordinator.set_zone_optimistic_state(self.zone_id, state)
