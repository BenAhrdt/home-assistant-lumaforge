# LumaForge for Home Assistant

A local-only Home Assistant custom integration for LumaForge devices. It discovers
devices via `_lumaforge._tcp.local.`, verifies their identity through
`/api/v1/info`, and exposes useful read-only diagnostics. No account, cloud
service, authentication, or YAML configuration is used.

Current integration version: **0.1.2**. Release history is available in the
[changelog](CHANGELOG.md).

## Requirements

- Home Assistant 2025.7.0 or newer
- LumaForge firmware exposing API version 1
- Home Assistant must be able to reach the device over local HTTP

## Installation

### HACS custom repository

1. Open HACS, select **Integrations**, then the three-dot menu and
   **Custom repositories**.
2. Add this GitHub repository URL with category **Integration**.
3. Search for and install **LumaForge**.
4. Restart Home Assistant.

### Manual installation

Copy `custom_components/lumaforge` into the `custom_components` directory in
your Home Assistant configuration directory, then restart Home Assistant.

## Setup and discovery

Devices advertising `_lumaforge._tcp.local.` appear under
**Settings → Devices & services**. Review and confirm each discovery. LumaForge
is discovery-only: users never need to enter an IP address or port. Each device
gets its own config entry, while all devices are grouped under the same
LumaForge integration.

The API `device_id` is the sole persistent identity. Changing an IP address,
hostname, or user-facing device name does not create another device. Rediscovery
updates the stored connection address.

## Device information and entities

The integration registers manufacturer, model, serial/device ID, installed
firmware version, device name, and a local configuration URL. It polls every 60
seconds and provides:

- connectivity, Wi-Fi signal, CPU usage, used/total memory, and memory usage;
- disabled-by-default diagnostic sensors for IP, hostname, device ID, device
  name, firmware/API version, model, and capabilities.

Unavailable devices remain configured and their entities become unavailable.
Downloaded diagnostics redact hostnames and IP addresses.

## Privacy and security

All communication is local, read-only HTTP. The integration does not contact
GitHub, a LumaForge cloud service, or any other external service at runtime. It
does not request or log Wi-Fi credentials. Because the current API uses plain
HTTP without authentication, keep devices on a trusted local network.

## Troubleshooting discovery

mDNS uses multicast and generally does not cross VLANs or routed subnets. If
Home Assistant and the device are separated, allow multicast DNS traffic or use
an mDNS reflector/repeater appropriate for your network. Check that multicast
is not blocked by Wi-Fi client isolation or firewall rules. There is no manual
host/IP setup fallback; direct local HTTP reachability is still required after
discovery.

## Current limitations and roadmap

This first release does not control LEDs, scenes, or zones. The device API only
reports the installed firmware version; it does not provide a latest version,
release URL, or update state. Consequently, this integration deliberately makes
no “firmware is current” claim and has no `UpdateEntity`.

Planned work includes LED output controls, scene and zone support, and OTA
updates once the firmware exposes a trustworthy local update contract.

## Releases

Versions follow Semantic Versioning. The integration version in
`custom_components/lumaforge/manifest.json` must match the Git tag with a `v`
prefix, for example manifest version `0.1.0` and tag `v0.1.0`. Pushing a matching
tag creates a GitHub Release automatically. A mismatched tag fails without
publishing a release.
