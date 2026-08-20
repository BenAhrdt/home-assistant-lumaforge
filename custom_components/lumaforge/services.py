"""Home Assistant services for targeted LumaForge LED control."""

from __future__ import annotations

from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError

from .api import LumaForgeError
from .const import DATA_COORDINATORS, DIRECTIONS, DOMAIN, EFFECTS
from .coordinator import LumaForgeCoordinator

TARGET_SCHEMA = {
    vol.Optional("config_entry_id"): cv.string,
    vol.Optional("device_id"): cv.string,
    vol.Optional("output_id"): cv.string,
}
CONTROL_SCHEMA = {
    vol.Required("color"): vol.Any(
        vol.Match(r"^#[0-9a-fA-F]{6}$"),
        [vol.All(vol.Coerce(int), vol.Range(min=0, max=255))],
    ),
    vol.Optional("brightness", default=1.0): vol.All(
        vol.Coerce(float), vol.Range(min=0.0, max=1.0)
    ),
    vol.Optional("effect", default=EFFECTS[0]): vol.In(EFFECTS),
    vol.Optional("speed", default=1.0): vol.All(
        vol.Coerce(float), vol.Range(min=0.0, max=1.0)
    ),
    vol.Optional("direction", default=DIRECTIONS[0]): vol.In(DIRECTIONS),
}
SET_LED_SCHEMA = vol.Schema(
    {**TARGET_SCHEMA, **CONTROL_SCHEMA, vol.Required("led_index"): cv.positive_int}
)
SET_LED_RANGE_SCHEMA = vol.Schema(
    {
        **TARGET_SCHEMA,
        **CONTROL_SCHEMA,
        vol.Required("start_index"): cv.positive_int,
        vol.Required("end_index"): cv.positive_int,
    }
)
APPLY_ZONE_SCHEMA = vol.Schema(
    {**TARGET_SCHEMA, **CONTROL_SCHEMA, vol.Required("zone_id"): cv.string}
)
AUTOMATION_TARGET_SCHEMA = {
    vol.Optional("config_entry_id"): cv.string,
    vol.Optional("device_id"): cv.string,
}
START_AUTOMATION_SCHEMA = vol.Schema(
    {**AUTOMATION_TARGET_SCHEMA, vol.Required("automation_id"): cv.string}
)
AUTOMATION_COMMAND_SCHEMA = vol.Schema(AUTOMATION_TARGET_SCHEMA)


