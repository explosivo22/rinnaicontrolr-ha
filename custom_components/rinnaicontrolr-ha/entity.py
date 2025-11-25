"""Base entity class for Rinnai entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN as RINNAI_DOMAIN

if TYPE_CHECKING:
    from .device import RinnaiDeviceDataUpdateCoordinator


class RinnaiEntity(CoordinatorEntity["RinnaiDeviceDataUpdateCoordinator"]):
    """Base class for Rinnai entities.

    Uses CoordinatorEntity for automatic updates and availability tracking.
    All Rinnai entities inherit from this class to share common functionality.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        entity_type: str,
        name: str,
        device: RinnaiDeviceDataUpdateCoordinator,
    ) -> None:
        """Initialize Rinnai entity.

        Args:
            entity_type: Type identifier for unique_id generation.
            name: Display name for the entity.
            device: The device coordinator for this entity.
        """
        super().__init__(device)
        self._attr_name = name
        self._attr_unique_id = f"{device.id}_{entity_type}"
        self._device: RinnaiDeviceDataUpdateCoordinator = device

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for device registry."""
        return DeviceInfo(
            identifiers={(RINNAI_DOMAIN, self._device.id)},
            manufacturer=self._device.manufacturer,
            model=self._device.model,
            name=self._device.device_name,
            sw_version=self._device.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        Combines coordinator availability with device-specific availability.
        """
        return super().available and self._device.available
