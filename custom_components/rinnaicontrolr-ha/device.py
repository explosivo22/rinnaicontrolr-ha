"""Rinnai device object"""
import asyncio
from datetime import timedelta

import async_timeout

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .rinnai import WaterHeater

from .const import (
	CONF_MAINT_INTERVAL_ENABLED,
	CONF_MAINT_REFRESH_INTERVAL,
	DEFAULT_MAINT_REFRESH_INTERVAL,
	DOMAIN as RINNAI_DOMAIN,
	LOGGER,
)

class RinnaiDeviceDataUpdateCoordinator(DataUpdateCoordinator):
	"""Rinnai device object"""

	def __init__(
		self, hass: HomeAssistant, host: str, serial: str, name: str, model: str, update_interval: int, options
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
		self.maint_refresh_interval = timedelta(seconds=self.options.get(CONF_MAINT_REFRESH_INTERVAL, DEFAULT_MAINT_REFRESH_INTERVAL))
		self._unsub_maintenance_timer = None  # Track the recurring maintenance timer
		self._unsub_maintenance_delay = None  # Track the initial delay timer
		self._maintenance_enabled = self.options.get(CONF_MAINT_INTERVAL_ENABLED, False)
		super().__init__(
			hass,
			LOGGER,
			name=f"{RINNAI_DOMAIN}-{serial}",
			update_interval=timedelta(seconds=update_interval),
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
	def firmware_version(self) -> str | None:
		"""Return the firmware version for the device"""
		if not self._device_info:
			return None
		return self._device_info.get('module_firmware_version')

	@property
	def current_temperature(self) -> float | None:
		"""Return the current temperature in degrees F"""
		if not self._device_info:
			return None
		value = self._device_info.get('domestic_temperature')
		if value is None:
			LOGGER.debug(
				"No current temperature found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid current_temperature value: %s", value)
			return None

	@property
	def target_temperature(self) -> float | None:
		"""Return the target temperature in degrees F"""
		if not self._device_info:
			return None
		value = self._device_info.get('set_domestic_temperature')
		if value is None:
			LOGGER.debug(
				"No target temperature found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid target_temperature value: %s", value)
			return None

	@property
	def serial_number(self) -> str:
		"""Return the serial number for the device"""
		return self.serial

	@property
	def is_heating(self) -> bool:
		"""Return if the water heater is heating"""
		if not self._device_info:
			return False
		value = self._device_info.get('domestic_combustion')
		if value is None:
			LOGGER.debug(
				"No domestic_combustion found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return False
		try:
			return self.str_to_bool(value)
		except Exception:
			LOGGER.warning("Invalid is_heating value: %s", value)
			return False
	@property
	def is_on(self) -> bool:
		"""Return if the water heater is on"""
		if not self._device_info:
			return False
		value = self._device_info.get('operation_enabled')
		if value is None:
			LOGGER.debug(
				"No operation_enabled found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return False
		try:
			return self.str_to_bool(value)
		except Exception:
			LOGGER.warning("Invalid is_on value: %s", value)
			return False

	@property
	def is_recirculating(self) -> bool:
		"""Return if recirculation is running"""
		if not self._device_info:
			return False
		value = self._device_info.get('recirculation_enabled')
		if value is None:
			LOGGER.debug(
				"No recirculation_enabled found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return False
		try:
			return self.str_to_bool(value)
		except Exception:
			LOGGER.warning("Invalid is_recirculating value: %s", value)
			return False

	@property
	def outlet_temperature(self) -> float | None:
		"""Return the outlet water temperature"""
		if not self._device_info:
			return None
		value = self._device_info.get('m02_outlet_temperature')
		if value is None:
			LOGGER.debug(
				"No outlet temperature found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid outlet_temperature value: %s", value)
			return None

	@property
	def inlet_temperature(self) -> float | None:
		"""Return the inlet water temperature"""
		if not self._device_info:
			return None
		value = self._device_info.get('m08_inlet_temperature')
		if value is None:
			LOGGER.debug(
				"No inlet temperature found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid inlet_temperature value: %s", value)
			return None

	@property
	def vacation_mode_on(self) -> bool:
		"""Return if vacation mode is on"""
		if not self._device_info:
			return False
		schedule_holiday = self._device_info.get('schedule_holiday')
		if schedule_holiday is None or (isinstance(schedule_holiday, str) and 'null' in schedule_holiday.lower()):
			return False
		try:
			return self.str_to_bool(schedule_holiday)
		except Exception:
			return False

	@property
	def water_flow_rate(self) -> float | None:
		"""Return the water flow rate"""
		if not self._device_info:
			return None
		value = self._device_info.get('m01_water_flow_rate_raw')
		if value is None:
			LOGGER.debug(
				"No water flow rate found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid water_flow_rate value: %s", value)
			return None

	@property
	def combustion_cycles(self) -> float | None:
		"""Return the combustion cycles"""
		if not self._device_info:
			return None
		value = self._device_info.get('m04_combustion_cycles')
		if value is None:
			LOGGER.debug(
				"No combustion cycles found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid combustion_cycles value: %s", value)
			return None

	@property
	def pump_hours(self) -> float | None:
		"""Return the pump hours"""
		if not self._device_info:
			return None
		value = self._device_info.get('m19_pump_hours')
		if value is None:
			LOGGER.debug(
				"No pump hours found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid pump_hours value: %s", value)
			return None

	@property
	def combustion_hours(self) -> float | None:
		"""Return the combustion hours"""
		if not self._device_info:
			return None
		value = self._device_info.get('m03_combustion_hours_raw')
		if value is None:
			LOGGER.debug(
				"No combustion hours found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid combustion_hours value: %s", value)
			return None

	@property
	def fan_current(self) -> float | None:
		"""Return the fan current"""
		if not self._device_info:
			return None
		value = self._device_info.get('m09_fan_current')
		if value is None:
			LOGGER.debug(
				"No fan current found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid fan_current value: %s", value)
			return None

	@property
	def fan_frequency(self) -> float | None:
		"""Return the fan frequency"""
		if not self._device_info:
			return None
		value = self._device_info.get('m05_fan_frequency')
		if value is None:
			LOGGER.debug(
				"No fan frequency found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid fan_frequency value: %s", value)
			return None

	@property
	def pump_cycles(self) -> float | None:
		"""Return the pump cycles"""
		if not self._device_info:
			return None
		value = self._device_info.get('m20_pump_cycles')
		if value is None:
			LOGGER.debug(
				"No pump cycles found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid pump_cycles value: %s", value)
			return None
	
	@property
	def wifi_signal(self) -> int | None:
		"""Return the wifi signal strength"""
		if not self._device_info:
			return None
		value = self._device_info.get('wifi_signal_strength')
		if value is None:
			LOGGER.debug(
				"No wifi signal found in device_info keys: %s",
				list(self._device_info.keys()),
			)
			return None
		try:
			return int(value)
		except (TypeError, ValueError):
			LOGGER.warning("Invalid wifi_signal value: %s", value)
			return None
	
	@staticmethod
	def str_to_bool(s):
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

	async def async_do_maintenance_retrieval(self, _event=None):
		await self.waterHeater.do_maintenance_retrieval()
		LOGGER.debug("Rinnai Maintenance Retrieval Started")

	async def _update_device(self, *_) -> None:
		"""Update the device information from the API"""
		self._device_info = await self.waterHeater.get_status()
		LOGGER.debug("Rinnai device data: %s", self._device_info)

	def start_maintenance_timer(self):
		"""Start the maintenance retrieval timer if enabled.
		
		Note: The first maintenance retrieval will occur after the configured interval,
		not immediately. This prevents unnecessary API calls during initialization.
		"""
		# Cancel any existing timers first
		if self._unsub_maintenance_delay:
			self._unsub_maintenance_delay()
			self._unsub_maintenance_delay = None
		if self._unsub_maintenance_timer:
			self._unsub_maintenance_timer()
			self._unsub_maintenance_timer = None
		
		# Only set up timer if maintenance is enabled
		if self.options.get(CONF_MAINT_INTERVAL_ENABLED, False):
			from datetime import datetime
			next_run = datetime.now() + self.maint_refresh_interval
			LOGGER.info(
				"Maintenance retrieval scheduled. First run will occur at approximately %s (in %s seconds)",
				next_run.strftime("%H:%M:%S"),
				self.maint_refresh_interval.total_seconds(),
			)
			
			# Schedule the first call after the interval delay
			# This prevents immediate execution on startup
			self._unsub_maintenance_delay = async_call_later(
				self.hass,
				self.maint_refresh_interval.total_seconds(),
				self._start_maintenance_interval,
			)
		else:
			LOGGER.debug("Maintenance retrieval disabled in configuration")
	
	@callback
	def _start_maintenance_interval(self, _now=None):
		"""Start the recurring maintenance interval timer.
		
		This is called after the initial delay to set up the recurring timer.
		"""
		# Clear the delay timer reference since it's now complete
		self._unsub_maintenance_delay = None
		
		LOGGER.info(
			"Starting maintenance retrieval cycle. Will run every %s",
			self.maint_refresh_interval,
		)
		
		# Perform the first maintenance retrieval
		self.hass.async_create_task(self.async_do_maintenance_retrieval())
		
		# Set up recurring timer for subsequent calls
		self._unsub_maintenance_timer = async_track_time_interval(
			self.hass, self.async_do_maintenance_retrieval, self.maint_refresh_interval
		)
	
	def stop_maintenance_timer(self):
		"""Stop the maintenance retrieval timer and any pending delayed calls"""
		# Cancel the delayed initial call if it hasn't fired yet
		if self._unsub_maintenance_delay:
			self._unsub_maintenance_delay()
			self._unsub_maintenance_delay = None
			LOGGER.debug("Cancelled pending maintenance retrieval delay")
		
		# Cancel the recurring timer if it exists
		if self._unsub_maintenance_timer:
			self._unsub_maintenance_timer()
			self._unsub_maintenance_timer = None
			LOGGER.debug("Maintenance retrieval timer stopped")

	async def async_shutdown(self):
		"""Called when the coordinator is being shut down"""
		# Clean up the maintenance timer
		self.stop_maintenance_timer()