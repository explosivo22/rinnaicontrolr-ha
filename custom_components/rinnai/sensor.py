"""Support for Rinnai Water Heater Monitor sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfFrequency,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RinnaiConfigEntry
from .entity import RinnaiEntity

if TYPE_CHECKING:
    from .device import RinnaiDeviceDataUpdateCoordinator

# Limit concurrent updates per platform
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RinnaiSensorEntityDescription(SensorEntityDescription):
    """Describes a Rinnai sensor entity."""

    value_fn: Callable[[RinnaiDeviceDataUpdateCoordinator], float | None]
    value_multiplier: float = 1.0
    round_digits: int = 1
    # Whether this is a diagnostic sensor (less commonly used)
    is_diagnostic: bool = False
    # Whether to disable this entity by default
    disabled_by_default: bool = False


SENSOR_DESCRIPTIONS: tuple[RinnaiSensorEntityDescription, ...] = (
    RinnaiSensorEntityDescription(
        key="outlet_temperature",
        translation_key="outlet_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        value_fn=lambda device: device.outlet_temperature,
    ),
    RinnaiSensorEntityDescription(
        key="inlet_temperature",
        translation_key="inlet_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        value_fn=lambda device: device.inlet_temperature,
    ),
    RinnaiSensorEntityDescription(
        key="water_flow_rate",
        translation_key="water_flow_rate",
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="gpm",
        value_fn=lambda device: device.water_flow_rate,
        value_multiplier=0.1,
    ),
    RinnaiSensorEntityDescription(
        key="combustion_cycles",
        translation_key="combustion_cycles",
        icon="mdi:fire-circle",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="cycles",
        value_fn=lambda device: device.combustion_cycles,
        value_multiplier=100.0,
        round_digits=0,
        is_diagnostic=True,
        disabled_by_default=True,
    ),
    RinnaiSensorEntityDescription(
        key="operation_hours",
        translation_key="operation_hours",
        icon="mdi:home-lightning-bolt-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="h",
        value_fn=lambda device: device.operation_hours,
        value_multiplier=100.0,
        round_digits=0,
        is_diagnostic=True,
    ),
    RinnaiSensorEntityDescription(
        key="pump_hours",
        translation_key="pump_hours",
        icon="mdi:pump",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement="h",
        value_fn=lambda device: device.pump_hours,
        value_multiplier=100.0,
        round_digits=0,
        is_diagnostic=True,
    ),
    RinnaiSensorEntityDescription(
        key="pump_cycles",
        translation_key="pump_cycles",
        icon="mdi:heat-pump-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="cycles",
        value_fn=lambda device: device.pump_cycles,
        value_multiplier=100.0,
        round_digits=0,
        is_diagnostic=True,
        disabled_by_default=True,
    ),
    RinnaiSensorEntityDescription(
        key="fan_current",
        translation_key="fan_current",
        icon="mdi:fan-auto",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        value_fn=lambda device: device.fan_current,
        value_multiplier=10.0,
        is_diagnostic=True,
        disabled_by_default=True,
    ),
    RinnaiSensorEntityDescription(
        key="fan_frequency",
        translation_key="fan_frequency",
        icon="mdi:fan-chevron-up",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        value_fn=lambda device: device.fan_frequency,
        is_diagnostic=True,
        disabled_by_default=True,
    ),
    RinnaiSensorEntityDescription(
        key="water_flow_control_position",
        translation_key="water_flow_control_position",
        icon="mdi:valve",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        value_fn=lambda device: device.water_flow_control_position,
        is_diagnostic=True,
        disabled_by_default=True,
    ),
    RinnaiSensorEntityDescription(
        key="heat_exchanger_outlet_temperature",
        translation_key="heat_exchanger_outlet_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        value_fn=lambda device: device.heat_exchanger_outlet_temperature,
        is_diagnostic=True,
        disabled_by_default=True,
    ),
    RinnaiSensorEntityDescription(
        key="bypass_servo_position",
        translation_key="bypass_servo_position",
        icon="mdi:cog-transfer",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        value_fn=lambda device: device.bypass_servo_position,
        is_diagnostic=True,
        disabled_by_default=True,
    ),
    RinnaiSensorEntityDescription(
        key="outdoor_antifreeze_temperature",
        translation_key="outdoor_antifreeze_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        value_fn=lambda device: device.outdoor_antifreeze_temperature,
        is_diagnostic=True,
        disabled_by_default=True,
    ),
    RinnaiSensorEntityDescription(
        key="exhaust_temperature",
        translation_key="exhaust_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        value_fn=lambda device: device.exhaust_temperature,
        is_diagnostic=True,
        disabled_by_default=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RinnaiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Rinnai sensors from config entry."""
    # Store callback for dynamic device support
    from homeassistant.const import Platform

    config_entry.runtime_data.entity_adders[Platform.SENSOR] = async_add_entities

    entities: list[RinnaiSensor] = [
        RinnaiSensor(device, description)
        for device in config_entry.runtime_data.devices
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class RinnaiSensor(RinnaiEntity, SensorEntity):
    """Rinnai sensor entity."""

    entity_description: RinnaiSensorEntityDescription

    def __init__(
        self,
        device: RinnaiDeviceDataUpdateCoordinator,
        description: RinnaiSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(description.key, device)
        self.entity_description = description

        # Set entity category for diagnostic sensors
        if description.is_diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        # Disable noisy sensors by default
        if description.disabled_by_default:
            self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        value = self.entity_description.value_fn(self._device)
        if value is None:
            return None
        # Apply multiplier and round
        adjusted_value = value * self.entity_description.value_multiplier
        return round(adjusted_value, self.entity_description.round_digits)
