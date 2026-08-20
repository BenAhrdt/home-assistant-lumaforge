"""Tests for API parsing."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientSession, web

from custom_components.lumaforge.api import (
    LumaForgeApiClient,
    LumaForgeConnectionError,
    LumaForgeIncompatibleApiError,
    LumaForgeInvalidResponseError,
)


@pytest.mark.parametrize(
    ("change", "exception"),
    [
        ({"product": "Other"}, LumaForgeInvalidResponseError),
        ({"api_version": 2}, LumaForgeIncompatibleApiError),
        ({"device_id": ""}, LumaForgeInvalidResponseError),
    ],
)
async def test_info_validation(change: dict, exception: type[Exception]) -> None:
    """Reject invalid authoritative identity data."""
    payload = {"product": "LumaForge", "device_id": "lf-one", "api_version": 1}
    payload.update(change)
    client = LumaForgeApiClient(MagicMock(), "device.local", 80)
    client._get = AsyncMock(return_value=payload)
    with pytest.raises(exception):
        await client.async_get_info()


async def test_ipv6_url_and_optional_values() -> None:
    """Bracket IPv6 and accept missing optional fields."""
    client = LumaForgeApiClient(MagicMock(), "fe80::1", 80)
    assert client.base_url == "http://[fe80::1]:80"
    client._get = AsyncMock(
        return_value={"product": "LumaForge", "device_id": "lf-one", "api_version": "1"}
    )
    info = await client.async_get_info()
    assert info.device_name == "lf-one"
    assert info.rssi is None


async def test_invalid_json(aiohttp_server, socket_enabled) -> None:
    """Invalid JSON is reported as an invalid response."""

    async def invalid_response(request):
        return web.Response(text="not-json")

    app = web.Application()
    app.router.add_get("/api/v1/info", invalid_response)
    server = await aiohttp_server(app)
    async with ClientSession() as session:
        client = LumaForgeApiClient(session, server.host, server.port)
        with pytest.raises(LumaForgeInvalidResponseError):
            await client.async_get_info()


async def test_timeout(aiohttp_server, socket_enabled) -> None:
    """A request timeout is reported as a connection error."""

    async def slow_response(request):
        await asyncio.sleep(0.1)
        return web.json_response({})

    app = web.Application()
    app.router.add_get("/api/v1/info", slow_response)
    server = await aiohttp_server(app)
    async with ClientSession() as session:
        client = LumaForgeApiClient(session, server.host, server.port, timeout=0.01)
        with pytest.raises(LumaForgeConnectionError):
            await client.async_get_info()
