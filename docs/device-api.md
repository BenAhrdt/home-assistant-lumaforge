# LumaForge local API

This integration uses the existing local REST and WebSocket interfaces below.
The legacy `/api/v1` and editor list paths intentionally differ; paths must not
be normalized by clients.

## REST endpoints

All requests use the mDNS-advertised HTTP host and port, are asynchronous and
have a 10-second timeout. HTTP `404` on an optional editor endpoint means that
the installed firmware does not support that resource. Other HTTP errors,
invalid JSON, timeouts and connection failures remain errors rather than being
interpreted as missing capabilities.

| Method | Path | Purpose | Used by Home Assistant |
| --- | --- | --- | --- |
| GET | `/api/v1/info` | Identity, network and capability data | Yes |
| GET | `/api/v1/status` | Runtime diagnostics | Yes |
| GET | `/api/v1/device` | Device settings | Client method available |
| PUT | `/api/v1/device` | Update `device_name` | Client method available |
| GET | `/api/project` | Complete editor project | Client method available |
| POST | `/api/project/import` | Import a project | No; never called |
| GET/PUT | `/api/layout` | Read or replace layout | GET only |
| GET/PUT | `/api/zones` | Read or replace zones | GET only |
| GET/PUT | `/api/scenes` | Read or replace scenes | GET only |
| GET/PUT | `/api/automations` | Read or replace automations | Both |
| GET | `/api/config` | Legacy combined configuration | No |

`GET /api/v1/info` returns the existing identity document, including stable
`device_id`, mutable `device_name`, model, firmware/API version, network object
and an array of capability strings. `GET /api/v1/status` returns optional
`wifi`, `ip`, `rssi`, `cpuPercent`, `memoryUsedBytes` and `memoryTotalBytes`
fields. These two endpoints remain mandatory.

The editor list endpoints may return either a JSON array or an object containing
that array under `layout`, `zones`, `scenes` or `automations`. Every scene, zone
and automation must have a stable string `id`. A scene contains `animations`.
A zone contains logical LED indices in `leds`. An automation contains `sceneId`
and may contain Boolean `enabled`.

Layout sections/outputs provide `id` or `outputId`, `startIndex`, and `ledCount`
(the parser also accepts the documented aliases `start`, `count` and
`led_count`). These bounds validate service calls and keep physical output IDs
separate from global logical LED indices. Layout sections are not exposed as
entities.

Enabling an automation performs a fresh `GET /api/automations`, changes only
the selected object's `enabled` value, sends the complete array to
`PUT /api/automations`, and reloads the list. Writes are serialized to avoid
losing concurrent changes.

## WebSocket interface

The variant is derived from `/api/v1/info`. A model containing `simulator`, a
Boolean `simulator`, or `server_variant: "simulator"` selects the simulator.
All other devices use the ESP32 transport:

- ESP32: `ws://DEVICE_HOST:81/`
- Simulator: `ws://DEVICE_HOST:HTTP_PORT/ws`

The first server message must be `{"type":"hello","apiVersion":1}`. Commands
are serialized because the current acknowledgement contract has no request ID.
The client waits for `<command-type>.accepted`; `{"type":"error", "message":
"..."}` rejects the waiting command. Disconnects fail the pending command and
reconnect with exponential backoff capped at 30 seconds. After reconnection the
coordinator refreshes the complete REST snapshot.

Implemented commands are:

```json
{"type":"scene.play","sceneId":"scene-1"}
{"type":"scene.stop"}
{"type":"preview.set","selection":[0,1],"color":"#5aa5e1","brightness":0.8,"effect":"solid","speed":1.0,"direction":"forward"}
{"type":"preview.cancel"}
{"type":"preview.apply"}
```

The client handles `layout.updated`, `zones.updated`, `scenes.updated` and
`automations.updated`. A simulator payload is validated and applied directly.
An ESP32 event without `payload` reloads the corresponding REST endpoint.

## Home Assistant representation

- Each stored scene is a `SceneEntity`; activation sends `scene.play`.
- One button sends `scene.stop` while scenes exist.
- Each zone is an RGB `LightEntity`; its `leds` become `preview.set.selection`.
- Each device-internal automation has a run button that plays its `sceneId`.
- Automations containing `enabled` also have a switch backed by the full-list
  GET/PUT process.
- `lumaforge.set_led`, `lumaforge.set_led_range` and
  `lumaforge.apply_to_zone` expose targeted control without creating hundreds
  of LED entities.

Entities use immutable device object IDs in their unique IDs. Coordinator
updates reconcile additions, renames and deletions; deleted objects are also
removed from the entity registry.

Known effects are `solid`, `blink`, `pulse`, `wipe`, `chase`, and `rainbow`.
Device brightness is `0.0` through `1.0`; Home Assistant light brightness is
converted from `0` through `255`. Colors are sent as six-digit RGB hex strings.

## Runtime-state and firmware limitations

The firmware does not provide a complete persistent runtime state per zone.
Zone lights therefore start with unknown state and retain an explicitly marked
optimistic state only after the device acknowledges a Home Assistant command.
That memory is discarded on reload/restart. Stored scene definitions are never
misrepresented as current zone state. Turning a zone off uses `preview.set`
with brightness `0`; `preview.cancel` is not used because it could affect other
selections.

Automations are device-stored configuration, not Home Assistant automations.
The switch persists `enabled`, while the run button directly tests `sceneId` in
the same way as the editor. Current evidence indicates that time scheduling may
be executed by editor JavaScript; this integration does not claim autonomous
ESP32 scheduling.

The `automations` endpoint can exist without an `automations` capability, so
the integration probes known optional endpoints and treats only `404` as
unsupported. Older firmware exposing only `/api/v1/info` and
`/api/v1/status` remains diagnostics-only. A missing WebSocket affects control
entity availability but not diagnostic sensors.
