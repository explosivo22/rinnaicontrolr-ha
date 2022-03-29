"""Rinnai device object"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from distutils.util import strtobool

from aiorinnai.api import API
from aiorinnai.errors import RequestError
from async_timeout import timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util
from homeassistant.util import Throttle

from .const import DOMAIN as RINNAI_DOMAIN, LOGGER

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

class RinnaiDeviceDataUpdateCoordinator(DataUpdateCoordinator):
	"""Rinnai device object"""

	def __init__(
		self, hass: HomeAssistant, api_client: API, device_id: str
	):
		"""Initialize the device"""
		self.hass: HomeAssistantType = hass
		self.api_client: API = api_client
		self._rinnai_device_id: str = device_id
		self._manufacturer: str = "Rinnai"
		self._device_information: Optional[Dict[str, Any]] | None = None
		super().__init__(
			hass,
			LOGGER,
			name=f"{RINNAI_DOMAIN}-{device_id}",
			update_interval=timedelta(seconds=60),
		)

	async def _async_update_data(self):
		"""Update data via library"""
		try:
			async with timeout(10):
				await asyncio.gather(
					*[self._update_device()]
				)
		except (RequestError) as error:
			raise UpdateFailed(error) from error
	
	@property
	def id(self) -> str:
		"""Return Rinnai thing name"""
		return self._rinnai_device_id

	@property
	def device_name(self) -> str:
		"""Return device name."""
		return f"{self.manufacturer} {self.model}"

	@property
	def should_poll(self):
		return True

	@property
	def manufacturer(self) -> str:
		"""Return manufacturer for device"""
		return self._manufacturer

	@property
	def model(self) -> str:
		"""Return model for device"""
		return self._device_information["data"]["getDevice"]["model"]

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
	def target_temperature(self) -> float:
		"""Return the current temperature in degrees F"""
		if self._device_information["data"]["getDevice"]["shadow"]["set_domestic_temperature"] is not None:
			return float(self._device_information["data"]["getDevice"]["shadow"]["set_domestic_temperature"])
		return float(self._device_information["data"]["getDevice"]["info"]["domestic_temperature"])

	@property
	def serial_number(self) -> str:
		"""Return the serial number for the device"""
		return self._device_information["data"]["getDevice"]["info"]["serial_id"]

	@property
	def last_known_state(self) -> str:
		return self._device_information["data"]["getDevice"]["activity"]["eventType"]

	@property
	def is_heating(self) -> bool:
		return strtobool(str(self._device_information["data"]["getDevice"]["info"]["domestic_combustion"]))

	@property
	def is_recirculating(self) -> bool:
		return strtobool(str(self._device_information["data"]["getDevice"]["shadow"]["recirculation_enabled"]))

	@property
	def outlet_temperature(self) -> float:
		return float(self._device_information["data"]["getDevice"]["info"]["m02_outlet_temperature"])

	@property
	def inlet_temperature(self) -> float:
		return float(self._device_information["data"]["getDevice"]["info"]["m08_inlet_temperature"])

	@property
	def vacation_mode_on(self) -> bool:
		return strtobool(str(self._device_information["data"]["getDevice"]["shadow"]["schedule_holiday"]))

	async def async_set_temperature(self, temperature: int):
		await self.api_client.device.set_temperature(self._device_information["data"]["getDevice"], temperature)

	async def async_start_recirculation(self, duration: int):
		await self.api_client.device.start_recirculation(self._device_information["data"]["getDevice"], duration)

	async def async_stop_recirculation(self):
		await self.api_client.device.stop_recirculation(self._device_information["data"]["getDevice"])

	@Throttle(MIN_TIME_BETWEEN_UPDATES)
	async def async_do_maintenance_retrieval(self):
		await self.api_client.device.do_maintenance_retrieval(self._device_information["data"]["getDevice"])
		LOGGER.debug("Rinnai Maintenance Retrieval Started")

	async def _update_device(self, *_) -> None:
		"""Update the device information from the API"""
		self._device_information = await self.api_client.device.get_info(
			self._rinnai_device_id
		)
		await self.async_do_maintenance_retrieval()
		LOGGER.debug("Rinnai device data: %s", self._device_information)