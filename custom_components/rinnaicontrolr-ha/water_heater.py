"""Water Heater representing the water heater for the Rinnai integration"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.water_heater import WaterHeaterEntity, WaterHeaterEntityFeature, ATTR_TEMPERATURE, STATE_GAS, STATE_OFF, STATE_ON
from homeassistant.helpers import entity_platform
from homeassistant.util.unit_system import METRIC_SYSTEM
from homeassistant.const import (
    UnitOfTemperature,
)

from .const import DOMAIN as RINNAI_DOMAIN, LOGGER, COORDINATOR
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

STATE_IDLE = "idle"

OPERATION_LIST = [STATE_OFF, STATE_ON]
ATTR_RECIRCULATION_MINUTES = "recirculation_minutes"
SERVICE_START_RECIRCULATION = "start_recirculation"
SERVICE_STOP_RECIRCULATION = "stop_recirculation"

# The Rinnai app hardcodes recirculation durations to certain intervals
RECIRCULATION_MINUTE_OPTIONS = set([5, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180, 195, 210, 225, 240, 255, 270, 285, 300])

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Rinnai Water heater from config entry."""
    device = hass.data[RINNAI_DOMAIN][config_entry.entry_id][COORDINATOR]
    entities = []
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
    _attr_supported_features = (WaterHeaterEntityFeature.AWAY_MODE | WaterHeaterEntityFeature.OPERATION_MODE | WaterHeaterEntityFeature.TARGET_TEMPERATURE)

    def __init__(self, device: RinnaiDeviceDataUpdateCoordinator) -> None:
        """Initialize the water heater."""
        super().__init__("water_heater", f"{device.device_name} Water Heater", device)

    @property
    def current_operation(self):
        """Return current operation"""
        if self._device.is_heating:
            return STATE_GAS
        elif self._device.is_on:
            return STATE_IDLE
        else:
            return STATE_OFF

    @property
    def icon(self):
        """Return the icon to use for the valve."""
        return "mdi:water-boiler"

    @property
    def temperature_unit(self):
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

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self._device.async_enable_vacation_mode()

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self._device.async_disable_vacation_mode()

    async def async_set_operation_mode(self, operation_mode):
        if operation_mode == STATE_ON:
            await self._device.async_turn_on()
        elif operation_mode == STATE_GAS:
            await self._device.async_turn_on()
        else: #STATE OFF
            await self._device.async_turn_off()

    async def async_turn_on(self):
        """Turn on."""
        await self.async_set_operation_mode(STATE_ON)

    async def async_turn_off(self):
        """Turn off."""
        await self.async_set_operation_mode(STATE_OFF)

    async def async_start_recirculation(self, recirculation_minutes = 5):
        await self._device.async_start_recirculation(recirculation_minutes)

    async def async_stop_recirculation(self):
        await self._device.async_stop_recirculation()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
