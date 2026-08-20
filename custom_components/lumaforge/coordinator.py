"""Data coordinator for LumaForge."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LumaForgeApiClient, LumaForgeData, LumaForgeError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class LumaForgeCoordinator(DataUpdateCoordinator[LumaForgeData]):
    """Poll a LumaForge device."""

    def __init__(self, hass: HomeAssistant, client: LumaForgeApiClient) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> LumaForgeData:
        try:
            return await self.client.async_get_data()
        except LumaForgeError as err:
            raise UpdateFailed(str(err)) from err
