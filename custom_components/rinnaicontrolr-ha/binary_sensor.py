"""Support for Rinnai Water Heater binary sensors."""
from __future__ import annotations
from distutils.util import strtobool

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)

from .const import DOMAIN as RINNAI_DOMAIN, COORDINATOR
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Flo sensors from config entry."""
    device = hass.data[RINNAI_DOMAIN][config_entry.entry_id][COORDINATOR]
    entities = []
    entities.append(RinnaiIsRecirculatingBinarySensor(device))
    entities.append(RinnaiIsHeatingBinarySensor(device))
    async_add_entities(entities)

class RinnaiIsRecirculatingBinarySensor(RinnaiEntity, BinarySensorEntity):
    """Binary sensor that reports if water is detected (for leak detectors)."""

    def __init__(self, device):
        """Initialize the binary sensors."""
        super().__init__("recirculation", "Water Heater Recirculation", device)
        
    @property
    def icon(self):
        """Return the icon"""
        if self.is_on:
            return "mdi:autorenew"
        return "mdi:circle-off-outline"

    @property
    def is_on(self):
        """Return true if the Rinnai device is recirculating water."""
        return self._device.is_recirculating

class RinnaiIsHeatingBinarySensor(RinnaiEntity, BinarySensorEntity):
    """Binary sensor that reports if water is detected (for leak detectors)."""

    def __init__(self, device):
        """Initialize the binary sensors."""
        super().__init__("water_heater_heating", f"{device.device_name} Water Heater Heating", device)
        
    @property
    def icon(self):
        """Return the icon"""
        if self.is_on:
            return "mdi:fire"
        return "mdi:fire-off"

    @property
    def is_on(self):
        """Return true if the Rinnai device is recirculating water."""
        return self._device.is_heating