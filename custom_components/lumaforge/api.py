"""Asynchronous client for the local LumaForge HTTP API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Final

from aiohttp import ClientError, ClientSession

from .const import DEFAULT_TIMEOUT, PRODUCT, SUPPORTED_API_VERSIONS


class LumaForgeError(Exception):
    """Base exception for LumaForge API errors."""


class LumaForgeConnectionError(LumaForgeError):
    """The device could not be reached."""


class LumaForgeInvalidResponseError(LumaForgeError):
    """The device returned an invalid response."""


class LumaForgeIncompatibleApiError(LumaForgeError):
    """The device exposes an unsupported API version."""


@dataclass(frozen=True, slots=True)
class LumaForgeInfo:
    """Stable device identity and metadata."""

    device_id: str
    device_name: str
    model: str
    firmware_version: str | None
    api_version: int
    hostname: str | None
    connected: bool | None
    ip_address: str | None
    rssi: int | None
    capabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LumaForgeStatus:
    """Dynamic device status."""

    connected: bool | None
    ip_address: str | None
    rssi: int | None
    cpu_percent: float | None
    memory_used_bytes: int | None
    memory_total_bytes: int | None


@dataclass(frozen=True, slots=True)
class LumaForgeData:
    """Combined coordinator data."""

    info: LumaForgeInfo
    status: LumaForgeStatus


_JSON: Final = dict[str, Any]


def _optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class LumaForgeApiClient:
    """Small, read-only asynchronous LumaForge API client."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._session = session
        self.host = host
        self.port = port
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        """Return the device base URL, including IPv6 brackets when needed."""
        host = self.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{self.port}"

    async def _get(self, path: str) -> _JSON:
        try:
            async with asyncio.timeout(self._timeout):
                response = await self._session.get(f"{self.base_url}{path}")
                async with response:
                    if response.status != 200:
                        raise LumaForgeInvalidResponseError(
                            f"Unexpected HTTP status {response.status}"
                        )
                    payload = await response.json(content_type=None)
        except (TimeoutError, ClientError) as err:
            raise LumaForgeConnectionError("Unable to communicate with device") from err
        except (ValueError, TypeError) as err:
            raise LumaForgeInvalidResponseError("Response is not valid JSON") from err
        if not isinstance(payload, dict):
            raise LumaForgeInvalidResponseError("Response must be a JSON object")
        return payload

    async def async_get_info(self) -> LumaForgeInfo:
        """Fetch and validate the authoritative identity document."""
        payload = await self._get("/api/v1/info")
        if payload.get("product") != PRODUCT:
            raise LumaForgeInvalidResponseError("Unexpected product")
        device_id = _optional_str(payload.get("device_id"))
        if device_id is None:
            raise LumaForgeInvalidResponseError("Missing device_id")
        api_version = _optional_int(payload.get("api_version"))
        if api_version not in SUPPORTED_API_VERSIONS:
            raise LumaForgeIncompatibleApiError(
                f"Unsupported API version: {api_version!r}"
            )
        network = payload.get("network")
        network = network if isinstance(network, dict) else {}
        capabilities = payload.get("capabilities")
        return LumaForgeInfo(
            device_id=device_id,
            device_name=_optional_str(payload.get("device_name")) or device_id,
            model=_optional_str(payload.get("model")) or "Unknown",
            firmware_version=_optional_str(payload.get("firmware_version")),
            api_version=api_version,
            hostname=_optional_str(payload.get("hostname")),
            connected=(
                network.get("connected")
                if isinstance(network.get("connected"), bool)
                else None
            ),
            ip_address=_optional_str(network.get("ip")),
            rssi=_optional_int(network.get("rssi")),
            capabilities=tuple(
                sorted(item for item in capabilities if isinstance(item, str))
            )
            if isinstance(capabilities, list)
            else (),
        )

    async def async_get_status(self) -> LumaForgeStatus:
        """Fetch dynamic status data."""
        payload = await self._get("/api/v1/status")
        wifi = _optional_str(payload.get("wifi"))
        return LumaForgeStatus(
            connected=wifi.lower() == "connected" if wifi is not None else None,
            ip_address=_optional_str(payload.get("ip")),
            rssi=_optional_int(payload.get("rssi")),
            cpu_percent=_optional_float(payload.get("cpuPercent")),
            memory_used_bytes=_optional_int(payload.get("memoryUsedBytes")),
            memory_total_bytes=_optional_int(payload.get("memoryTotalBytes")),
        )

    async def async_get_data(self) -> LumaForgeData:
        """Fetch all data needed by the integration."""
        info = await self.async_get_info()
        status = await self.async_get_status()
        return LumaForgeData(info=info, status=status)
