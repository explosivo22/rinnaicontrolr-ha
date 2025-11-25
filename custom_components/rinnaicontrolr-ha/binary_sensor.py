"""Support for Rinnai Water Heater binary sensors."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as RINNAI_DOMAIN
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Rinnai binary sensors from config entry."""
    devices: list[RinnaiDeviceDataUpdateCoordinator] = hass.data[RINNAI_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    entities: list[BinarySensorEntity] = []
    for device in devices:
        entities.extend([
            RinnaiIsRecirculatingBinarySensor(device),
            RinnaiIsHeatingBinarySensor(device),
        ])
    async_add_entities(entities)

class RinnaiIsRecirculatingBinarySensor(RinnaiEntity, BinarySensorEntity):
    """Binary sensor that reports if the water heater is recirculating."""

    def __init__(self, device: RinnaiDeviceDataUpdateCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__("recirculation", "Water Heater Recirculation", device)
        
    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.is_on:
            return "mdi:autorenew"
        return "mdi:circle-off-outline"

    @property
    def is_on(self) -> bool:
        """Return true if the Rinnai device is recirculating water."""
        return self._device.is_recirculating

class RinnaiIsHeatingBinarySensor(RinnaiEntity, BinarySensorEntity):
    """Binary sensor that reports if the water heater is heating."""

    def __init__(self, device: RinnaiDeviceDataUpdateCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__("water_heater_heating", f"{device.device_name} Water Heater Heating", device)
        
    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.is_on:
            return "mdi:fire"
        return "mdi:fire-off"

    @property
    def is_on(self) -> bool:
        """Return true if the Rinnai device is heating water."""
        return self._device.is_heating