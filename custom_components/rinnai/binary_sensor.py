"""Support for Rinnai Water Heater binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
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
class RinnaiBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Rinnai binary sensor entity."""

    value_fn: Callable[[RinnaiDeviceDataUpdateCoordinator], bool | None]
    icon_on: str
    icon_off: str


BINARY_SENSOR_DESCRIPTIONS: tuple[RinnaiBinarySensorEntityDescription, ...] = (
    RinnaiBinarySensorEntityDescription(
        key="water_heater_heating",
        translation_key="water_heater_heating",
        value_fn=lambda device: device.is_heating,
        icon_on="mdi:fire",
        icon_off="mdi:fire-off",
    ),
    RinnaiBinarySensorEntityDescription(
        key="recirculation",
        translation_key="recirculation",
        value_fn=lambda device: device.is_recirculating,
        icon_on="mdi:sync",
        icon_off="mdi:sync-off",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RinnaiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Rinnai binary sensors from config entry."""
    # Store callback for dynamic device support
    from homeassistant.const import Platform

    config_entry.runtime_data.entity_adders[Platform.BINARY_SENSOR] = async_add_entities

    entities: list[RinnaiBinarySensor] = [
        RinnaiBinarySensor(device, description)
        for device in config_entry.runtime_data.devices
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class RinnaiBinarySensor(RinnaiEntity, BinarySensorEntity):
    """Rinnai binary sensor entity."""

    entity_description: RinnaiBinarySensorEntityDescription

    def __init__(
        self,
        device: RinnaiDeviceDataUpdateCoordinator,
        description: RinnaiBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(description.key, device)
        self.entity_description = description

    @property
    def icon(self) -> str:
        """Return the icon based on state."""
        if self.is_on:
            return self.entity_description.icon_on
        return self.entity_description.icon_off

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(self._device)
