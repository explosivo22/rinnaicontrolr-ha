"""Support for Rinnai Water Heater Monitor sensors."""
from __future__ import annotations
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    TEMP_FAHRENHEIT,
)
from homeassistant.util import Throttle

from .const import DOMAIN as RINNAI_DOMAIN
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
                RinnaiOutletTemperatureSensor(device),
                RinnaiInletTemperatureSensor(device),
            ]
        )
    async_add_entities(entities)

class RinnaiOutletTemperatureSensor(RinnaiEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_unit_of_measurement = TEMP_FAHRENHEIT

    def __init__(self, device):
        """Initialize the temperature sensor."""
        super().__init__("outlet_temperature", "Outlet Temperature", device)
        self._state: float = None

    @property
    def state(self) -> float | None:
        """Return the current temperature."""
        if self._device.outlet_temperature is None:
            return None
        return round(self._device.outlet_temperature, 1)

    @property
    def should_poll(self) -> None:
        return True

    @Throttle(timedelta(hours=1))
    async def async_update(self):
        """Get the latest data for the sensor"""
        self._device._do_maintenance_retrieval()

class RinnaiInletTemperatureSensor(RinnaiEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_unit_of_measurement = TEMP_FAHRENHEIT

    def __init__(self, device):
        """Initialize the temperature sensor."""
        super().__init__("inlet_temperature", "Inlet Temperature", device)
        self._state: float = None

    @property
    def state(self) -> float | None:
        """Return the current temperature."""
        if self._device.inlet_temperature is None:
            return None
        return round(self._device.inlet_temperature, 1)

    @property
    def should_poll(self) -> None:
        return True