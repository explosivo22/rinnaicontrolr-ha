from datetime import timedelta
import logging
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    MAJOR_VERSION,
    MINOR_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_MAINT_REFRESH_INTERVAL,
    DEFAULT_MAINT_REFRESH_INTERVAL,
    DOMAIN,
    COORDINATOR,
    CONF_REFRESH_INTERVAL,
    DEFAULT_REFRESH_INTERVAL
)

from .device import RinnaiDeviceDataUpdateCoordinator
from .rinnai import WaterHeater

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["water_heater","binary_sensor", "sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rinnai from config entry."""
    session = async_get_clientsession(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    waterHeater = WaterHeater(entry.data[CONF_HOST])
    
    # Attempt to fetch system information from the controller
    # This is required during setup to obtain device metadata (serial number, model)
    # needed for device registry and coordinator initialization
    sysinfo = await waterHeater.get_sysinfo()

    # Validate sysinfo response structure following HA best practices
    # Raising ConfigEntryNotReady will trigger automatic retry by Home Assistant
    if sysinfo is None:
        _LOGGER.warning(
            "Unable to connect to Rinnai controller at %s; setup will be retried automatically",
            entry.data[CONF_HOST],
        )
        raise ConfigEntryNotReady(
            f"Unable to connect to Rinnai controller at {entry.data[CONF_HOST]}"
        )
    
    if not isinstance(sysinfo, dict):
        _LOGGER.warning(
            "Invalid response from Rinnai controller at %s; setup will be retried automatically",
            entry.data[CONF_HOST],
        )
        raise ConfigEntryNotReady(
            f"Invalid response from Rinnai controller at {entry.data[CONF_HOST]}"
        )
    
    # Safely check nested structure
    sysinfo_data = sysinfo.get("sysinfo")
    if not isinstance(sysinfo_data, dict):
        _LOGGER.warning(
            "Missing system information from Rinnai controller at %s; setup will be retried automatically",
            entry.data[CONF_HOST],
        )
        raise ConfigEntryNotReady(
            f"Missing system information from Rinnai controller at {entry.data[CONF_HOST]}"
        )
    
    serial_number = sysinfo_data.get("serial-number")
    if not serial_number:
        _LOGGER.warning(
            "Missing serial number from Rinnai controller at %s; setup will be retried automatically",
            entry.data[CONF_HOST],
        )
        raise ConfigEntryNotReady(
            f"Missing serial number from Rinnai controller at {entry.data[CONF_HOST]}"
        )
    
    _LOGGER.info(
        "Successfully connected to Rinnai controller at %s (Serial: %s)",
        entry.data[CONF_HOST],
        serial_number,
    )

    update_interval = entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)

    maint_refresh_interval = entry.options.get(CONF_MAINT_REFRESH_INTERVAL, DEFAULT_MAINT_REFRESH_INTERVAL)

    # Extract safely validated values
    ayla_dsn = sysinfo_data.get("ayla-dsn", "unknown")

    coordinator = RinnaiDeviceDataUpdateCoordinator(
            hass, 
            entry.data[CONF_HOST],
            serial_number,
            serial_number,
            ayla_dsn,
            update_interval, 
            entry.options
        )
    
    coordinator.maint_refresh_interval = timedelta(seconds=maint_refresh_interval)
    
    await coordinator.async_config_entry_first_refresh()

    if not entry.options:
        await _async_options_updated(hass, entry)

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator
    }

    # Start maintenance timer after coordinator is fully initialized
    coordinator.start_maintenance_timer()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    
    # Ensure maintenance timer is stopped when entry is unloaded
    entry.async_on_unload(coordinator.stop_maintenance_timer)
    
    return True

async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry):
    """Update options."""
    # Reload the integration to apply new settings including maintenance interval changes
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # Stop maintenance timer before unloading
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    coordinator.stop_maintenance_timer()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok