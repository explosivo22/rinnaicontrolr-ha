"""Support for Rinnai Water Heater Monitor sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    ELECTRIC_CURRENT_MILLIAMPERE,
    FREQUENCY_HERTZ,
    UnitOfTemperature
)

from homeassistant.components.sensor import (
    SensorStateClass,
    SensorDeviceClass
)

from .const import DOMAIN as RINNAI_DOMAIN, CONF_UNIT
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

GAUGE_ICON = "mdi:gauge"
COMBUSTION_ICON = "mdi:fire-circle"
OPERATION_ICON = "mdi:home-lightning-bolt-outline"
PUMP_ICON = "mdi:pump"
PUMP_CYCLES_ICON = "mdi:heat-pump-outline"
FAN_CURRENT_ICON = "mdi:fan-auto"
FAN_FREQUENCY_ICON = "mdi:fan-chevron-up"

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
                RinnaiWaterFlowRateSensor(device),
                RinnaiCombustionCyclesSensor(device),
                RinnaiOperationHoursSensor(device),
                RinnaiPumpHoursSensor(device),
                RinnaiPumpCyclesSensor(device),
                RinnaiFanCurrentSensor(device),
                RinnaiFanFrequencySensor(device),
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
    def device_class(self):
        """Return the device class of the sensor."""
        return SensorDeviceClass.TEMPERATURE

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str | None:
        return UnitOfTemperature.FAHRENHEIT

    @property
    def native_value(self):
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
    def device_class(self):
        """Return the device class of the sensor."""
        return SensorDeviceClass.TEMPERATURE

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str | None:
        return UnitOfTemperature.FAHRENHEIT

    @property
    def native_value(self):
        """Return the current temperature."""
        if self._device.inlet_temperature is None:
            return None
        return round(self._device.inlet_temperature, 1)

class RinnaiWaterFlowRateSensor(RinnaiEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_icon = GAUGE_ICON
    _attr_native_unit_of_measurement = "gpm"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, device):
        """Initialize the temperature sensor."""
        super().__init__("water_flow_rate", f"{device.device_name} Water Flow Rate", device)
        self._state: float = None

    @property
    def native_value(self):
        """Return the current temperature."""
        if self._device.water_flow_rate is None:
            return None
        return round(self._device.water_flow_rate * 0.1, 1)

class RinnaiCombustionCyclesSensor(RinnaiEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_icon = COMBUSTION_ICON
    _attr_native_unit_of_measurement = "cycles"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, device):
        """Initialize the temperature sensor."""
        super().__init__("combustion_cycles", f"{device.device_name} Combustion Cycles x100", device)
        self._state: float = None

    @property
    def native_value(self):
        """Return the current temperature."""
        if self._device.combustion_cycles is None:
            return None
        return round(self._device.combustion_cycles, 1)

class RinnaiOperationHoursSensor(RinnaiEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_icon = OPERATION_ICON
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, device):
        """Initialize the temperature sensor."""
        super().__init__("operation_hours", f"{device.device_name} Operation Hours x100", device)
        self._state: float = None

    @property
    def native_value(self):
        """Return the current temperature."""
        if self._device.operation_hours is None:
            return None
        return round(self._device.operation_hours, 1)

class RinnaiPumpHoursSensor(RinnaiEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_icon = PUMP_ICON
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, device):
        """Initialize the temperature sensor."""
        super().__init__("pump_hours", f"{device.device_name} Pump Hours x100", device)
        self._state: float = None

    @property
    def native_value(self):
        """Return the current temperature."""
        if self._device.pump_hours is None:
            return None
        return round(self._device.pump_hours, 1)

class RinnaiPumpCyclesSensor(RinnaiEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_icon = PUMP_CYCLES_ICON
    _attr_native_unit_of_measurement = "cycles"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, device):
        """Initialize the temperature sensor."""
        super().__init__("pump_cycles", f"{device.device_name} Pump Cycles x100", device)
        self._state: float = None

    @property
    def native_value(self):
        """Return the current temperature."""
        if self._device.pump_cycles is None:
            return None
        return round(self._device.pump_cycles, 1)

class RinnaiFanCurrentSensor(RinnaiEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_icon = FAN_CURRENT_ICON
    _attr_native_unit_of_measurement = ELECTRIC_CURRENT_MILLIAMPERE
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, device):
        """Initialize the temperature sensor."""
        super().__init__("fan_current", f"{device.device_name} Fan Current x10", device)
        self._state: float = None

    @property
    def native_value(self):
        """Return the current temperature."""
        if self._device.fan_current is None:
            return None
        return round(self._device.fan_current, 1)

class RinnaiFanFrequencySensor(RinnaiEntity, SensorEntity):
    """Monitors the temperature."""

    _attr_icon = FAN_FREQUENCY_ICON
    _attr_native_unit_of_measurement = FREQUENCY_HERTZ
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT

    def __init__(self, device):
        """Initialize the temperature sensor."""
        super().__init__("fan_frequency", f"{device.device_name} Fan Frequency", device)
        self._state: float = None

    @property
    def native_value(self):
        """Return the current temperature."""
        if self._device.fan_frequency is None:
            return None
        return round(self._device.fan_frequency, 1)