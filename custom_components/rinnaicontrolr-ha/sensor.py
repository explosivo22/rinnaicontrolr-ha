"""Support for Rinnai Water Heater Monitor sensors."""
from __future__ import annotations
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    TEMP_FAHRENHEIT,
    TEMP_CELSIUS,
)
from homeassistant.util import Throttle

from .const import DOMAIN as RINNAI_DOMAIN, CONF_UNIT
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Rinnai sensors from config entry."""
    devices: list[RinnaiDeviceDataUpdateCoordinator] = hass.data[RINNAI_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    entities = []
    for device in devices:
        entities.extend(
            [
                RinnaiOutletTemperatureSensor(device, config_entry.options),
                RinnaiInletTemperatureSensor(device, config_entry.options),
            ]
        )
    async_add_entities(entities)

class RinnaiOutletTemperatureSensor(RinnaiEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE

    def __init__(self, device, options):
        """Initialize the temperature sensor."""
        super().__init__("outlet_temperature", f"{device.device_name} Outlet Temperature", device)
        self._state: float = None
        self.options = options

    @property
    def unit_of_measurement(self) -> str | None:
        if self.options[CONF_UNIT] == "celsius":
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def state(self) -> float | None:
        """Return the current temperature."""
        if self._device.outlet_temperature is None:
            return None
        return round(self._device.outlet_temperature, 1)

class RinnaiInletTemperatureSensor(RinnaiEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE

    def __init__(self, device, options):
        """Initialize the temperature sensor."""
        super().__init__("inlet_temperature", f"{device.device_name} Inlet Temperature", device)
        self._state: float = None
        self.options = options

    @property
    def unit_of_measurement(self) -> str | None:
        if self.options[CONF_UNIT] == "celsius":
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def state(self) -> float | None:
        """Return the current temperature."""
        if self._device.inlet_temperature is None:
            return None
        return round(self._device.inlet_temperature, 1)