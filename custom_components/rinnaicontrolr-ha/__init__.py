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
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN

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
    """Set up Rinnai from config entry"""
    session = async_get_clientsession(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    waterHeater = WaterHeater(entry.data[CONF_HOST])
    sysinfo = await waterHeater.get_sysinfo()

    # Gracefully handle controller offline or unreachable
    if not sysinfo or "sysinfo" not in sysinfo or "serial-number" not in sysinfo["sysinfo"]:
        _LOGGER.error("Could not connect to Rinnai controller or missing sysinfo; will retry later.")
        raise ConfigEntryNotReady("Rinnai controller is offline or unreachable.")

    update_interval = entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)

    maint_refresh_interval = entry.options.get(CONF_MAINT_REFRESH_INTERVAL, DEFAULT_MAINT_REFRESH_INTERVAL)

    coordinator = RinnaiDeviceDataUpdateCoordinator(
            hass, 
            entry.data[CONF_HOST],
            sysinfo["sysinfo"]["serial-number"],
            sysinfo["sysinfo"]["serial-number"],
            sysinfo["sysinfo"].get("ayla-dsn", "unknown"),  # Use get method with default value
            update_interval, 
            entry.options
        )
    
    coordinator.maint_refresh_interval = timedelta(seconds=maint_refresh_interval)
    
    await coordinator.async_refresh()

    if not entry.options:
        await _async_options_updated(hass, entry)

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    
    return True

async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry):
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok