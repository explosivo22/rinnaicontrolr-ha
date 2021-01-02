"""
Support for Rinnai water heater monitoring and control devices
FUTURE:
- convert to async
"""
from datetime import datetime, timedelta
import time
import logging
import voluptuous as vol

from homeassistant.const import TEMP_FAHRENHEIT, ATTR_TEMPERATURE, CONF_SCAN_INTERVAL, ATTR_ENTITY_ID, DEVICE_CLASS_PRESSURE, DEVICE_CLASS_TEMPERATURE
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.util import dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from .const import ICON_DOMESTIC_TEMP

from . import RinnaiEntity, RinnaiDeviceEntity, RINNAI_DOMAIN, RINNAI_SERVICE, CONF_DEVICE_ID

LOG = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE_ID): cv.string
})

# pylint: disable=unused-argument
def setup_platform(hass, config, add_sensors_callback, discovery_info=None):
    """Setup the Rinnai water heater monitoring sensors"""

    rinnai = hass.data[RINNAI_SERVICE]
    if rinnai is None or not rinnai.is_connected:
        LOG.warning("No connection to Rinnai service, ignoring setup of platform sensor")
        return False

    if discovery_info:
        device_id = discovery_info[CONF_DEVICE_ID]
    else:  # manual config
        device_id = config[CONF_DEVICE_ID]

    sensors = []
    mode_sensors = {}

    device = rinnai.getDevices()

    # create device-based sensors for all devices at this location
    for device_details in device:
        device_id = device_details['thing_name']
        user_uuid = device_details['user_uuid']

        sensors.append( RinnaiTempSensor(hass, device_id, user_uuid))

    add_sensors_callback(sensors)

class RinnaiTempSensor(RinnaiDeviceEntity):
    """Water temp sensor for a Rinnai device"""

    def __init__(self, hass, device_id, user_uuid):
        super().__init__(hass, 'Rinnai Water Temperature', device_id, user_uuid)
        self.update()

    @property
    def unit_of_measurement(self):
        return TEMP_FAHRENHEIT

    @property
    def icon(self):
        return ICON_DOMESTIC_TEMP

    def update(self):
        """Update sensor state"""
        state = self.get_telemetry('domestic_temperature')
        if state:
            self.update_state(state)

    @property
    def unique_id(self):
        return f"rinnai_temp_{self._device_id}"

    @property
    def device_class(self):
        """Return the device class for this sensor."""
        return DEVICE_CLASS_TEMPERATURE