def _coordinator(hass: HomeAssistant, data: dict[str, Any]) -> LumaForgeCoordinator:
    coordinators: dict[str, LumaForgeCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    entry_id = data.get("config_entry_id")
    device_id = data.get("device_id")
    if entry_id is None and device_id is None:
        if len(coordinators) == 1:
            return next(iter(coordinators.values()))
        raise ServiceValidationError("Specify config_entry_id or device_id")
    if entry_id is not None:
        coordinator = coordinators.get(entry_id)
        if coordinator is None:
            raise ServiceValidationError(f"Unknown config entry: {entry_id}")
        if device_id is not None and coordinator.data.info.device_id != device_id:
            raise ServiceValidationError("config_entry_id and device_id do not match")
        return coordinator
    matches = [
        value
        for value in coordinators.values()
        if value.data.info.device_id == device_id
    ]
    if len(matches) != 1:
        raise ServiceValidationError(f"Unknown device: {device_id}")
    return matches[0]


def _color(value: str | list[int]) -> str:
    if isinstance(value, str):
        return value.lower()
    if len(value) != 3:
        raise ServiceValidationError("color must contain exactly three RGB channels")
    return f"#{value[0]:02x}{value[1]:02x}{value[2]:02x}"


def _validate_selection(
    coordinator: LumaForgeCoordinator, selection: list[int], output_id: str | None
) -> tuple[int, ...]:
    layout = coordinator.data.layout
    if layout is None or not layout.valid_leds:
        raise ServiceValidationError("The device did not provide usable LED bounds")
    allowed = layout.valid_leds
    if output_id is not None:
        if output_id not in layout.output_leds:
            raise ServiceValidationError(f"Unknown output: {output_id}")
        allowed = layout.output_leds[output_id]
    invalid = sorted(set(selection) - allowed)
    if invalid:
        raise ServiceValidationError(f"Invalid LED indices: {invalid}")
    return tuple(dict.fromkeys(selection))


async def _send(
    coordinator: LumaForgeCoordinator, selection: tuple[int, ...], data: dict[str, Any]
) -> None:
    await coordinator.client.async_set_preview(
        selection,
        _color(data["color"]),
        data["brightness"],
        data["effect"],
        data["speed"],
        data["direction"],
    )


def _require_automation_sequences(coordinator: LumaForgeCoordinator) -> None:
    if not coordinator.supports_automation_sequences:
        raise ServiceValidationError(
            "The device does not support native automation sequences"
        )
    if not coordinator.client.websocket_connected:
        raise ServiceValidationError("The device WebSocket is not connected")


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.services.has_service(DOMAIN, "set_led"):
        return

    async def set_led(call: ServiceCall) -> ServiceResponse | None:
        coordinator = _coordinator(hass, call.data)
        selection = _validate_selection(
            coordinator, [call.data["led_index"]], call.data.get("output_id")
        )
        await _send(coordinator, selection, call.data)
        return None

    async def set_led_range(call: ServiceCall) -> ServiceResponse | None:
        coordinator = _coordinator(hass, call.data)
        start, end = call.data["start_index"], call.data["end_index"]
        if start > end:
            raise ServiceValidationError("start_index must not exceed end_index")
        selection = _validate_selection(
            coordinator, list(range(start, end + 1)), call.data.get("output_id")
        )
        await _send(coordinator, selection, call.data)
        return None

    async def apply_to_zone(call: ServiceCall) -> ServiceResponse | None:
        coordinator = _coordinator(hass, call.data)
        zone = next(
            (
                value
                for value in coordinator.data.zones
                if value.zone_id == call.data["zone_id"]
            ),
            None,
        )
        if zone is None:
            raise ServiceValidationError(f"Unknown zone: {call.data['zone_id']}")
        selection = _validate_selection(
            coordinator, list(zone.leds), call.data.get("output_id")
        )
        if not selection:
            raise ServiceValidationError("Zone contains no LEDs")
        await _send(coordinator, selection, call.data)
        color = _color(call.data["color"])
        coordinator.set_zone_optimistic_state(
            zone.zone_id,
            {
                "on": call.data["brightness"] > 0,
                "rgb": tuple(bytes.fromhex(color[1:])),
                "brightness": round(call.data["brightness"] * 255),
                "effect": call.data["effect"],
                "speed": call.data["speed"],
                "direction": call.data["direction"],
            },
        )
        return None

    async def start_automation(call: ServiceCall) -> ServiceResponse | None:
        coordinator = _coordinator(hass, call.data)
        _require_automation_sequences(coordinator)
        automation_id = call.data["automation_id"]
        if not any(
            item.automation_id == automation_id for item in coordinator.data.automations
        ):
            raise ServiceValidationError(f"Unknown automation: {automation_id}")
        try:
            await coordinator.client.async_start_automation(automation_id)
        except LumaForgeError as err:
            raise ServiceValidationError(str(err)) from err
        return None

    async def stop_automation(call: ServiceCall) -> ServiceResponse | None:
        coordinator = _coordinator(hass, call.data)
        _require_automation_sequences(coordinator)
        state = coordinator.automation_state
        if state is None or state.state != "running":
            raise ServiceValidationError("No automation is currently running")
        try:
            await coordinator.client.async_stop_automation()
        except LumaForgeError as err:
            raise ServiceValidationError(str(err)) from err
        return None

    async def next_automation_step(call: ServiceCall) -> ServiceResponse | None:
        coordinator = _coordinator(hass, call.data)
        _require_automation_sequences(coordinator)
        state = coordinator.automation_state
        if state is None or state.state != "running":
            raise ServiceValidationError("No automation is currently running")
        try:
            await coordinator.client.async_next_automation_step()
        except LumaForgeError as err:
            raise ServiceValidationError(str(err)) from err
        return None

    hass.services.async_register(DOMAIN, "set_led", set_led, schema=SET_LED_SCHEMA)
    hass.services.async_register(
        DOMAIN, "set_led_range", set_led_range, schema=SET_LED_RANGE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "apply_to_zone", apply_to_zone, schema=APPLY_ZONE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        "start_automation",
        start_automation,
        schema=START_AUTOMATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "stop_automation",
        stop_automation,
        schema=AUTOMATION_COMMAND_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "next_automation_step",
        next_automation_step,
        schema=AUTOMATION_COMMAND_SCHEMA,
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove services after the final entry unloads."""
    for service in (
        "set_led",
        "set_led_range",
        "apply_to_zone",
        "start_automation",
        "stop_automation",
        "next_automation_step",
    ):
        hass.services.async_remove(DOMAIN, service)
