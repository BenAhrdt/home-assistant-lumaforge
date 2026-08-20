"""The LumaForge integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LumaForgeApiClient
from .const import CONF_PORT, DEFAULT_PORT, PLATFORMS
from .coordinator import LumaForgeCoordinator

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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LumaForgeConfigEntry) -> bool:
    """Unload a LumaForge config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
