"""Rinnai device object"""
import asyncio
from datetime import timedelta
from typing import Any, Dict, Optional

from aiorinnai.api import API
from aiorinnai.errors import RequestError
from aiorinnai.api import Unauthenticated
from homeassistant.exceptions import ConfigEntryAuthFailed
from async_timeout import timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle

from .const import (
    CONF_MAINT_INTERVAL_ENABLED,
    DEFAULT_MAINT_INTERVAL_ENABLED,
    DOMAIN as RINNAI_DOMAIN,
    LOGGER,
)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

def _convert_to_bool(value: Any) -> bool:
    """Convert a string 'true'/'false' to a boolean, or return the boolean value."""
    if isinstance(value, str):
        return value.lower() == 'true'
    return bool(value)

class RinnaiDeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """Rinnai device object"""

    def __init__(
        self, hass: HomeAssistant, api_client: API, device_id: str, options: Dict[str, Any]
    ):
        """Initialize the device"""
        self.hass: HomeAssistant = hass
        self.api_client: API = api_client
        self._rinnai_device_id: str = device_id
        self._manufacturer: str = "Rinnai"
        self._device_information: Optional[Dict[str, Any]] = None
        self.options = options
        super().__init__(
            hass,
            LOGGER,
            name=f"{RINNAI_DOMAIN}-{device_id}",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from device via API, following Home Assistant best practices."""
        try:
            async with timeout(10):
                device_info = await self.api_client.device.get_info(self._rinnai_device_id)
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

        # Optionally perform maintenance retrieval if enabled (outside try block)
        if self.options.get(CONF_MAINT_INTERVAL_ENABLED, False):
            try:
                await self.async_do_maintenance_retrieval()
            except Exception as error:
                LOGGER.warning("Maintenance retrieval failed: %s", error)
        else:
            LOGGER.debug("Skipping Maintenance retrieval since disabled inside of configuration")

        LOGGER.debug("Rinnai device data: %s", device_info)
        self._device_information = device_info
        return device_info

    @property
    def id(self) -> str:
        """Return Rinnai thing name"""
        return self._rinnai_device_id

    @property
    def device_name(self) -> Optional[str]:
        """Return device name."""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["device_name"]

    @property
    def manufacturer(self) -> str:
        """Return manufacturer for device"""
        return self._manufacturer

    @property
    def model(self) -> Optional[str]:
        """Return model for device"""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["model"]
        
    @property
    def firmware_version(self) -> Optional[str]:
        """Return the serial number for the device"""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["firmware"]

    @property
    def thing_name(self) -> Optional[str]:
        """Return model for device"""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["thing_name"]

    @property
    def user_uuid(self) -> Optional[str]:
        """Return model for device"""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["user_uuid"]

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature in degrees F"""
        if not self._device_information:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["domestic_temperature"])

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the current temperature in degrees F"""
        if not self._device_information:
            return None
        if self._device_information["data"]["getDevice"]["shadow"]["set_domestic_temperature"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["shadow"]["set_domestic_temperature"])

    @property
    def serial_number(self) -> Optional[str]:
        """Return the serial number for the device"""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["info"]["serial_id"]

    @property
    def last_known_state(self) -> Optional[str]:
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["activity"]["eventType"]

    @property
    def is_heating(self) -> Optional[bool]:
        if not self._device_information:
            return None
        value = self._device_information["data"]["getDevice"]["info"]["domestic_combustion"]
        return _convert_to_bool(value)

    @property
    def is_on(self) -> Optional[bool]:
        if not self._device_information:
            return None
        value = self._device_information["data"]["getDevice"]["shadow"]["set_operation_enabled"]
        return _convert_to_bool(value)

    @property
    def is_recirculating(self) -> Optional[bool]:
        if not self._device_information:
            return None
        value = self._device_information["data"]["getDevice"]["shadow"]["recirculation_enabled"]
        return _convert_to_bool(value)

    @property
    def vacation_mode_on(self) -> Optional[bool]:
        if not self._device_information:
            return None
        value = self._device_information["data"]["getDevice"]["shadow"]["schedule_holiday"]
        if value is None:
            return None
        return _convert_to_bool(value)

    @property
    def outlet_temperature(self) -> Optional[float]:
        if not self._device_information:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m02_outlet_temperature"])

    @property
    def inlet_temperature(self) -> Optional[float]:
        if not self._device_information:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m08_inlet_temperature"])

    @property
    def water_flow_rate(self) -> Optional[float]:
        """Return the current temperature in degrees F"""
        if not self._device_information:
            return None
        if self._device_information["data"]["getDevice"]["info"]["m01_water_flow_rate_raw"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m01_water_flow_rate_raw"])

    @property
    def combustion_cycles(self) -> Optional[float]:
        """Return the current temperature in degrees F"""
        if not self._device_information:
            return None
        if self._device_information["data"]["getDevice"]["info"]["m04_combustion_cycles"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m04_combustion_cycles"])

    @property
    def operation_hours(self) -> Optional[float]:
        """Return the operation hours."""
        if not self._device_information:
            return None
        if self._device_information["data"]["getDevice"]["info"]["operation_hours"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["operation_hours"])

    @property
    def pump_hours(self) -> Optional[float]:
        """Return the pump hours."""
        if not self._device_information:
            return None
        if self._device_information["data"]["getDevice"]["info"]["m19_pump_hours"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m19_pump_hours"])

    @property
    def fan_current(self) -> Optional[float]:
        """Return the fan current."""
        if not self._device_information:
            return None
        if self._device_information["data"]["getDevice"]["info"]["m09_fan_current"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m09_fan_current"])

    @property
    def fan_frequency(self) -> Optional[float]:
        """Return the fan frequency."""
        if not self._device_information:
            return None
        if self._device_information["data"]["getDevice"]["info"]["m05_fan_frequency"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m05_fan_frequency"])

    @property
    def pump_cycles(self) -> Optional[float]:
        """Return the pump cycles."""
        if not self._device_information:
            return None
        if self._device_information["data"]["getDevice"]["info"]["m20_pump_cycles"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m20_pump_cycles"])

    async def async_set_temperature(self, temperature: int) -> None:
        if not self._device_information:
            return
        try:
            await self.api_client.device.set_temperature(self._device_information["data"]["getDevice"], temperature)
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_start_recirculation(self, duration: int) -> None:
        if not self._device_information:
            return
        try:
            await self.api_client.device.start_recirculation(self._device_information["data"]["getDevice"], duration)
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_stop_recirculation(self) -> None:
        if not self._device_information:
            return
        try:
            await self.api_client.device.stop_recirculation(self._device_information["data"]["getDevice"])
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_enable_vacation_mode(self) -> None:
        if not self._device_information:
            return
        try:
            await self.api_client.device.enable_vacation_mode(self._device_information["data"]["getDevice"])
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_disable_vacation_mode(self) -> None:
        if not self._device_information:
            return
        try:
            await self.api_client.device.disable_vacation_mode(self._device_information["data"]["getDevice"])
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_turn_off(self) -> None:
        if not self._device_information:
            return
        try:
            await self.api_client.device.turn_off(self._device_information["data"]["getDevice"])
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_turn_on(self) -> None:
        if not self._device_information:
            return
        try:
            await self.api_client.device.turn_on(self._device_information["data"]["getDevice"])
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_do_maintenance_retrieval(self) -> None:
        if not self._device_information:
            return
        try:
            await self.api_client.device.do_maintenance_retrieval(self._device_information["data"]["getDevice"])
            LOGGER.debug("Rinnai Maintenance Retrieval Started")
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error
