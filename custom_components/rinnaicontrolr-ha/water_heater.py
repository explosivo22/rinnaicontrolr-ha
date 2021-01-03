"""
Support for Rinnai water heater monitoring and control devices
FUTURE:
- convert to async
"""
from datetime import datetime, timedelta
import time
import logging
import voluptuous as vol

import aiohttp

from homeassistant.const import TEMP_FAHRENHEIT, ATTR_TEMPERATURE, CONF_SCAN_INTERVAL, ATTR_ENTITY_ID, DEVICE_CLASS_TEMPERATURE
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.util import dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.components.water_heater import (
    STATE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW
)

from .const import ICON_DOMESTIC_TEMP, SIGNAL_UPDATE_RINNAI

from . import RinnaiEntity, RinnaiDeviceEntity, RINNAI_DOMAIN, RINNAI_SERVICE, CONF_DEVICE_ID

LOG = logging.getLogger(__name__)

SUPPORT_FLAGS_HEATER = SUPPORT_TARGET_TEMPERATURE

def setup_platform(hass, config, add_water_heater_callback, discovery_info=None):
    rinnai = hass.data[RINNAI_SERVICE]
    if rinnai is None or not rinnai.is_connected:
        LOG.warning("No connection to Rinnai Service, ignoring setup of platform water heater")
        return False

    if discovery_info:
        device_id = discovery_info[CONF_DEVICE_ID]
    else:
        device_id = config[CONFIG_DEVICE_ID]

    water_heater = []

    device = rinnai.getDevices()

    for device_details in device:
        device_id = device_details['thing_name']
        user_uuid = device_details['user_uuid']

        water_heater.append( RinnaiWaterHeaterEntity(hass, device_id, user_uuid) )

    add_water_heater_callback(water_heater)

class RinnaiWaterHeaterEntity(RinnaiDeviceEntity):
    """Water Heater entity for a Rinnai Device"""

    def __init__(self, hass, device_id, user_uuid):
        super().__init__(hass, 'Rinnai Water Heater', device_id, user_uuid)
        self.hass = hass
        self._name = 'Rinnai Water Heater'
        self._current_temperature = None
        self._max_temp = 140
        self._low_temp = 110
        self._state = self.device_state
        if self._state:
            self.update()

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"rinnai_water_heater_{self._device_id}"

    @property
    def temperature_unit(self):
        return TEMP_FAHRENHEIT

    def update(self):
        """Update sensor state"""
        if not self.device_state:
            return

        self._current_temperature = self.get_telemetry('domestic_temperature')
        self._low_temp = 110
        self._max_temp = 140
        self.schedule_update_ha_state()

    async def set_rinnai_temp(self, temp):
        url = "https://d1coipyopavzuf.cloudfront.net/api/device_shadow/input"
        
        # check if the temp is a multiple of 5. Rinnai only takes temps this way
        if temp % 5 == 0:
            payload="user=%s&thing=%s&attribute=set_domestic_temperature&value=%s" % (self._user_uuid, self._device_id, int(temp))
            LOG.debug(payload)
            headers = {
              'User-Agent': 'okhttp/3.12.1',
              'Content-Type': 'application/x-www-form-urlencoded'
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=payload) as resp:
                    data = await resp.json()
                    LOG.debug(data)
                    if resp.status == 200:
                        return

    async def async_set_temperature(self, **kwargs):
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp and target_temp != self._current_temperature:
            await self.set_rinnai_temp(target_temp)
            self._current_temperature = target_temp
            self.update_state(self._current_temperature)

            self.async_schedule_update_ha_state(force_refresh=True)

    @property 
    def current_temperature(self):
        return self._current_temperature

    @property
    def min_temp(self):
        return self._min_temp

    @property
    def max_temp(self):
        return self._max_temp

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_HEATER