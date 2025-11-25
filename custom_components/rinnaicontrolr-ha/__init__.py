"""Rinnai Control-R Water Heater integration for Home Assistant."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aiorinnai import API
from aiorinnai.api import Unauthenticated
from aiorinnai.errors import RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from .device import RinnaiDeviceDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceEntry


@dataclass
class RinnaiRuntimeData:
    """Runtime data for Rinnai integration.

    This class holds data that is created during setup and needed throughout
    the integration's lifecycle.
    """

    client: API
    devices: list[RinnaiDeviceDataUpdateCoordinator] = field(default_factory=list)


# Type alias for config entry with runtime data
RinnaiConfigEntry = ConfigEntry[RinnaiRuntimeData]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.WATER_HEATER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

async def async_setup_entry(hass: HomeAssistant, entry: RinnaiConfigEntry) -> bool:
    """Set up Rinnai from config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry being set up.

    Returns:
        True if setup was successful.

    Raises:
        ConfigEntryAuthFailed: When authentication fails.
        ConfigEntryNotReady: When the API is unavailable or no devices found.
    """
    _LOGGER.debug("Setting up Rinnai integration for %s", entry.data[CONF_EMAIL])

    client = API()

    try:
        await client.async_renew_access_token(
            entry.data[CONF_EMAIL],
            entry.data[CONF_ACCESS_TOKEN],
            entry.data[CONF_REFRESH_TOKEN],
        )
        user_info = await client.user.get_info()
        _LOGGER.debug("User info retrieved: %s", user_info)

        # Persist refreshed tokens if they changed
        await _persist_tokens_if_changed(hass, entry, client)

    except Unauthenticated as err:
        _LOGGER.error("Authentication error: %s", err)
        ir.async_create_issue(
            hass,
            DOMAIN,
            "reauth_required",
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="reauth_required",
        )
        raise ConfigEntryAuthFailed from err
    except RequestError as err:
        _LOGGER.error("Request error during setup: %s", err)
        raise ConfigEntryNotReady(
            f"Unable to connect to Rinnai API: {err}"
        ) from err

    devices = user_info.get("devices", {}).get("items", [])
    if not devices:
        _LOGGER.error("No devices found in user info")
        raise ConfigEntryNotReady("No Rinnai devices found for this account")

    # Convert MappingProxyType to dict for options
    options = dict(entry.options) if not isinstance(entry.options, dict) else entry.options

    # Create coordinators for each device, passing config_entry for token persistence
    coordinators = [
        RinnaiDeviceDataUpdateCoordinator(
            hass, client, device["id"], options, entry
        )
        for device in devices
    ]

    # Store runtime data using modern pattern
    entry.runtime_data = RinnaiRuntimeData(client=client, devices=coordinators)

    # Initial data fetch for all devices
    tasks = [coordinator.async_refresh() for coordinator in coordinators]
    await asyncio.gather(*tasks)

    if not entry.options:
        await _async_options_updated(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _persist_tokens_if_changed(
    hass: HomeAssistant, entry: ConfigEntry, client: API
) -> None:
    """Persist tokens to config entry if they've been refreshed."""
    current_access = entry.data.get(CONF_ACCESS_TOKEN)
    current_refresh = entry.data.get(CONF_REFRESH_TOKEN)

    new_access = getattr(client, "access_token", None)
    new_refresh = getattr(client, "refresh_token", None)

    if (
        new_access
        and new_refresh
        and (new_access != current_access or new_refresh != current_refresh)
    ):
        _LOGGER.debug("Persisting refreshed tokens to config entry")
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: new_access,
                CONF_REFRESH_TOKEN: new_refresh,
            },
        )

async def _async_options_updated(
    hass: HomeAssistant, entry: RinnaiConfigEntry
) -> None:
    """Handle options update by reloading the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RinnaiConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry being unloaded.

    Returns:
        True if unload was successful.
    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Remove a config entry from a device.

    Args:
        hass: Home Assistant instance.
        config_entry: Config entry being modified.
        device_entry: Device entry being removed.

    Returns:
        True to allow device removal.
    """
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version.

    Args:
        hass: Home Assistant instance.
        config_entry: Config entry being migrated.

    Returns:
        True if migration was successful.

    Raises:
        ConfigEntryAuthFailed: When authentication fails during migration.
        ConfigEntryNotReady: When the API is unavailable during migration.
    """
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
                await client.async_login(
                    config_entry.data[CONF_EMAIL],
                    config_entry.data[CONF_PASSWORD],
                )
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