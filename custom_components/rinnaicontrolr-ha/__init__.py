import logging
import asyncio
import time
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN

from .const import DOMAIN
from .device import RinnaiDeviceDataUpdateCoordinator

from rinnaicontrolr import RinnaiWaterHeater

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["water_heater","sensor"]

RINNAI_SERVICE = 'rinnai_service'

NOTIFICATION_ID = 'rinnai_notification'

CONF_DEVICES = 'devices'
CONF_DEVICE_ID = 'device_id'
CONF_SCAN_INTERVAL = 'scan interval'

ATTR_DURATION = 'duration'

SCAN_INTERVAL = timedelta(seconds=300)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rinnai from config entry"""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    user = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    for ar in entry.data:
        _LOGGER.debug(ar)

    try:
        hass.data[DOMAIN][entry.entry_id][RINNAI] = rinnai = RinnaiWaterHeater(
            entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
        )
    except RequestError as err:
        raise ConfigEntryNotReady from err

    rinnai_devices = await rinnai.getDevices()

    hass.data[DOMAIN][entry.entry_id]["devices"] = devices = [
        RinnaiDeviceDataUpdateCoordinator(hass, rinnai, device["thing_name"])
        for device in rinnai_devices["info"]
    ]
    
    tasks = [device.async_refresh() for device in devices]
    await asyncio.gather(*tasks)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok