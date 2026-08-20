"""Helpers for dynamic LumaForge entity collections."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


async def async_remove_entity(hass: HomeAssistant, entity: Entity) -> None:
    """Remove a live entity and its registry entry."""
    entity_id = entity.entity_id
    await entity.async_remove()
    if entity_id is not None:
        registry = er.async_get(hass)
        if registry.async_get(entity_id) is not None:
            registry.async_remove(entity_id)


async def async_sync_entities(
    hass: HomeAssistant,
    async_add_entities: AddConfigEntryEntitiesCallback,
    known: dict[str, Entity],
    wanted: Iterable[str],
    factory: Callable[[str], Entity],
) -> None:
    """Add new objects once and fully remove objects deleted on the device."""
    wanted_ids = set(wanted)
    new_ids = wanted_ids - known.keys()
    if new_ids:
        entities = [factory(item_id) for item_id in sorted(new_ids)]
        known.update(zip(sorted(new_ids), entities, strict=True))
        async_add_entities(entities)
    for item_id in set(known) - wanted_ids:
        entity = known.pop(item_id)
        await async_remove_entity(hass, entity)


def schedule_sync(hass: HomeAssistant, sync: Callable[[], Any]) -> None:
    """Schedule reconciliation from a coordinator listener."""
    hass.async_create_task(sync())
