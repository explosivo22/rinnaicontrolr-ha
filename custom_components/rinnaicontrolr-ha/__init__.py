import logging
import asyncio

from rinnaicontrolr import async_get_api
from rinnaicontrolr.errors import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN

from .const import CLIENT, DOMAIN
from .device import RinnaiDeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["water_heater"]

RINNAI_SERVICE = 'rinnai_service'

NOTIFICATION_ID = 'rinnai_notification'

CONF_DEVICES = 'devices'
CONF_DEVICE_ID = 'device_id'
CONF_SCAN_INTERVAL = 'scan interval'

ATTR_DURATION = 'duration'

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rinnai from config entry"""
    session = async_get_clientsession(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    try:
        hass.data[DOMAIN][entry.entry_id][CLIENT] = client = await async_get_api(
            entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD], session=session
        )
    except RequestError as err:
        raise ConfigEntryNotReady from err

    user_info = await client.user.get_info()

    _LOGGER.debug("Rinnai user information: %s", user_info)

    hass.data[DOMAIN][entry.entry_id]["devices"] = devices = [
        RinnaiDeviceDataUpdateCoordinator(hass, client, device["id"])
        for device in user_info["devices"]["items"]
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