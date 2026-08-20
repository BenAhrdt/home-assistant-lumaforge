"""Asynchronous client for the local LumaForge REST and WebSocket APIs."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from aiohttp import ClientError, ClientSession, ClientWebSocketResponse, WSMsgType

from .const import DEFAULT_TIMEOUT, PRODUCT, SUPPORTED_API_VERSIONS


class LumaForgeError(Exception):
    """Base API error."""


class LumaForgeConnectionError(LumaForgeError):
    """The device could not be reached."""


class LumaForgeInvalidResponseError(LumaForgeError):
    """The device returned an invalid response."""


class LumaForgeIncompatibleApiError(LumaForgeError):
    """The device exposes an unsupported API version."""


class LumaForgeUnsupportedError(LumaForgeError):
    """An optional endpoint is unavailable."""


class LumaForgeCommandError(LumaForgeError):
    """The device rejected a command."""


@dataclass(frozen=True, slots=True)
class LumaForgeInfo:
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
    connected: bool | None
    ip_address: str | None
    rssi: int | None
    cpu_percent: float | None
    memory_used_bytes: int | None
    memory_total_bytes: int | None


@dataclass(frozen=True, slots=True)
class LumaForgeScene:
    scene_id: str
    name: str
    animations: tuple[dict[str, Any], ...]
    raw: dict[str, Any] = field(compare=False)


@dataclass(frozen=True, slots=True)
class LumaForgeZone:
    zone_id: str
    name: str
    leds: tuple[int, ...]
    raw: dict[str, Any] = field(compare=False)


@dataclass(frozen=True, slots=True)
class LumaForgeAutomation:
    automation_id: str
    name: str
    scene_id: str | None
    enabled: bool | None
    raw: dict[str, Any] = field(compare=False)


@dataclass(frozen=True, slots=True)
class LumaForgeLayout:
    raw: Any = field(compare=False)
    valid_leds: frozenset[int]
    output_leds: dict[str, frozenset[int]] = field(compare=False)


@dataclass(frozen=True, slots=True)
class LumaForgeData:
    info: LumaForgeInfo
    status: LumaForgeStatus
    layout: LumaForgeLayout | None = None
    zones: tuple[LumaForgeZone, ...] = ()
    scenes: tuple[LumaForgeScene, ...] = ()
    automations: tuple[LumaForgeAutomation, ...] = ()


JsonObject = dict[str, Any]
EventCallback = Callable[[JsonObject], Awaitable[None]]


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


def _object_list(payload: Any, key: str) -> list[JsonObject]:
    value = payload.get(key) if isinstance(payload, dict) else payload
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise LumaForgeInvalidResponseError(f"{key} response must be an object array")
    return value


def _stable_id(item: JsonObject, kind: str) -> str:
    value = _optional_str(item.get("id"))
    if value is None:
        raise LumaForgeInvalidResponseError(f"{kind} is missing a stable id")
    return value


def parse_scenes(payload: Any) -> tuple[LumaForgeScene, ...]:
    result = []
    for item in _object_list(payload, "scenes"):
        item_id = _stable_id(item, "scene")
        animations = item.get("animations", [])
        if not isinstance(animations, list) or not all(
            isinstance(value, dict) for value in animations
        ):
            raise LumaForgeInvalidResponseError("scene animations must be objects")
        result.append(
            LumaForgeScene(
                item_id,
                _optional_str(item.get("name")) or item_id,
                tuple(animations),
                dict(item),
            )
        )
    return tuple(result)


def parse_zones(payload: Any) -> tuple[LumaForgeZone, ...]:
    result = []
    for item in _object_list(payload, "zones"):
        item_id = _stable_id(item, "zone")
        raw_leds = item.get("leds", [])
        if not isinstance(raw_leds, list):
            raise LumaForgeInvalidResponseError("zone leds must be an array")
        leds: list[int] = []
        for raw_led in raw_leds:
            led = _optional_int(raw_led)
            if led is None or led < 0:
                raise LumaForgeInvalidResponseError("zone LED index is invalid")
            if led not in leds:
                leds.append(led)
        result.append(
            LumaForgeZone(
                item_id,
                _optional_str(item.get("name")) or item_id,
                tuple(leds),
                dict(item),
            )
        )
    return tuple(result)


def parse_automations(payload: Any) -> tuple[LumaForgeAutomation, ...]:
    result = []
    for item in _object_list(payload, "automations"):
        item_id = _stable_id(item, "automation")
        enabled = item.get("enabled")
        result.append(
            LumaForgeAutomation(
                item_id,
                _optional_str(item.get("name")) or item_id,
                _optional_str(item.get("sceneId")),
                enabled if isinstance(enabled, bool) else None,
                dict(item),
            )
        )
    return tuple(result)


def _walk_layout(value: Any) -> Iterable[JsonObject]:
    if isinstance(value, list):
        for item in value:
            yield from _walk_layout(item)
    elif isinstance(value, dict):
        if any(key in value for key in ("ledCount", "led_count", "count")):
            yield value
        for key in ("outputs", "sections", "strips", "layout"):
            if key in value:
                yield from _walk_layout(value[key])


def parse_layout(payload: Any) -> LumaForgeLayout:
    valid: set[int] = set()
    outputs: dict[str, set[int]] = {}
    for item in _walk_layout(payload):
        count = _optional_int(
            item.get("ledCount", item.get("led_count", item.get("count")))
        )
        start = _optional_int(item.get("startIndex", item.get("start", 0)))
        if count is None or count < 0 or start is None or start < 0:
            raise LumaForgeInvalidResponseError("layout LED bounds are invalid")
        indices = set(range(start, start + count))
        valid.update(indices)
        output_id = _optional_str(item.get("outputId")) or _optional_str(item.get("id"))
        if output_id is not None:
            outputs.setdefault(output_id, set()).update(indices)
    return LumaForgeLayout(
        payload,
        frozenset(valid),
        {key: frozenset(value) for key, value in outputs.items()},
    )


class LumaForgeApiClient:
    """Central asynchronous REST and WebSocket client."""

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
        self._simulator = False
        self.supported_resources: set[str] = set()
        self._ws: ClientWebSocketResponse | None = None
        self._ws_task: asyncio.Task[None] | None = None
        self._ws_connected = asyncio.Event()
        self._closing = False
        self._event_callback: EventCallback | None = None
        self._command_lock = asyncio.Lock()
        self._pending_ack: tuple[str, asyncio.Future[None]] | None = None

    @property
    def base_url(self) -> str:
        host = self.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{self.port}"

    @property
    def websocket_url(self) -> str:
        host = self.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"ws://{host}:{self.port}/ws" if self._simulator else f"ws://{host}:81/"

    @property
    def websocket_connected(self) -> bool:
        return self._ws_connected.is_set()

    async def _request(self, method: str, path: str, *, json_data: Any = None) -> Any:
        try:
            async with asyncio.timeout(self._timeout):
                response = await self._session.request(
                    method, f"{self.base_url}{path}", json=json_data
                )
                async with response:
                    if response.status == 404:
                        raise LumaForgeUnsupportedError(
                            f"Endpoint {path} is unsupported"
                        )
                    if not 200 <= response.status < 300:
                        raise LumaForgeInvalidResponseError(
                            f"Unexpected HTTP status {response.status} for {path}"
                        )
                    if response.status == 204:
                        return None
                    return await response.json(content_type=None)
        except (TimeoutError, ClientError) as err:
            raise LumaForgeConnectionError("Unable to communicate with device") from err
        except (ValueError, TypeError) as err:
            raise LumaForgeInvalidResponseError("Response is not valid JSON") from err

    async def _get(self, path: str) -> JsonObject:
        payload = await self._request("GET", path)
        if not isinstance(payload, dict):
            raise LumaForgeInvalidResponseError("Response must be a JSON object")
        return payload

    async def async_get_info(self) -> LumaForgeInfo:
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
        model = _optional_str(payload.get("model")) or "Unknown"
        variant = _optional_str(payload.get("server_variant"))
        self._simulator = bool(
            payload.get("simulator") is True
            or (variant and variant.lower() == "simulator")
            or "simulator" in model.lower()
        )
        network = payload.get("network")
        network = network if isinstance(network, dict) else {}
        capabilities = payload.get("capabilities")
        return LumaForgeInfo(
            device_id,
            _optional_str(payload.get("device_name")) or device_id,
            model,
            _optional_str(payload.get("firmware_version")),
            api_version,
            _optional_str(payload.get("hostname")),
            (
                network.get("connected")
                if isinstance(network.get("connected"), bool)
                else None
            ),
            _optional_str(network.get("ip")),
            _optional_int(network.get("rssi")),
            tuple(sorted(value for value in capabilities if isinstance(value, str)))
            if isinstance(capabilities, list)
            else (),
        )

    async def async_get_status(self) -> LumaForgeStatus:
        payload = await self._get("/api/v1/status")
        wifi = _optional_str(payload.get("wifi"))
        return LumaForgeStatus(
            wifi.lower() == "connected" if wifi is not None else None,
            _optional_str(payload.get("ip")),
            _optional_int(payload.get("rssi")),
            _optional_float(payload.get("cpuPercent")),
            _optional_int(payload.get("memoryUsedBytes")),
            _optional_int(payload.get("memoryTotalBytes")),
        )

    async def async_get_device(self) -> JsonObject:
        return await self._get("/api/v1/device")

    async def async_set_device_name(self, name: str) -> JsonObject:
        payload = await self._request(
            "PUT", "/api/v1/device", json_data={"device_name": name}
        )
        if not isinstance(payload, dict):
            raise LumaForgeInvalidResponseError("device response must be an object")
        return payload

    async def async_get_project(self) -> JsonObject:
        return await self._get("/api/project")

    async def async_get_layout(self) -> LumaForgeLayout:
        return parse_layout(await self._request("GET", "/api/layout"))

    async def async_get_zones(self) -> tuple[LumaForgeZone, ...]:
        return parse_zones(await self._request("GET", "/api/zones"))

    async def async_get_scenes(self) -> tuple[LumaForgeScene, ...]:
        return parse_scenes(await self._request("GET", "/api/scenes"))

    async def async_get_automations(self) -> tuple[LumaForgeAutomation, ...]:
        return parse_automations(await self._request("GET", "/api/automations"))

    async def async_put_automations(
        self, automations: Iterable[dict[str, Any]]
    ) -> tuple[LumaForgeAutomation, ...]:
        await self._request("PUT", "/api/automations", json_data=list(automations))
        return await self.async_get_automations()

    async def async_get_data(self) -> LumaForgeData:
        info = await self.async_get_info()
        status = await self.async_get_status()
        values: list[Any] = []
        self.supported_resources.clear()
        for name, getter in (
            ("layout", self.async_get_layout),
            ("zones", self.async_get_zones),
            ("scenes", self.async_get_scenes),
            ("automations", self.async_get_automations),
        ):
            try:
                values.append(await getter())
                self.supported_resources.add(name)
            except LumaForgeUnsupportedError:
                values.append(None)
        layout, zones, scenes, automations = values
        return LumaForgeData(
            info, status, layout, zones or (), scenes or (), automations or ()
        )

    async def async_start_websocket(self, callback: EventCallback) -> None:
        self._event_callback = callback
        self._closing = False
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = asyncio.create_task(
                self._websocket_loop(), name="lumaforge-websocket"
            )

    async def async_close(self) -> None:
        self._closing = True
        self._ws_connected.clear()
        if self._ws is not None:
            await self._ws.close()
        if self._ws_task is not None:
            self._ws_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._ws_task
            self._ws_task = None
        self._fail_pending(LumaForgeConnectionError("WebSocket closed"))

    async def _websocket_loop(self) -> None:
        delay = 1
        while not self._closing:
            try:
                async with asyncio.timeout(self._timeout):
                    self._ws = await self._session.ws_connect(self.websocket_url)
                    hello = await self._ws.receive_json()
                if not isinstance(hello, dict) or hello.get("type") != "hello":
                    raise LumaForgeInvalidResponseError("Missing WebSocket hello")
                if _optional_int(hello.get("apiVersion")) not in SUPPORTED_API_VERSIONS:
                    raise LumaForgeIncompatibleApiError(
                        "Unsupported WebSocket API version"
                    )
                self._ws_connected.set()
                delay = 1
                if self._event_callback:
                    await self._event_callback({"type": "connected"})
                async for message in self._ws:
                    if message.type == WSMsgType.TEXT:
                        await self._handle_ws_message(message.json())
                    elif message.type in (WSMsgType.ERROR, WSMsgType.CLOSED):
                        break
            except asyncio.CancelledError:
                raise
            except (TimeoutError, ClientError, ValueError, LumaForgeError):
                pass
            finally:
                self._ws_connected.clear()
                self._fail_pending(LumaForgeConnectionError("WebSocket disconnected"))
                self._ws = None
                if self._event_callback:
                    await self._event_callback({"type": "disconnected"})
            if not self._closing:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def _handle_ws_message(self, payload: Any) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
            return
        message_type = payload["type"]
        pending = self._pending_ack
        if message_type == "error" and pending:
            self._fail_pending(
                LumaForgeCommandError(
                    _optional_str(payload.get("message")) or "Command failed"
                )
            )
        elif pending and message_type == f"{pending[0]}.accepted":
            if not pending[1].done():
                pending[1].set_result(None)
            self._pending_ack = None
        elif self._event_callback:
            await self._event_callback(payload)

    def _fail_pending(self, error: LumaForgeError) -> None:
        if self._pending_ack:
            future = self._pending_ack[1]
            if not future.done():
                future.set_exception(error)
            self._pending_ack = None

    async def _send_command(self, payload: JsonObject) -> None:
        command = payload["type"]
        async with self._command_lock:
            try:
                async with asyncio.timeout(self._timeout):
                    await self._ws_connected.wait()
                    if self._ws is None:
                        raise LumaForgeConnectionError("WebSocket is unavailable")
                    future = asyncio.get_running_loop().create_future()
                    self._pending_ack = (command, future)
                    await self._ws.send_json(payload)
                    await future
            except TimeoutError as err:
                self._pending_ack = None
                raise LumaForgeConnectionError("WebSocket command timed out") from err
            except ClientError as err:
                self._pending_ack = None
                raise LumaForgeConnectionError(
                    "Unable to send WebSocket command"
                ) from err

    async def async_play_scene(self, scene_id: str) -> None:
        await self._send_command({"type": "scene.play", "sceneId": scene_id})

    async def async_stop_scene(self) -> None:
        await self._send_command({"type": "scene.stop"})

    async def async_set_preview(
        self,
        selection: Iterable[int],
        color: str,
        brightness: float,
        effect: str,
        speed: float,
        direction: str,
    ) -> None:
        await self._send_command(
            {
                "type": "preview.set",
                "selection": list(selection),
                "color": color,
                "brightness": brightness,
                "effect": effect,
                "speed": speed,
                "direction": direction,
            }
        )

    async def async_cancel_preview(self) -> None:
        await self._send_command({"type": "preview.cancel"})

    async def async_apply_preview(self) -> None:
        await self._send_command({"type": "preview.apply"})
