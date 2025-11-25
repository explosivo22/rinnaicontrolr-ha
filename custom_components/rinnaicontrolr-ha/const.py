"""Constants for Rinnai Water Heater Monitoring."""

from __future__ import annotations

import logging
from typing import Final

LOGGER: Final = logging.getLogger(__package__)

DOMAIN: Final = "rinnai"

ATTRIBUTION: Final = "Data provided by Rinnai"

# Configuration keys
CONF_MAINT_INTERVAL_ENABLED: Final = "maint_interval_enabled"
DEFAULT_MAINT_INTERVAL_ENABLED: Final = True

CONF_RECIRCULATION_DURATION: Final = "recirculation_duration"
DEFAULT_RECIRCULATION_DURATION: Final = 10

# Token storage keys
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
