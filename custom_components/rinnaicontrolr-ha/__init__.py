import logging
import asyncio

from aiorinnai import API
from aiorinnai.api import Unauthenticated
from aiorinnai.errors import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    CLIENT,
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
)
from .device import RinnaiDeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["water_heater", "binary_sensor", "sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rinnai from config entry"""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    _LOGGER.debug(entry.data[CONF_EMAIL])

    hass.data[DOMAIN][entry.entry_id][CLIENT] = client = API()

    try:
        await client.async_renew_access_token(entry.data[CONF_EMAIL], entry.data[CONF_ACCESS_TOKEN], entry.data[CONF_REFRESH_TOKEN])
        user_info = await client.user.get_info()
        _LOGGER.debug("User info retrieved: %s", user_info)
    except Unauthenticated as err:
        _LOGGER.error("Authentication error: %s", err)
        raise ConfigEntryAuthFailed from err
    except RequestError as err:
        _LOGGER.error("Request error: %s", err)
        raise ConfigEntryNotReady from err

    devices = user_info.get("devices", {}).get("items", [])
    if not devices:
        _LOGGER.error("No devices found in user info")
        raise ConfigEntryNotReady("No devices found")

    hass.data[DOMAIN][entry.entry_id]["devices"] = [
        RinnaiDeviceDataUpdateCoordinator(hass, client, device["id"], entry.options)
        for device in devices
    ]

    tasks = [device.async_refresh() for device in hass.data[DOMAIN][entry.entry_id]["devices"]]
    await asyncio.gather(*tasks)

    if not entry.options:
        await _async_options_updated(hass, entry)
    
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

async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        data = {**config_entry.data}

        # Set default values if keys are missing
        data.setdefault(CONF_ACCESS_TOKEN, "")
        data.setdefault(CONF_REFRESH_TOKEN, "")

        if not data[CONF_ACCESS_TOKEN] or not data[CONF_REFRESH_TOKEN]:
            # Fetch new tokens from the API using existing credentials
            client = API()
            try:
                # Assuming you have CONF_EMAIL and CONF_PASSWORD in the config_entry.data
                await client.async_login(config_entry.data[CONF_EMAIL], config_entry.data[CONF_PASSWORD])
                user_info = await client.user.get_info()
                _LOGGER.debug("User info retrieved during migration: %s", user_info)
                
                # Update tokens in data
                data[CONF_ACCESS_TOKEN] = client.access_token
                data[CONF_REFRESH_TOKEN] = client.refresh_token
            except Unauthenticated as err:
                _LOGGER.error("Authentication error during migration: %s", err)
                raise ConfigEntryAuthFailed from err
            except RequestError as err:
                _LOGGER.error("Request error during migration: %s", err)
                raise ConfigEntryNotReady from err

        hass.config_entries.async_update_entry(config_entry, data=data, version=2)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True