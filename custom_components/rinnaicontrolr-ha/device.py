"""Rinnai device object"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from rinnaicontrolr.api import API
from rinnaicontrolr.errors import RequestError
from async_timeout import timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DOMAIN as RINNAI_DOMAIN, LOGGER

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
		return float(self._device_information["data"]["getDevice"]["shadow"]["set_domestic_temperature"])

	@property
	def serial_number(self) -> str:
		"""Return the serial number for the device"""
		return self._device_information["data"]["getDevice"]["info"]["serial_id"]

	@property
	def last_known_state(self) -> str:
		return self._device_information["data"]["getDevice"]["activity"]["eventType"]

	@property
	def domestic_combustion(self) -> bool:
		return bool((self._device_information["data"]["getDevice"]["info"]["domestic_combustion"]).capitalize())

	async def async_set_temperature(self, temperature: int):
		await self.api_client.device.set_temperature(self.user_uuid, self.thing_name, temperature)

	async def async_start_recirculation(self, duration: int):
		await self.api_client.device.start_recirculation(self.user_uuid, self.thing_name, duration)

	async def _update_device(self, *_) -> None:
		"""Update the device information from the API"""
		self._device_information = await self.api_client.device.get_info(
			self._rinnai_device_id
		)
		LOGGER.debug("Rinnai device data: %s", self._device_information)