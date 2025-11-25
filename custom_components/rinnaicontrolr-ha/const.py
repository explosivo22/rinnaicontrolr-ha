"""Constants for Rinnai Water Heater Monitoring."""

from __future__ import annotations

import logging
from typing import Final

LOGGER: Final = logging.getLogger(__package__)

DOMAIN: Final = "rinnai"

ATTRIBUTION: Final = "Data provided by Rinnai"

DEFAULT_UNIT: Final = "fahrenheit"
CONF_UNIT: Final = "units"

CONF_MAINT_INTERVAL_ENABLED: Final = "maint_interval_enabled"
DEFAULT_MAINT_INTERVAL_ENABLED: Final = True

CONF_UNITS: Final[list[str]] = ["celsius", "fahrenheit"]

SIGNAL_UPDATE_RINNAI: Final = "rinnai_temp_update"

ICON_DOMESTIC_TEMP: Final = "mdi:thermometer"
ICON_RECIRCULATION: Final = "mdi:sync"
ICON_RECIRCULATION_DISABLED: Final = "mdi:octagon-outline"

CONF_UNIT_SYSTEM_IMPERIAL: Final = "imperial"
CONF_UNIT_SYSTEM_METRIC: Final = "metric"

CONF_REFRESH_TOKEN: Final = "conf_refresh_token"
CONF_ACCESS_TOKEN: Final = "conf_access_token"

# Connection modes
CONF_CONNECTION_MODE: Final = "connection_mode"
CONNECTION_MODE_CLOUD: Final = "cloud"
CONNECTION_MODE_LOCAL: Final = "local"
CONNECTION_MODE_HYBRID: Final = "hybrid"

# Local connection settings
CONF_HOST: Final = "host"
LOCAL_PORT: Final = 9798
