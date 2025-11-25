"""Switch entities for Rinnai Control-R integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RinnaiConfigEntry
from .const import (
    CONF_RECIRCULATION_DURATION,
    DEFAULT_RECIRCULATION_DURATION,
    LOGGER,
)
from .device import RinnaiDeviceDataUpdateCoordinator
from .entity import RinnaiEntity

# Limit concurrent updates per platform
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RinnaiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Rinnai switches from config entry."""
    LOGGER.debug("Setting up Rinnai switch entities")
    entities: list[SwitchEntity] = []
    for device in config_entry.runtime_data.devices:
        entities.append(RinnaiRecirculationSwitch(device, config_entry))
    async_add_entities(entities)
    LOGGER.debug("Added %d switch entities", len(entities))


class RinnaiRecirculationSwitch(RinnaiEntity, SwitchEntity):
    """Switch to control water recirculation.

    Uses optimistic updates for responsive UI - the switch state is updated
    immediately when toggled, then verified on the next coordinator poll.
    """

    _attr_translation_key = "recirculation_switch"

    def __init__(
        self, device: RinnaiDeviceDataUpdateCoordinator, config_entry: RinnaiConfigEntry
    ) -> None:
        """Initialize the switch."""
        super().__init__("recirculation_switch", "Recirculation", device)
        self._config_entry = config_entry
        self._optimistic_state: bool | None = None

    @property
    def _recirculation_duration(self) -> int:
        """Get the configured recirculation duration in minutes."""
        return self._config_entry.options.get(
            CONF_RECIRCULATION_DURATION, DEFAULT_RECIRCULATION_DURATION
        )

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.is_on:
            return "mdi:autorenew"
        return "mdi:sync-off"

    @property
    def is_on(self) -> bool | None:
        """Return true if recirculation is active.

        Uses optimistic state if set, otherwise falls back to device state.
        """
        if self._optimistic_state is not None:
            return self._optimistic_state
        return self._device.is_recirculating

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Clear optimistic state when coordinator updates with real device state.
        """
        self._optimistic_state = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on recirculation with configured duration."""
        duration = self._recirculation_duration
        LOGGER.info(
            "Starting recirculation on %s for %d minutes",
            self._device.device_name,
            duration,
        )
        # Set optimistic state immediately for responsive UI
        self._optimistic_state = True
        self.async_write_ha_state()

        await self._device.async_start_recirculation(duration)
        # Request refresh to eventually sync with real device state
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off recirculation."""
        LOGGER.info("Stopping recirculation on %s", self._device.device_name)
        # Set optimistic state immediately for responsive UI
        self._optimistic_state = False
        self.async_write_ha_state()

        await self._device.async_stop_recirculation()
        # Request refresh to eventually sync with real device state
        await self.coordinator.async_request_refresh()
