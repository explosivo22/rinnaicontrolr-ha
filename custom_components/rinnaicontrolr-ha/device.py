"""Rinnai device object"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DOMAIN as RINNAI_DOMAIN, LOGGER

class RinnaiDeviceDataUpdateCoordinator(DataUpdateCoordinator):
	"""Rinnai device object"""

	def __init__(
		self, hass: HomeAssistantType, rinnai_client: API, thing_name: str
	):
		"""Initialize the device"""
		self.hass: HomeAssistantType = hass
		self.rinnai_client: API = rinnai_client
		self._rinnai_thing_name: str = thing_name
		self._manufacturer: str = "Rinnai"
		self._device_information: Optional[Dict[str, Any]] = None
		super().__init__(
			hass,
			LOGGER,
			name=f"{RINNAI_DOMAIN}-{thing_name}",
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
		return self._rinnai_thing_name

	@property
	def device_name(self) -> str:
		"""Return device name"
		return f"{self.manufacturer} {self.model}"

	@property
	def manufacturer(self) -> str:
		"""Return manufacturer for device"""
		return self._manufacturer

	@property
	def model(self) -> str:
		"""Return model for device"""
		return self._device_information["info"]["model"]

	@property
	def temperature(self) -> str:
		"""Return the current temperature in degrees F"""
		return self._device_information["info"]["domestic_temperature"]

	@property
	def serial_number(self) -> str:
		"""Return the serial number for the device"""
		reutnr self._device_information["shadow"]["heater_serial_number"]

