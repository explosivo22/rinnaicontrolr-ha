"""Rinnai Control-R Water Heater integration for Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CONNECTION_MODE,
    CONF_HOST,
    CONF_REFRESH_TOKEN,
    CONNECTION_MODE_CLOUD,
    CONNECTION_MODE_HYBRID,
    CONNECTION_MODE_LOCAL,
    DOMAIN,
)
from .device import RinnaiDeviceDataUpdateCoordinator
from .local import RinnaiLocalClient

if TYPE_CHECKING:
    from aiorinnai import API
    from homeassistant.helpers.device_registry import DeviceEntry


@dataclass
class RinnaiRuntimeData:
    """Runtime data for Rinnai integration.

    This class holds data that is created during setup and needed throughout
    the integration's lifecycle.
    """

    devices: list[RinnaiDeviceDataUpdateCoordinator] = field(default_factory=list)
    client: API | None = None
    local_client: RinnaiLocalClient | None = None
    connection_mode: str = CONNECTION_MODE_CLOUD


# Type alias for config entry with runtime data
RinnaiConfigEntry: TypeAlias = ConfigEntry[RinnaiRuntimeData]  # type: ignore[type-arg]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.WATER_HEATER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: RinnaiConfigEntry) -> bool:
    """Set up Rinnai from config entry.

    Supports three connection modes:
    - Cloud: Uses aiorinnai API with Rinnai account credentials
    - Local: Direct TCP connection to water heater controller
    - Hybrid: Local primary with cloud fallback

    Args:
        hass: Home Assistant instance.
        entry: Config entry being set up.

    Returns:
        True if setup was successful.

    Raises:
        ConfigEntryAuthFailed: When authentication fails.
        ConfigEntryNotReady: When connection fails or no devices found.
    """
    connection_mode = entry.data.get(CONF_CONNECTION_MODE, CONNECTION_MODE_CLOUD)
    _LOGGER.debug("Setting up Rinnai integration in %s mode", connection_mode)

    api_client: API | None = None
    local_client: RinnaiLocalClient | None = None
    device_ids: list[str] = []

    # Set up clients based on connection mode
    if connection_mode in (CONNECTION_MODE_CLOUD, CONNECTION_MODE_HYBRID):
        api_client, device_ids = await _setup_cloud_client(hass, entry)

    if connection_mode in (CONNECTION_MODE_LOCAL, CONNECTION_MODE_HYBRID):
        local_client, local_device_id = await _setup_local_client(entry)
        if connection_mode == CONNECTION_MODE_LOCAL:
            device_ids = [local_device_id]

    if not device_ids:
        raise ConfigEntryNotReady("No Rinnai devices found")

    # Convert MappingProxyType to dict for options
    options = (
        dict(entry.options) if not isinstance(entry.options, dict) else entry.options
    )

    # Create coordinators for each device
    coordinators = []
    for device_id in device_ids:
        coordinator = RinnaiDeviceDataUpdateCoordinator(
            hass,
            device_id,
            options,
            entry,
            api_client=api_client,
            local_client=local_client,
            connection_mode=connection_mode,
        )
        coordinators.append(coordinator)

    # Store runtime data using modern pattern
    entry.runtime_data = RinnaiRuntimeData(
        devices=coordinators,
        client=api_client,
        local_client=local_client,
        connection_mode=connection_mode,
    )

    # Initial data fetch for all devices
    tasks = [coordinator.async_refresh() for coordinator in coordinators]
    await asyncio.gather(*tasks)

    if not entry.options:
        await _async_options_updated(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _setup_cloud_client(
    hass: HomeAssistant, entry: ConfigEntry
) -> tuple[API, list[str]]:
    """Set up the cloud API client and get device list.

    Returns:
        Tuple of (API client, list of device IDs).

    Raises:
        ConfigEntryAuthFailed: When authentication fails.
        ConfigEntryNotReady: When the API is unavailable.
    """
    from aiorinnai import API
    from aiorinnai.api import Unauthenticated
    from aiorinnai.errors import RequestError

    _LOGGER.debug("Setting up cloud client for %s", entry.data.get(CONF_EMAIL))

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
        raise ConfigEntryNotReady(f"Unable to connect to Rinnai API: {err}") from err

    devices = user_info.get("devices", {}).get("items", [])
    if not devices:
        _LOGGER.error("No devices found in user info")
        raise ConfigEntryNotReady("No Rinnai devices found for this account")

    device_ids = [device["id"] for device in devices]
    return client, device_ids


async def _setup_local_client(entry: ConfigEntry) -> tuple[RinnaiLocalClient, str]:
    """Set up the local TCP client.

    Returns:
        Tuple of (local client, device ID from sysinfo).

    Raises:
        ConfigEntryNotReady: When local connection fails.
    """
    host = entry.data.get(CONF_HOST)
    if not host:
        raise ConfigEntryNotReady("No host configured for local connection")

    _LOGGER.debug("Setting up local client for %s", host)

    client = RinnaiLocalClient(host)

    # Test connection and get device info
    sysinfo = await client.get_sysinfo()
    if sysinfo is None:
        raise ConfigEntryNotReady(f"Unable to connect to Rinnai controller at {host}")

    sysinfo_data = sysinfo.get("sysinfo", {})
    serial_number = sysinfo_data.get("serial-number", host)

    _LOGGER.info(
        "Successfully connected to Rinnai controller at %s (Serial: %s)",
        host,
        serial_number,
    )

    # Use serial number as device ID for local mode
    return client, serial_number


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


async def _async_options_updated(hass: HomeAssistant, entry: RinnaiConfigEntry) -> None:
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
    from aiorinnai import API
    from aiorinnai.api import Unauthenticated
    from aiorinnai.errors import RequestError

    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        data = {**config_entry.data}

        # Set default values if keys are missing
        data.setdefault(CONF_ACCESS_TOKEN, "")
        data.setdefault(CONF_REFRESH_TOKEN, "")
        # Default to cloud mode for existing entries
        data.setdefault(CONF_CONNECTION_MODE, CONNECTION_MODE_CLOUD)

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
