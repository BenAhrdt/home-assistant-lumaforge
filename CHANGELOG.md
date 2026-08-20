# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.1] - 2026-08-20

### Changed

- Display diagnostic percentages without decimal places and data sizes in kB or
  MB with two decimal places while retaining bytes as the native API unit.
- Label heap-memory diagnostics explicitly as RAM.

## [0.4.0] - 2026-08-20

### Added

- Native firmware UpdateEntity for devices advertising `ota_update`, including
  device-side check/install commands, progress, errors and reboot recovery.
- WebSocket-driven system status plus diagnostic sensors for physical flash,
  firmware partition and LittleFS capacity and usage.
- Optional `lumaforge.check_for_update` and `lumaforge.install_update` services.

## [0.3.1] - 2026-08-20

### Changed

- Prefix scene, zone and automation entity names with their type so related
  controls sort together on Home Assistant's generated device page.

## [0.3.0] - 2026-08-20

### Added

- Native multi-step automation start, stop and next-step commands, global
  controls, runtime status sensor and matching Home Assistant services.
- Backwards-compatible parsing of legacy single-scene automations.

### Changed

- Probe only the lightweight identity endpoint every 15 seconds while a device
  is offline, then reload all data immediately after it returns.
- Trigger an API connection check when an established WebSocket disconnects.
- Reduce the request timeout from 10 to 5 seconds.

### Fixed

- Keep the connectivity entity available so it reports `Disconnected` instead
  of becoming unavailable when polling fails.
- Advertise effect support on zone lights so Home Assistant displays the
  effect selector.

## [0.2.0] - 2026-08-20

### Added

- Dynamic scene, zone light, automation button and automation switch entities.
- ESP32 and simulator WebSocket transports with acknowledgement handling and
  reconnect.
- Targeted LED, LED-range and zone services.
- Documentation of the complete local REST and WebSocket API.

## [0.1.3] - 2026-08-20

### Fixed

- Pass the discovered device name to the confirmation form so localized
  discovery text renders correctly instead of showing `MISSING_VALUE`.

## [0.1.2] - 2026-08-20

### Changed

- Make setup discovery-only. Users are no longer asked for internal host and
  port connection data when adding the integration manually.
- Clarify that each discovered device gets an independent config entry under
  the same LumaForge integration.

## [0.1.1] - 2026-08-20

### Fixed

- Use the current Home Assistant service-info import path so the config flow
  loads on recent Home Assistant releases.

## [0.1.0] - 2026-08-20

### Added

- Automatic discovery through `_lumaforge._tcp.local.`.
- Device verification and stable identity through `/api/v1/info` and
  `device_id`.
- Manual setup by hostname or IP address.
- Automatic connection-data updates when a known device changes address.
- Local polling of device information and status through a typed coordinator.
- Connectivity, Wi-Fi signal, CPU, and memory diagnostic entities.
- Disabled-by-default metadata and capability diagnostic entities.
- Home Assistant device registration with model, firmware, serial number, and
  local configuration URL.
- Redacted downloadable diagnostics.
- German and English user-interface translations.
- HACS metadata and a project-local brand icon.
- Automated tests, Ruff linting, Hassfest validation, HACS validation,
  dependency updates, and tag-driven GitHub releases.

### Security

- Communication remains local and read-only; no credentials or cloud services
  are used.
- Downloaded diagnostics redact IP addresses and hostnames.

[Unreleased]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/BenAhrdt/home-assistant-lumaforge/releases/tag/v0.1.0
