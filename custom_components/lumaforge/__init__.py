"""The LumaForge integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LumaForgeApiClient
from .const import CONF_PORT, DATA_COORDINATORS, DEFAULT_PORT, DOMAIN
from .coordinator import LumaForgeCoordinator
from .services import async_setup_services, async_unload_services

type LumaForgeConfigEntry = ConfigEntry[LumaForgeCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LumaForgeConfigEntry) -> bool:
    """Set up LumaForge from a config entry."""
    client = LumaForgeApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
    )
    coordinator = LumaForgeCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    domain_data = hass.data.setdefault(DOMAIN, {})
    coordinators = domain_data.setdefault(DATA_COORDINATORS, {})
    coordinators[entry.entry_id] = coordinator
    await async_setup_services(hass)
    coordinator.loaded_platforms = coordinator.platforms
    await hass.config_entries.async_forward_entry_setups(
        entry, coordinator.loaded_platforms
    )
    if coordinator.supports_automation_sequences or client.supported_resources & {
        "scenes",
        "zones",
        "automations",
    }:
        await coordinator.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LumaForgeConfigEntry) -> bool:
    """Unload a LumaForge config entry."""
    if not await hass.config_entries.async_unload_platforms(
        entry, entry.runtime_data.loaded_platforms
    ):
        return False
    await entry.runtime_data.async_shutdown()
    coordinators = hass.data[DOMAIN][DATA_COORDINATORS]
    coordinators.pop(entry.entry_id, None)
    if not coordinators:
        async_unload_services(hass)
        hass.data.pop(DOMAIN)
    return True
