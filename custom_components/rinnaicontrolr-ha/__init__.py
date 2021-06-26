import logging
import asyncio
import time
from datetime import datetime, timedelta

import async_timeout
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN

from .const import DOMAIN

from rinnaicontrolr import RinnaiWaterHeater

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["water_heater"]

RINNAI_SERVICE = 'rinnai_service'

NOTIFICATION_ID = 'rinnai_notification'

CONF_DEVICES = 'devices'
CONF_DEVICE_ID = 'device_id'
CONF_SCAN_INTERVAL = 'scan interval'

ATTR_DURATION = 'duration'

SCAN_INTERVAL = timedelta(seconds=300)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICES, default=[]): cv.ensure_list,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Rinnai component"""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Rinnai from config entry"""
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

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok