"""Support for Rinnai Water Heater Monitor sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    TEMP_FAHRENHEIT,
)

from .const import DOMAIN as RINNAI_DOMAIN
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

WATER_ICON = "mdi:water"
GAUGE_ICON = "mdi:gauge"
NAME_DAILY_USAGE = "Today's Water Usage"
NAME_CURRENT_SYSTEM_MODE = "Current System Mode"
NAME_FLOW_RATE = "Water Flow Rate"
NAME_WATER_TEMPERATURE = "Water Temperature"
NAME_AIR_TEMPERATURE = "Temperature"
NAME_WATER_PRESSURE = "Water Pressure"
NAME_HUMIDITY = "Humidity"
NAME_BATTERY = "Battery"


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