# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/BenAhrdt/home-assistant-lumaforge/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/BenAhrdt/home-assistant-lumaforge/releases/tag/v0.1.0
