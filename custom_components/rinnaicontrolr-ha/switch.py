"""Switch entities for Rinnai Control-R integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up the Rinnai switches from config entry."""
    entities: list[SwitchEntity] = []
    for device in config_entry.runtime_data.devices:
        entities.append(RinnaiRecirculationSwitch(device))
    async_add_entities(entities)


class RinnaiRecirculationSwitch(RinnaiEntity, SwitchEntity):
    """Switch to control water recirculation."""

    _attr_translation_key = "recirculation_switch"

    def __init__(self, device: RinnaiDeviceDataUpdateCoordinator) -> None:
        """Initialize the switch."""
        super().__init__("recirculation_switch", "Recirculation", device)

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.is_on:
            return "mdi:autorenew"
        return "mdi:sync-off"

    @property
    def is_on(self) -> bool | None:
        """Return true if recirculation is active."""
        return self._device.is_recirculating

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on recirculation."""
        await self._device.async_start_recirculation()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off recirculation."""
        await self._device.async_stop_recirculation()
        self.async_write_ha_state()
