"""Water Heater entity for Rinnai Control-R integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.water_heater import (
    ATTR_TEMPERATURE,
    STATE_GAS,
    STATE_OFF,
    STATE_ON,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_system import METRIC_SYSTEM

from . import RinnaiConfigEntry
from .const import LOGGER
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

STATE_IDLE = "idle"

OPERATION_LIST = [STATE_OFF, STATE_ON]
ATTR_RECIRCULATION_MINUTES = "recirculation_minutes"
SERVICE_START_RECIRCULATION = "start_recirculation"
SERVICE_STOP_RECIRCULATION = "stop_recirculation"

# The Rinnai app hardcodes recirculation durations to certain intervals
RECIRCULATION_MINUTE_OPTIONS = {
    5,
    15,
    30,
    45,
    60,
    75,
    90,
    105,
    120,
    135,
    150,
    165,
    180,
    195,
    210,
    225,
    240,
    255,
    270,
    285,
    300,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RinnaiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Rinnai Water heater from config entry."""
    async_add_entities(
        RinnaiWaterHeater(device) for device in config_entry.runtime_data.devices
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_START_RECIRCULATION,
        {
            vol.Required(ATTR_RECIRCULATION_MINUTES, default=5): vol.In(
                RECIRCULATION_MINUTE_OPTIONS
            )
        },
        "async_start_recirculation",
    )

    platform.async_register_entity_service(
        SERVICE_STOP_RECIRCULATION, {}, "async_stop_recirculation"
    )


class RinnaiWaterHeater(RinnaiEntity, WaterHeaterEntity):
    """Water Heater entity for a Rinnai Device"""

    _attr_operation_list = OPERATION_LIST
    _attr_supported_features = (
        WaterHeaterEntityFeature.AWAY_MODE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
    )

    def __init__(self, device: RinnaiDeviceDataUpdateCoordinator) -> None:
        """Initialize the water heater."""
        super().__init__("water_heater", f"{device.device_name} Water Heater", device)

    @property
    def current_operation(self) -> str:
        """Return current operation"""
        if self._device.is_heating:
            return STATE_GAS
        elif self._device.is_on:
            return STATE_IDLE
        else:
            return STATE_OFF

    @property
    def icon(self) -> str:
        """Return the icon to use for the valve."""
        return "mdi:water-boiler"

    @property
    def temperature_unit(self) -> str:
        return UnitOfTemperature.FAHRENHEIT

    @property
    def min_temp(self) -> float:
        return float(110)

    @property
    def max_temp(self) -> float:
        return float(140)

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach"""
        return self._device.target_temperature

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return whether away mode is on."""
        return self._device.vacation_mode_on

    @property
    def outlet_temperature(self) -> float | None:
        """Return outlet temperature, converted to metric if needed."""
        temp = self._device.outlet_temperature
        if temp is None:
            return None
        if self.hass.config.units is METRIC_SYSTEM:
            return round((temp - 32) / 1.8, 1)
        return round(temp, 1)

    @property
    def inlet_temperature(self) -> float | None:
        """Return inlet temperature, converted to metric if needed."""
        temp = self._device.inlet_temperature
        if temp is None:
            return None
        if self.hass.config.units is METRIC_SYSTEM:
            return round((temp - 32) / 1.8, 1)
        return round(temp, 1)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def extra_state_attributes(self) -> dict:
        """Return the optional device state attributes."""
        return {
            "target_temp_step": 5,
            "outlet_temperature": self.outlet_temperature,
            "inlet_temperature": self.inlet_temperature,
        }

    async def async_set_temperature(self, **kwargs) -> None:
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is not None:
            try:
                await self._device.async_set_temperature(int(target_temp))
                LOGGER.debug("Updated temperature to: %s", target_temp)
            except ValueError:
                LOGGER.error("Invalid temperature value: %s", target_temp)
        else:
            LOGGER.error("A target temperature must be provided")

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self._device.async_enable_vacation_mode()

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self._device.async_disable_vacation_mode()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set operation mode (on/off)."""
        if operation_mode in (STATE_ON, STATE_GAS):
            await self._device.async_turn_on()
        else:  # STATE_OFF
            await self._device.async_turn_off()

    async def async_turn_on(self) -> None:
        """Turn on."""
        await self.async_set_operation_mode(STATE_ON)

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.async_set_operation_mode(STATE_OFF)

    async def async_start_recirculation(self, recirculation_minutes: int = 5) -> None:
        await self._device.async_start_recirculation(recirculation_minutes)
        LOGGER.debug("Started recirculation for %s minutes", recirculation_minutes)
        self.async_write_ha_state()

    async def async_stop_recirculation(self) -> None:
        """Stop water recirculation."""
        await self._device.async_stop_recirculation()
        LOGGER.debug("Stopped recirculation")
        self.async_write_ha_state()
