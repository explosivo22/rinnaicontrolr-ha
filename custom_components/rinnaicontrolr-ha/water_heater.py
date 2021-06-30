"""Water Heater representing the water heater for the Rinnai integration"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.water_heater import WaterHeaterEntity, SUPPORT_TARGET_TEMPERATURE, TEMP_FAHRENHEIT, ATTR_TEMPERATURE
from homeassistant.core import callback
from homeassistant.helpers import entity_platform

from .const import DOMAIN as RINNAI_DOMAIN, LOGGER
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

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
        self._state = self._device.last_known_state == "False"

    @property
    def state(self):
        return self._device.last_known_state

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
    def device_state_attributes(self):
        """Return the optional device state attributes."""
        data = {"target_temp_step": 5}
        return data

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

    async def set_temperature(self, **kwargs):
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is not None:
            await self._device.async_set_temperature(target_temp)
            self.async_schedule_update_ha_state(forst_refresh=True)
        else:
            LOGGER.error("A target temperature must be provided")

    @callback
    def async_update_state(self) -> None:
        """Retrieve the latest valve state and update the state machine."""
        self._state = self._device.last_known_state == "False"
        self.async_write_ha_state()

    async def async_update(self) -> None:
        await super().async_update()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(self._device.async_add_listener(self.async_update_state))