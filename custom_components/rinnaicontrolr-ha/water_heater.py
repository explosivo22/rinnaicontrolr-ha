"""Water Heater representing the water heater for the Rinnai integration"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.water_heater import WaterHeaterEntity, SUPPORT_TARGET_TEMPERATURE, TEMP_FAHRENHEIT, ATTR_TEMPERATURE, STATE_GAS, STATE_OFF
from homeassistant.core import callback
from homeassistant.helpers import entity_platform

from .const import DOMAIN as RINNAI_DOMAIN, LOGGER
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

OPERATION_LIST = [STATE_OFF, STATE_GAS]

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Rinnai Water heater from config entry."""
    devices: list[RinnaiDeviceDataUpdateCoordinator] = hass.data[RINNAI_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    entities = []
    for device in devices:
        entities.append(RinnaiWaterHeater(device))
    async_add_entities(entities)

class RinnaiWaterHeater(RinnaiEntity, WaterHeaterEntity):
    """Water Heater entity for a Rinnai Device"""

    def __init__(self, device: RinnaiDeviceDataUpdateCoordinator) -> None:
        """Initialize the water heater."""
        super().__init__("water_heater", "Water Heater", device)

    @property
    def state(self):
        if self._device.last_known_state:
            return "Running"
        return "Off"

    @property
    def current_operation(self):
        if self._device.last_known_state:
            return STATE_GAS
        return STATE_OFF

    @property
    def operation_list(self):
        return OPERATION_LIST

    @property
    def icon(self):
        """Return the icon to use for the valve."""
        return "mdi:thermometer"

    @property
    def temperature_unit(self):
        return TEMP_FAHRENHEIT

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def target_temperature_step(self):
        return 5

    @property
    def min_temp(self):
        return float(110)

    @property
    def max_temp(self):
        return float(140)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach"""
        return self._device.target_temperature

    @property
    def current_temperature(self):
        """REturn the current temperature."""
        return self._device.current_temperature

    @property
    def should_poll(self) -> bool:
        return True

    async def async_set_temperature(self, **kwargs):
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is not None:
            await self._device.async_set_temperature(target_temp)
            LOGGER.debug("Updated temperature to: %s", target_temp)
        else:
            LOGGER.error("A target temperature must be provided")

    async def async_update(self) -> None:
        await self._device._update_device()
        self.async_write_ha_state()

    @callback
    async def async_update_state(self) -> None:
        """Retrieve the latest state and update the state machine."""
        await self._device._update_device()
        await self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await self.async_on_remove(self._device.async_add_listener(self.async_update_state))