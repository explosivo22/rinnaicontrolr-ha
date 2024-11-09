"""Rinnai device object"""
import asyncio
from datetime import timedelta

import async_timeout

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
		self.waterHeater = WaterHeater(host)
		self.serial = serial
		self.name = name
		self.device_model = model
		self.device_manufacturer: str = "Rinnai"
		self._device_info: Optional[Dict[str, Any]] | None = None
		self.options = options
		super().__init__(
			hass,
			LOGGER,
			name=f"{RINNAI_DOMAIN}-{serial}",
			update_interval=timedelta(seconds=30),
		)

	async def _async_update_data(self):
		"""Update data via library"""
		try:
			async with async_timeout.timeout(10):
				await self._update_device()
		except (IndexError) as error:
			raise UpdateFailed(error) from error
	
	@property
	def device_name(self) -> str:
		"""Return the device name"""
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
		"""Return the firmware version for the device"""
		return self._device_info['module_firmware_version']

	@property
	def current_temperature(self) -> float:
		"""Return the current temperature in degrees F"""
		return float(self._device_info['domestic_temperature'])

	@property
	def target_temperature(self) -> float:
		"""Return the target temperature in degrees F"""
		if self._device_info['set_domestic_temperature'] is None:
			return None
		return float(self._device_info['set_domestic_temperature'])

	@property
	def serial_number(self) -> str:
		"""Return the serial number for the device"""
		return self.serial

	@property
	def is_heating(self) -> bool:
		"""Return if the water heater is heating"""
		return self.str_to_bool(self._device_info['domestic_combustion'])
	@property
	def is_on(self) -> bool:
		"""Return if the water heater is on"""
		return self.str_to_bool(self._device_info['operation_enabled'])

	@property
	def is_recirculating(self) -> bool:
		"""Return if recirculation is running"""
		return self.str_to_bool(self._device_info['recirculation_enabled'])

	@property
	def outlet_temperature(self) -> float:
		"""Return the outlet water temperature"""
		return float(self._device_info['m02_outlet_temperature'])

	@property
	def inlet_temperature(self) -> float:
		"""Return the inlet water temperature"""
		return float(self._device_info['m08_inlet_temperature'])

	@property
	def vacation_mode_on(self) -> bool:
		"""Return if vacation mode is on"""
		if self._device_info['schedule_holiday'] is None:
			return None
		return self.str_to_bool(self._device_info['schedule_holiday'])

	@property
	def water_flow_rate(self) -> float:
		"""Return the water flow rate"""
		if int(self._device_info['m01_water_flow_rate_raw']) is None:
			return None
		return float(self._device_info['m01_water_flow_rate_raw'])

	@property
	def combustion_cycles(self) -> float:
		"""Return the combustion cycles"""
		if self._device_info['m04_combustion_cycles'] is None:
			return None
		return float(self._device_info['m04_combustion_cycles'])

	@property
	def pump_hours(self) -> float:
		"""Return the pump hours"""
		if self._device_info['m19_pump_hours'] is None:
			return None
		return float(self._device_info['m19_pump_hours'])

	@property
	def combustion_hours(self) -> float:
		"""Return the combustion hours"""
		if self._device_info['m03_combustion_hours_raw'] is None:
			return None
		return float(self._device_info['m03_combustion_hours_raw'])

	@property
	def fan_current(self) -> float:
		"""Return the fan current"""
		if self._device_info['m09_fan_current'] is None:
			return None
		return float(self._device_info['m09_fan_current'])

	@property
	def fan_frequency(self) -> float:
		"""Return the fan frequency"""
		if self._device_info['m05_fan_frequency'] is None:
			return None
		return float(self._device_info['m05_fan_frequency'])

	@property
	def pump_cycles(self) -> float:
		"""Return the pump cycles"""
		if self._device_info['m20_pump_cycles'] is None:
			return None
		return float(self._device_info['m20_pump_cycles'])
	
	@staticmethod
	def str_to_bool(s):
		LOGGER.debug(f"String value: {s}")
		if s.lower() == "true":
			return True
		elif s.lower() == "false":
			return False
		else:
			raise ValueError(f"Cannot convert {s} to boolean.")

	async def async_set_temperature(self, temperature: int):
		await self.waterHeater.set_temperature(temperature)

	async def async_start_recirculation(self, duration: int):
		await self.waterHeater.start_recirculation(duration)

	async def async_stop_recirculation(self):
		await self.waterHeater.stop_recirculation()

	async def async_enable_vacation_mode(self):
		await self.waterHeater.vacation_mode_on()

	async def async_disable_vacation_mode(self):
		await self.waterHeater.vacation_mode_off()

	async def async_turn_off(self):
		await self.waterHeater.turn_off()

	async def async_turn_on(self):
		await self.waterHeater.turn_on()

	@Throttle(MIN_TIME_BETWEEN_UPDATES)
	async def async_do_maintenance_retrieval(self):
		await self.waterHeater.do_maintenance_retrieval()
		LOGGER.debug("Rinnai Maintenance Retrieval Started")

	async def _update_device(self, *_) -> None:
		"""Update the device information from the API"""
		self._device_info = await self.waterHeater.get_status()
		if self.options[CONF_MAINT_INTERVAL_ENABLED]:
			await self.async_do_maintenance_retrieval()
		else:
			LOGGER.debug("Skipping Maintenance retrieval since disabled inside of configuration")
		
		LOGGER.debug("Rinnai device data: %s", self._device_info)