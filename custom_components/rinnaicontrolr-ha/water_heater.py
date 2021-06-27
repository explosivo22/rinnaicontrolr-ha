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
from homeassistant.components.water_heater import WaterHeaterEntity

from .const import DOMAIN as RINNAI_DOMAIN
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

ICON_DOMESTIC_TEMP='mdi:thermometer'
NAME_WATER_TEMPERATURE = "Water Temperature"

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Rinnai Water heater from config entry."""
    devices: list[RinnaiDeviceDataUpdateCoordinator] = hass.data[RINNAI_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    entities = []
    for device in devices:
        entities.extend(
            [
                RinnaiWaterHeater(NAME_WATER_TEMPERATURE, device),
            ]
        )
    async_add_entities(entities)

class RinnaiWaterHeater(RinnaiEntity, WaterHeaterEntity):
    """Water Heater entity for a Rinnai Device"""

    def __init__(self, device: RinnaiDeviceDataUpdateCoordinator) -> None:
        """Initialize the water heater."""
        super().__init__("water_heater", "Water Heater", device)

    @property
    def temperature_unit(self):
        return TEMP_FAHRENHEIT

    @property
    def device_state_attributes(self):
        """Return the optional device state attributes."""
        data = {"target_temp_step": 5}
        return data

    @property
    def current_operation(self):
        return self._current_operation

    @property
    def min_temp(self):
        return 110

    @property
    def max_temp(self):
        return 140

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_features

    @property
    def target_temperature(self):
        """Return the temperature we try to reach"""
        return self._device.get('info').get('set_domestic_temperature')

    @property
    def current_temperature(self):
        """REturn the current temperature."""
        return self._device.get('info').get('domestic_temperature')