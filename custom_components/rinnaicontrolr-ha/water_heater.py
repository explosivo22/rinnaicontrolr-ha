"""Water Heater entity for Rinnai Control-R integration."""

from __future__ import annotations

from typing import Any

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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from . import RinnaiConfigEntry
from .const import LOGGER
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

STATE_IDLE = "idle"

# Limit concurrent updates per platform
PARALLEL_UPDATES = 1

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

# Temperature limits in Fahrenheit
MIN_TEMP_F = 110
MAX_TEMP_F = 140
TEMP_STEP = 5


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RinnaiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Rinnai Water heater from config entry."""
    LOGGER.debug("Setting up Rinnai water heater entities")
    entities = [
        RinnaiWaterHeater(device) for device in config_entry.runtime_data.devices
    ]
    async_add_entities(entities)
    LOGGER.debug("Added %d water heater entities", len(entities))

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
    """Water Heater entity for a Rinnai Device."""

    _attr_operation_list = OPERATION_LIST
    _attr_supported_features = (
        WaterHeaterEntityFeature.AWAY_MODE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
    )
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = float(MIN_TEMP_F)
    _attr_max_temp = float(MAX_TEMP_F)
    _attr_target_temperature_step = float(TEMP_STEP)
    _attr_translation_key = "water_heater"

    def __init__(self, device: RinnaiDeviceDataUpdateCoordinator) -> None:
        """Initialize the water heater."""
        super().__init__("water_heater", "Water Heater", device)

    @property
    def current_operation(self) -> str:
        """Return current operation."""
        if self._device.is_heating:
            return STATE_GAS
        elif self._device.is_on:
            return STATE_IDLE
        return STATE_OFF

    @property
    def icon(self) -> str:
        """Return the icon to use for the water heater."""
        return "mdi:water-boiler"

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.target_temperature

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return whether away mode is on."""
        return self._device.vacation_mode_on

    @property
    def outlet_temperature(self) -> float | None:
        """Return outlet temperature, converted to system units if needed."""
        temp = self._device.outlet_temperature
        if temp is None:
            return None
        # Convert if system uses metric
        if self.hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS:
            return round(
                TemperatureConverter.convert(
                    temp, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
                ),
                1,
            )
        return round(temp, 1)

    @property
    def inlet_temperature(self) -> float | None:
        """Return inlet temperature, converted to system units if needed."""
        temp = self._device.inlet_temperature
        if temp is None:
            return None
        # Convert if system uses metric
        if self.hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS:
            return round(
                TemperatureConverter.convert(
                    temp, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
                ),
                1,
            )
        return round(temp, 1)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional device state attributes."""
        return {
            "outlet_temperature": self.outlet_temperature,
            "inlet_temperature": self.inlet_temperature,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            LOGGER.warning("async_set_temperature called without target temperature")
            return

        # Validate temperature range
        if not (MIN_TEMP_F <= target_temp <= MAX_TEMP_F):
            raise ServiceValidationError(
                f"Temperature must be between {MIN_TEMP_F}°F and {MAX_TEMP_F}°F, "
                f"got {target_temp}°F"
            )

        LOGGER.info(
            "Setting target temperature to %s°F on %s",
            target_temp,
            self._device.device_name,
        )
        await self._device.async_set_temperature(int(target_temp))
        LOGGER.debug("Temperature update completed for %s", self._device.device_name)

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        LOGGER.info("Enabling away mode on %s", self._device.device_name)
        await self._device.async_enable_vacation_mode()

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        LOGGER.info("Disabling away mode on %s", self._device.device_name)
        await self._device.async_disable_vacation_mode()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set operation mode (on/off)."""
        LOGGER.info(
            "Setting operation mode to '%s' on %s",
            operation_mode,
            self._device.device_name,
        )
        if operation_mode in (STATE_ON, STATE_GAS):
            await self._device.async_turn_on()
        else:  # STATE_OFF
            await self._device.async_turn_off()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.async_set_operation_mode(STATE_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.async_set_operation_mode(STATE_OFF)

    async def async_start_recirculation(self, recirculation_minutes: int = 5) -> None:
        """Start water recirculation via service call."""
        LOGGER.info(
            "Starting recirculation for %d minutes on %s (service call)",
            recirculation_minutes,
            self._device.device_name,
        )
        await self._device.async_start_recirculation(recirculation_minutes)
        # Request coordinator refresh to get updated state from device
        await self.coordinator.async_request_refresh()

    async def async_stop_recirculation(self) -> None:
        """Stop water recirculation."""
        LOGGER.info(
            "Stopping recirculation on %s (service call)", self._device.device_name
        )
        await self._device.async_stop_recirculation()
        # Request coordinator refresh to get updated state from device
        await self.coordinator.async_request_refresh()
