"""Rinnai device object"""
import asyncio
from datetime import timedelta

from async_timeout import timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle

from .rinnai import WaterHeater

from .const import (
	CONF_MAINT_INTERVAL_ENABLED,
	DOMAIN as RINNAI_DOMAIN,
	LOGGER,
)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

class RinnaiDeviceDataUpdateCoordinator(DataUpdateCoordinator):
	"""Rinnai device object"""

	def __init__(
		self, hass: HomeAssistant, host: str, serial: str, name: str, model: str, options
	):
		"""Initialize the device"""
		self.hass: HomeAssistantType = hass
		self.host = host
		self.waterHeater = WaterHeater(host)
		self.serial = serial
		self.name = name
		self.device_model = model
		self.device_manufacturer: str = "Rinnai"
		self.info = None
		self.options = options
		super().__init__(
			hass,
			LOGGER,
			name=RINNAI_DOMAIN,
			update_interval=timedelta(seconds=10),
		)

	async def _async_update_data(self):
		"""Update data via library"""
		try:
			async with timeout(10):
				await asyncio.gather(
					*[self._update_device()]
				)
		except (IndexError) as error:
			raise UpdateFailed(error) from error
	
	@property
	def device_name(self) -> str:
		"""Return device name."""
		return self.name

	@property
	def manufacturer(self) -> str:
		"""Return manufacturer for device"""
		return self.device_manufacturer

	@property
	def model(self) -> str:
		"""Return model for device"""
		return self.device_model
		
	@property
	def firmware_version(self) -> str:
		"""Return the serial number for the device"""
		return self.info['firmware_version']

	@property
	def current_temperature(self) -> float:
		"""Return the current temperature in degrees F"""
		return float(self.info['domestic_temperature'])

	@property
	def target_temperature(self) -> float:
		"""Return the current temperature in degrees F"""
		if self.info['set_domestic_temperature'] is None:
			return None
		return float(self.info['set_domestic_temperature'])

	@property
	def serial_number(self) -> str:
		"""Return the serial number for the device"""
		return self.serial

	@property
	def is_heating(self) -> bool:
		return self.info['domestic_combustion']

	@property
	def is_on(self) -> bool:
		return self.info['operation_enabled']

	@property
	def is_recirculating(self) -> bool:
		return self.info['recirculation_enabled']

	@property
	def outlet_temperature(self) -> float:
		return float(self.info['outlet_temperature'])

	@property
	def inlet_temperature(self) -> float:
		return float(self.info['inlet_temperature'])

	@property
	def vacation_mode_on(self) -> bool:
		if self.info['schedule_holiday'] is None:
			return None
		return self.info['schedule_holiday']

	@property
	def water_flow_rate(self) -> float:
		"""Return the current temperature in degrees F"""
		if int(self.info['water_flow_rate']) is None:
			return None
		return float(self.info['water_flow_rate'])

	@property
	def combustion_cycles(self) -> float:
		"""Return the current temperature in degrees F"""
		if self.info['combustion_cycles'] is None:
			return None
		return float(self.info['combustion_cycles'])

	@property
	def pump_hours(self) -> float:
		"""Return the current temperature in degrees F"""
		if self.info['pump_hours'] is None:
			return None
		return float(self.info['pump_hours'])

	@property
	def fan_current(self) -> float:
		"""Return the current temperature in degrees F"""
		if self.info['fan_current'] is None:
			return None
		return float(self.info['fan_current'])

	@property
	def fan_frequency(self) -> float:
		"""Return the current temperature in degrees F"""
		if self.info['fan_frequency'] is None:
			return None
		return float(self.info['fan_frequency'])

	@property
	def pump_cycles(self) -> float:
		"""Return the current temperature in degrees F"""
		if self.info['pump_cycles'] is None:
			return None
		return float(self.info['pump_cycles'])

	async def async_set_temperature(self, temperature: int):
		await self.hass.async_add_executor_job(self.waterHeater.set_temperature(temperature))

	async def async_start_recirculation(self, duration: int):
		await self.hass.async_add_executor_job(self.waterHeater.start_recirculation(duration))

	async def async_stop_recirculation(self):
		await self.hass.async_add_executor_job(self.waterHeater.stop_recirculation())

	async def async_enable_vacation_mode(self):
		await self.hass.async_add_executor_job(self.waterHeater.vacation_mode_on())

	async def async_disable_vacation_mode(self):
		await self.hass.async_add_executor_job(self.waterHeater.vacation_mode_off())

	async def async_turn_off(self):
		await self.hass.async_add_executor_job(self.waterHeater.turn_off())

	async def async_turn_on(self):
		await self.hass.async_add_executor_job(self.waterHeater.turn_on())

	@Throttle(MIN_TIME_BETWEEN_UPDATES)
	async def async_do_maintenance_retrieval(self):
		await self.hass.async_add_executor_job(self.waterHeater.do_maintenance_retrieval())
		LOGGER.debug("Rinnai Maintenance Retrieval Started")

	async def _update_device(self, *_) -> None:
		"""Update the device information from the API"""
		LOGGER.debug(self.host)
		self.info = await self.hass.async_add_executor_job(
			self.waterHeater.get_status()
		)
		if self.options[CONF_MAINT_INTERVAL_ENABLED]:
			await self.async_do_maintenance_retrieval()
		else:
			LOGGER.debug("Skipping Maintenance retrieval since disabled inside of configuration")
		
		LOGGER.debug("Rinnai device data: %s", self.info)