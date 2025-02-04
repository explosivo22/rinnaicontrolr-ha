"""Constants for Rinnai Water Heater Monitoring"""
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = 'rinnai'
CLIENT = "client"

ATTRIBUTION = "Data provided by Rinnai"

DEFAULT_UNIT = "fahrenheit"
CONF_UNIT = "units"

COORDINATOR = "coordinator"

CONF_MAINT_INTERVAL_ENABLED = "maint_interval_enabled"
DEFAULT_MAINT_INTERVAL_ENABLED = True
CONF_MAINT_REFRESH_INTERVAL = "maint_refresh_interval"
DEFAULT_MAINT_REFRESH_INTERVAL = 300
CONF_REFRESH_INTERVAL = "refresh_interval"
DEFAULT_REFRESH_INTERVAL = 30

CONF_UNITS = ["celsius", "fahrenheit"]

ATTR_CACHE = 'cache'
ATTR_COORDINATOR = 'coordinator'

SIGNAL_UPDATE_RINNAI = 'rinnai_temp_update'

ICON_DOMESTIC_TEMP='mdi:thermometer'
ICON_RECIRCULATION='mdi:sync'
ICON_RECIRCULATION_DISABLED='mdi:octagon-outline'

CONF_UNIT_SYSTEM_IMPERIAL = "imperial"
CONF_UNIT_SYSTEM_METRIC = "metric"