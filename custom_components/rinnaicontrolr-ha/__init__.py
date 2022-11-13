import logging
import asyncio
from datetime import timedelta

from aiorinnai import async_get_api
from aiorinnai.errors import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD, 
    CONF_EMAIL,
    MAJOR_VERSION,
    MINOR_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN

from .const import (
    CLIENT,
    DOMAIN,
    CONF_UNIT,
    DEFAULT_UNIT,
    CONF_MAINT_INTERVAL_ENABLED,
    DEFAULT_MAINT_INTERVAL_ENABLED,
)
from .device import RinnaiDeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["water_heater","binary_sensor", "sensor"]

def is_min_ha_version(min_ha_major_ver: int, min_ha_minor_ver: int) -> bool:
    """Check if HA version at least a specific version."""
    return (
        MAJOR_VERSION > min_ha_major_ver or
        (MAJOR_VERSION == min_ha_major_ver and MINOR_VERSION >= min_ha_minor_ver)
    )


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
        RinnaiDeviceDataUpdateCoordinator(hass, client, device["id"], entry.options)
        for device in user_info["devices"]["items"]
    ]

    if not entry.options:
        await _async_options_updated(hass, entry)
    
    tasks = [device.async_refresh() for device in devices]
    await asyncio.gather(*tasks)

    if is_min_ha_version(2022,8):
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    else:
        hass.config_entries.async_setup_platforms(entry, PLATFORMS)

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