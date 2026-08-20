"""Constants for the LumaForge integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "lumaforge"
MANUFACTURER = "LumaForge"
PRODUCT = "LumaForge"
SUPPORTED_API_VERSIONS = {1}

CONF_PORT = "port"
DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 10
UPDATE_INTERVAL = timedelta(seconds=60)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
