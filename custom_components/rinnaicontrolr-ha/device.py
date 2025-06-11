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
        self._listeners = []
        super().__init__(
            hass,
            LOGGER,
            name=f"{RINNAI_DOMAIN}-{device_id}",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self) -> None:
        """Update data via library"""
        try:
            async with timeout(10):
                await asyncio.gather(
                    self._update_device()
                )
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    @property
    def id(self) -> str:
        """Return Rinnai thing name"""
        return self._rinnai_device_id

    @property
    def device_name(self) -> str:
        """Return device name."""
        return self._device_information["data"]["getDevice"]["device_name"]

    @property
    def manufacturer(self) -> str:
        """Return manufacturer for device"""
        return self._manufacturer

    @property
    def model(self) -> str:
        """Return model for device"""
        return self._device_information["data"]["getDevice"]["model"]
        
    @property
    def firmware_version(self) -> str:
        """Return the serial number for the device"""
        return self._device_information["data"]["getDevice"]["firmware"]

    @property
    def thing_name(self) -> str:
        """Return model for device"""
        return self._device_information["data"]["getDevice"]["thing_name"]

    @property
    def user_uuid(self) -> str:
        """Return model for device"""
        return self._device_information["data"]["getDevice"]["user_uuid"]

    @property
    def current_temperature(self) -> float:
        """Return the current temperature in degrees F"""
        return float(self._device_information["data"]["getDevice"]["info"]["domestic_temperature"])

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the current temperature in degrees F"""
        if self._device_information["data"]["getDevice"]["shadow"]["set_domestic_temperature"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["shadow"]["set_domestic_temperature"])

    @property
    def serial_number(self) -> str:
        """Return the serial number for the device"""
        return self._device_information["data"]["getDevice"]["info"]["serial_id"]

    @property
    def last_known_state(self) -> str:
        return self._device_information["data"]["getDevice"]["activity"]["eventType"]

    @property
    def is_heating(self) -> bool:
        value = self._device_information["data"]["getDevice"]["info"]["domestic_combustion"]
        return _convert_to_bool(value)

    @property
    def is_on(self) -> bool:
        value = self._device_information["data"]["getDevice"]["shadow"]["set_operation_enabled"]
        return _convert_to_bool(value)

    @property
    def is_recirculating(self) -> bool:
        value = self._device_information["data"]["getDevice"]["shadow"]["recirculation_enabled"]
        return _convert_to_bool(value)

    @property
    def vacation_mode_on(self) -> Optional[bool]:
        value = self._device_information["data"]["getDevice"]["shadow"]["schedule_holiday"]
        if value is None:
            return None
        return _convert_to_bool(value)

    @property
    def outlet_temperature(self) -> float:
        return float(self._device_information["data"]["getDevice"]["info"]["m02_outlet_temperature"])

    @property
    def inlet_temperature(self) -> float:
        return float(self._device_information["data"]["getDevice"]["info"]["m08_inlet_temperature"])

    @property
    def water_flow_rate(self) -> Optional[float]:
        """Return the current temperature in degrees F"""
        if self._device_information["data"]["getDevice"]["info"]["m01_water_flow_rate_raw"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m01_water_flow_rate_raw"])

    @property
    def combustion_cycles(self) -> Optional[float]:
        """Return the current temperature in degrees F"""
        if self._device_information["data"]["getDevice"]["info"]["m04_combustion_cycles"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m04_combustion_cycles"])

    @property
    def operation_hours(self) -> Optional[float]:
        """Return the operation hours."""
        if self._device_information["data"]["getDevice"]["info"]["operation_hours"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["operation_hours"])

    @property
    def pump_hours(self) -> Optional[float]:
        """Return the pump hours."""
        if self._device_information["data"]["getDevice"]["info"]["m19_pump_hours"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m19_pump_hours"])

    @property
    def fan_current(self) -> Optional[float]:
        """Return the fan current."""
        if self._device_information["data"]["getDevice"]["info"]["m09_fan_current"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m09_fan_current"])

    @property
    def fan_frequency(self) -> Optional[float]:
        """Return the fan frequency."""
        if self._device_information["data"]["getDevice"]["info"]["m05_fan_frequency"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m05_fan_frequency"])

    @property
    def pump_cycles(self) -> Optional[float]:
        """Return the pump cycles."""
        if self._device_information["data"]["getDevice"]["info"]["m20_pump_cycles"] is None:
            return None
        return float(self._device_information["data"]["getDevice"]["info"]["m20_pump_cycles"])

    async def async_set_temperature(self, temperature: int) -> None:
        try:
            await self.api_client.device.set_temperature(self._device_information["data"]["getDevice"], temperature)
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_start_recirculation(self, duration: int) -> None:
        try:
            await self.api_client.device.start_recirculation(self._device_information["data"]["getDevice"], duration)
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_stop_recirculation(self) -> None:
        try:
            await self.api_client.device.stop_recirculation(self._device_information["data"]["getDevice"])
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_enable_vacation_mode(self) -> None:
        try:
            await self.api_client.device.enable_vacation_mode(self._device_information["data"]["getDevice"])
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_disable_vacation_mode(self) -> None:
        try:
            await self.api_client.device.disable_vacation_mode(self._device_information["data"]["getDevice"])
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_turn_off(self) -> None:
        try:
            await self.api_client.device.turn_off(self._device_information["data"]["getDevice"])
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def async_turn_on(self) -> None:
        try:
            await self.api_client.device.turn_on(self._device_information["data"]["getDevice"])
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_do_maintenance_retrieval(self) -> None:
        try:
            await self.api_client.device.do_maintenance_retrieval(self._device_information["data"]["getDevice"])
            LOGGER.debug("Rinnai Maintenance Retrieval Started")
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error

    async def _update_device(self, *_) -> None:
        """Update the device information from the API"""
        self._device_information = await self.api_client.device.get_info(
            self._rinnai_device_id
        )

        if self.options[CONF_MAINT_INTERVAL_ENABLED]:
            await self.async_do_maintenance_retrieval()
        else:
            LOGGER.debug("Skipping Maintenance retrieval since disabled inside of configuration")
        
        LOGGER.debug("Rinnai device data: %s", self._device_information)