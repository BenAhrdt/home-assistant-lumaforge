"""Tests for API parsing."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientSession, web

from custom_components.lumaforge.api import (
    LumaForgeApiClient,
    LumaForgeCommandError,
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


async def test_existing_endpoints_and_status_parsing() -> None:
    """Use only the two documented endpoints and parse their current models."""
    client = LumaForgeApiClient(MagicMock(), "device.local", 80)
    client._get = AsyncMock(
        side_effect=[
            {
                "product": "LumaForge",
                "device_id": "lf-one",
                "api_version": 1,
                "capabilities": ["zones", 4, "scenes"],
            },
            {
                "wifi": "CONNECTED",
                "ip": "192.0.2.1",
                "rssi": "-61",
                "cpuPercent": "3.5",
                "memoryUsedBytes": "100",
                "memoryTotalBytes": 200,
            },
        ]
    )

    data = await client.async_get_data()

    assert [call.args[0] for call in client._get.await_args_list] == [
        "/api/v1/info",
        "/api/v1/status",
    ]
    assert data.info.capabilities == ("scenes", "zones")
    assert data.status.connected is True
    assert data.status.rssi == -61
    assert data.status.cpu_percent == 3.5
    assert data.status.memory_used_bytes == 100


async def test_older_firmware_without_capabilities() -> None:
    """Keep API v1 firmware without capabilities in diagnostics-only mode."""
    client = LumaForgeApiClient(MagicMock(), "device.local", 80)
    client._get = AsyncMock(
        return_value={"product": "LumaForge", "device_id": "lf-old", "api_version": 1}
    )

    info = await client.async_get_info()

    assert info.capabilities == ()


async def test_editor_endpoint_paths_and_models() -> None:
    """Use the confirmed unversioned editor endpoint paths."""
    client = LumaForgeApiClient(MagicMock(), "device.local", 80)
    client._request = AsyncMock(
        side_effect=[
            {"scenes": [{"id": "s1", "name": "One", "animations": []}]},
            [{"id": "z1", "name": "Zone", "leds": [2, 2, 3]}],
            [{"id": "a1", "name": "Timer", "sceneId": "s1", "enabled": True}],
            {"outputs": [{"id": "out", "startIndex": 2, "ledCount": 2}]},
        ]
    )

    scenes = await client.async_get_scenes()
    zones = await client.async_get_zones()
    automations = await client.async_get_automations()
    layout = await client.async_get_layout()

    assert [call.args[:2] for call in client._request.await_args_list] == [
        ("GET", "/api/scenes"),
        ("GET", "/api/zones"),
        ("GET", "/api/automations"),
        ("GET", "/api/layout"),
    ]
    assert scenes[0].scene_id == "s1"
    assert zones[0].leds == (2, 3)
    assert automations[0].scene_id == "s1"
    assert layout.valid_leds == {2, 3}
    assert layout.output_leds["out"] == {2, 3}


async def test_websocket_url_selection() -> None:
    """Use port 81 for ESP32 and the HTTP /ws path for the simulator."""
    client = LumaForgeApiClient(MagicMock(), "192.0.2.1", 8080)
    assert client.websocket_url == "ws://192.0.2.1:81/"
    client._get = AsyncMock(
        return_value={
            "product": "LumaForge",
            "device_id": "sim-one",
            "api_version": 1,
            "model": "LumaForge Simulator",
        }
    )
    await client.async_get_info()
    assert client.websocket_url == "ws://192.0.2.1:8080/ws"


@pytest.mark.parametrize(
    ("method", "payload", "accepted"),
    [
        (
            "async_play_scene",
            {"type": "scene.play", "sceneId": "s1"},
            "scene.play.accepted",
        ),
        ("async_stop_scene", {"type": "scene.stop"}, "scene.stop.accepted"),
    ],
)
async def test_websocket_scene_commands(
    method: str, payload: dict, accepted: str
) -> None:
    """Wait for the matching acknowledgement for scene commands."""
    client = LumaForgeApiClient(MagicMock(), "device.local", 80)
    client._ws = MagicMock()
    client._ws.send_json = AsyncMock()
    client._ws_connected.set()
    args = ("s1",) if method == "async_play_scene" else ()
    task = asyncio.create_task(getattr(client, method)(*args))
    await asyncio.sleep(0)
    client._ws.send_json.assert_awaited_once_with(payload)
    await client._handle_ws_message({"type": accepted})
    await task


async def test_preview_command_and_websocket_error() -> None:
    """Send preview.set and surface a firmware error."""
    client = LumaForgeApiClient(MagicMock(), "device.local", 80)
    client._ws = MagicMock()
    client._ws.send_json = AsyncMock()
    client._ws_connected.set()
    task = asyncio.create_task(
        client.async_set_preview([1, 2], "#5aa5e1", 0.8, "solid", 1.0, "forward")
    )
    await asyncio.sleep(0)
    client._ws.send_json.assert_awaited_once_with(
        {
            "type": "preview.set",
            "selection": [1, 2],
            "color": "#5aa5e1",
            "brightness": 0.8,
            "effect": "solid",
            "speed": 1.0,
            "direction": "forward",
        }
    )
    await client._handle_ws_message({"type": "error", "message": "bad selection"})
    with pytest.raises(LumaForgeCommandError, match="bad selection"):
        await task


async def test_websocket_hello_and_reconnect(monkeypatch) -> None:
    """Reconnect after a clean disconnect and require hello each time."""

    class Socket:
        async def receive_json(self):
            return {"type": "hello", "apiVersion": 1}

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

        async def close(self):
            return None

    session = MagicMock()
    session.ws_connect = AsyncMock(side_effect=[Socket(), Socket()])
    client = LumaForgeApiClient(session, "device.local", 80)
    connected = 0

    async def callback(event):
        nonlocal connected
        if event["type"] == "connected":
            connected += 1
            if connected == 2:
                client._closing = True

    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    await client.async_start_websocket(callback)
    assert client._ws_task is not None
    await client._ws_task

    assert session.ws_connect.await_count == 2
    assert connected == 2


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
