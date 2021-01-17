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
from homeassistant.components import websocket_api
from homeassistant.util import dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.components.water_heater import (
    STATE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN,
)

from .const import ICON_DOMESTIC_TEMP, SIGNAL_UPDATE_RINNAI

from . import RinnaiEntity, RinnaiDeviceEntity, RINNAI_DOMAIN, RINNAI_SERVICE, CONF_DEVICE_ID

LOG = logging.getLogger(__name__)

ATTR_DURATION = 'duration'

SUPPORT_FLAGS_HEATER = SUPPORT_TARGET_TEMPERATURE

WS_START_RECIRCULATION = 'rinnai_start_recirculation'
WS_START_RECIRCULATION_SCHEMA = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    { 
    vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Required(ATTR_DURATION): cv.positive_int,
    }
)

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

        water_heater.append( RinnaiWaterHeaterEntity(hass, rinnai, device_id, user_uuid) )

    add_water_heater_callback(water_heater)

    hass.components.websocket_api.async_register_command(
        WS_START_RECIRCULATION, websocket_start_recirculation, WS_START_RECIRCULATION_SCHEMA
    )

class RinnaiWaterHeaterEntity(RinnaiDeviceEntity):
    """Water Heater entity for a Rinnai Device"""

    def __init__(self, hass, rinnai, device_id, user_uuid):
        super().__init__(hass, 'Rinnai Water Heater', device_id, user_uuid)
        self._name = 'Rinnai Water Heater'
        self._current_temperature = None
        self._target_temperature = None
        self._current_setpoint = None
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
    def device_info(self):
        return {
            "manufacturer": "Rinnai",
            "model": self.device_state.get('model'),
            "dsn": self.device_state.get('dsn')
        }

    @property
    def temperature_unit(self):
        return TEMP_FAHRENHEIT

    @property
    def state_attributes(self):
        data = {}
        data['info'] = self.device_state.get('info')
        data['setpoint'] = self.device_state.get('shadow').get('set_domestic_temperature')
        return data

    def update(self):
        """Update sensor state"""
        if not self.device_state:
            return

        self._current_temperature = self.device_state.get('info').get('domestic_temperature')
        self._low_temp = 110
        self._max_temp = 140
        self._target_temperature = self.device_state.get('shadow').get('set_domestic_temperature')
        self.update_state(self._current_temperature)

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

    @property
    def target_temp(self):
        """Return the temperature we try to reach"""
        return self._target_temperature

    def start_recirculation(self, duration=30):
        self.rinnai_service.start_recirculation(self._device_id, self._user_uuid, duration)

    async def async_start_recirculation(self, duration):
        return await self.hass.async_add_executor_job(self.start_recirculation, duration)

    async def async_added_to_hass(self):
        self.update_state(None)

def _get_base_from_entity_id(hass, entity_id):
    component = hass.data.get(DOMAIN)
    if component is None:
        raise HomeAssistantError("base component not set up")

    base = component.get_entity(entity_id)
    if base is None:
        raise HomeAssistantError("base not found")

    return base

@websocket_api.async_response
async def websocket_start_recirculation(hass, connection, msg):
    base = _get_base_from_entity_id(hass, msg["entity_id"])

    await base.async_start_recirculation(duration=msg["duration"])
    connection.send_message(websocket_api.result_message(msg["id"], {"recirculation": "on"}))