"""Constants for the LumaForge integration."""

from datetime import timedelta

DOMAIN = "lumaforge"
DATA_COORDINATORS = "coordinators"
MANUFACTURER = "LumaForge"
PRODUCT = "LumaForge"
SUPPORTED_API_VERSIONS = {1}

CONF_PORT = "port"
DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 10
UPDATE_INTERVAL = timedelta(seconds=60)

EFFECTS = ("solid", "blink", "pulse", "wipe", "chase", "rainbow")
DIRECTIONS = ("forward", "reverse")
