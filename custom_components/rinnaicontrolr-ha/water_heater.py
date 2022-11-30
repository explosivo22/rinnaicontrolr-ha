"""Water Heater representing the water heater for the Rinnai integration"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.water_heater import WaterHeaterEntity, SUPPORT_TARGET_TEMPERATURE, ATTR_TEMPERATURE, STATE_GAS, STATE_OFF
from homeassistant.helpers import entity_platform
from homeassistant.util.unit_system import METRIC_SYSTEM
from homeassistant.const import (
    UnitOfTemperature,
)

from .const import DOMAIN as RINNAI_DOMAIN, LOGGER, CONF_UNIT
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

OPERATION_LIST = [STATE_OFF, STATE_GAS]
ATTR_RECIRCULATION_MINUTES = "recirculation_minutes"
SERVICE_START_RECIRCULATION = "start_recirculation"
SERVICE_STOP_RECIRCULATION = "stop_recirculation"

# The Rinnai app hardcodes recirculation durations to certain intervals
RECIRCULATION_MINUTE_OPTIONS = set([5, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180, 195, 210, 225, 240, 255, 270, 285, 300])

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Rinnai Water heater from config entry."""
    devices: list[RinnaiDeviceDataUpdateCoordinator] = hass.data[RINNAI_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    entities = []
    for device in devices:
        entities.append(RinnaiWaterHeater(device))
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_START_RECIRCULATION,
        {
            vol.Required(ATTR_RECIRCULATION_MINUTES, default=5): vol.In(RECIRCULATION_MINUTE_OPTIONS)
        },
        "async_start_recirculation",
    )

    platform.async_register_entity_service(
        SERVICE_STOP_RECIRCULATION, {}, "async_stop_recirculation"
    )

class RinnaiWaterHeater(RinnaiEntity, WaterHeaterEntity):
    """Water Heater entity for a Rinnai Device"""

    _attr_operation_list = OPERATION_LIST
    _attr_supported_features = SUPPORT_TARGET_TEMPERATURE

    def __init__(self, device: RinnaiDeviceDataUpdateCoordinator) -> None:
        """Initialize the water heater."""
        super().__init__("water_heater", f"{device.device_name} Water Heater", device)

    @property
    def is_on(self):
        return self._device.is_heating

    @property
    def current_operation(self):
        """Return current operation"""
        if self.is_on:
            return STATE_GAS
        else:
            return STATE_OFF

    @property
    def icon(self):
        """Return the icon to use for the valve."""
        return "mdi:water-boiler"

    @property
    def temperature_unit(self):
        if self.hass.config.units is METRIC_SYSTEM:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

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
    def is_away_mode_on(self):
        return self._device.vacation_mode_on

    @property
    def outlet_temperature(self):
        return round(self._device.outlet_temperature, 1)

    @property
    def inlet_temperature(self):
        return round(self._device.inlet_temperature, 1)

    @property
    def current_temperature(self):
        """REturn the current temperature."""
        return self._device.current_temperature

    @property
    def extra_state_attributes(self) -> dict:
        """Return the optional device state attributes."""
        return {
            "target_temp_step": 5,
            "outlet_temperature": self.outlet_temperature,
            "inlet_temperature": self.inlet_temperature
        }

    async def async_set_temperature(self, **kwargs):
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is not None:
            await self._device.async_set_temperature(int(target_temp))
            LOGGER.debug("Updated temperature to: %s", target_temp)
        else:
            LOGGER.error("A target temperature must be provided")

    async def async_start_recirculation(self, recirculation_minutes = 5):
        await self._device.async_start_recirculation(recirculation_minutes)
        self.async_write_ha_state()

    async def async_stop_recirculation(self):
        await self._device.async_stop_recirculation()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
