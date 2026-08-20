"""Config flow for LumaForge."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import (
    LumaForgeApiClient,
    LumaForgeConnectionError,
    LumaForgeIncompatibleApiError,
    LumaForgeInfo,
    LumaForgeInvalidResponseError,
)
from .const import CONF_PORT, DEFAULT_PORT, DOMAIN


def _txt_value(properties: dict[str | bytes, str | bytes], key: str) -> str | None:
    """Read a TXT value defensively from byte or string mappings."""
    value = properties.get(key)
    if value is None:
        value = properties.get(key.encode())
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip() or None
    if isinstance(value, str):
        return value.strip() or None
    return None


class LumaForgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a LumaForge config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] = {}
        self._info: LumaForgeInfo | None = None

    async def _async_verify(self, host: str, port: int) -> LumaForgeInfo:
        client = LumaForgeApiClient(async_get_clientsession(self.hass), host, port)
        return await client.async_get_info()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""
        host = str(discovery_info.ip_address)
        port = discovery_info.port or DEFAULT_PORT
        txt_id = _txt_value(discovery_info.properties, "id")
        try:
            info = await self._async_verify(host, port)
        except LumaForgeIncompatibleApiError:
            return self.async_abort(reason="unsupported_api")
        except LumaForgeConnectionError:
            return self.async_abort(reason="cannot_connect")
        except LumaForgeInvalidResponseError:
            return self.async_abort(reason="invalid_response")
        if txt_id is not None and txt_id != info.device_id:
            return self.async_abort(reason="id_mismatch")

        await self.async_set_unique_id(info.device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
        self._discovered = {CONF_HOST: host, CONF_PORT: port}
        self._info = info
        self.context["title_placeholders"] = {"name": info.device_name}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered device."""
        if user_input is not None:
            assert self._info is not None
            return self.async_create_entry(
                title=self._info.device_name, data=self._discovered
            )
        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Explain that setup is handled automatically through discovery."""
        return self.async_abort(reason="discovery_only")
