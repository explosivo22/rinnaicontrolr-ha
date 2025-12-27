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

CONF_MAINT_INTERVAL_MINUTES: Final = "maint_interval_minutes"
DEFAULT_MAINT_INTERVAL_MINUTES: Final = 5
MIN_MAINT_INTERVAL_MINUTES: Final = 1
MAX_MAINT_INTERVAL_MINUTES: Final = 60

CONF_RECIRCULATION_DURATION: Final = "recirculation_duration"
DEFAULT_RECIRCULATION_DURATION: Final = 10

# Token storage keys
CONF_REFRESH_TOKEN: Final = "conf_refresh_token"
CONF_ACCESS_TOKEN: Final = "conf_access_token"

# Password storage (optional - for automatic re-authentication)
CONF_SAVE_PASSWORD: Final = "save_password"
CONF_STORED_PASSWORD: Final = "stored_password"
DEFAULT_SAVE_PASSWORD: Final = False

# Connection modes
CONF_CONNECTION_MODE: Final = "connection_mode"
CONNECTION_MODE_CLOUD: Final = "cloud"
CONNECTION_MODE_LOCAL: Final = "local"
CONNECTION_MODE_HYBRID: Final = "hybrid"

# Local connection settings
CONF_HOST: Final = "host"
LOCAL_PORT: Final = 9798
