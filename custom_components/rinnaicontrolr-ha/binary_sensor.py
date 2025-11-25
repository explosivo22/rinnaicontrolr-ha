"""Support for Rinnai Water Heater binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RinnaiConfigEntry
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RinnaiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Rinnai binary sensors from config entry."""
    entities: list[BinarySensorEntity] = []
    for device in config_entry.runtime_data.devices:
        entities.extend(
            [
                RinnaiIsRecirculatingBinarySensor(device),
                RinnaiIsHeatingBinarySensor(device),
            ]
        )
    async_add_entities(entities)


class RinnaiIsRecirculatingBinarySensor(RinnaiEntity, BinarySensorEntity):
    """Binary sensor that reports if the water heater is recirculating."""

    _attr_translation_key = "recirculation"

    def __init__(self, device: RinnaiDeviceDataUpdateCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__("recirculation", "Recirculation", device)

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.is_on:
            return "mdi:autorenew"
        return "mdi:circle-off-outline"

    @property
    def is_on(self) -> bool | None:
        """Return true if the Rinnai device is recirculating water."""
        return self._device.is_recirculating


class RinnaiIsHeatingBinarySensor(RinnaiEntity, BinarySensorEntity):
    """Binary sensor that reports if the water heater is heating."""

    _attr_translation_key = "water_heater_heating"

    def __init__(self, device: RinnaiDeviceDataUpdateCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__("water_heater_heating", "Heating", device)

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.is_on:
            return "mdi:fire"
        return "mdi:fire-off"

    @property
    def is_on(self) -> bool | None:
        """Return true if the Rinnai device is heating water."""
        return self._device.is_heating
