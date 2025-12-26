"""Rinnai Control-R Water Heater integration for Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CONNECTION_MODE,
    CONF_HOST,
    CONF_REFRESH_TOKEN,
    CONF_STORED_PASSWORD,
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
    known_device_ids: set[str] = field(default_factory=set)
    # Callbacks for adding entities dynamically (set by platforms)
    entity_adders: dict[Platform, AddEntitiesCallback] = field(default_factory=dict)
    # Config entry options for creating new coordinators
    options: dict = field(default_factory=dict)
    # Cancel callback for device discovery listener
    cancel_device_discovery: Any | None = None


# Type alias for config entry with runtime data
RinnaiConfigEntry: TypeAlias = ConfigEntry[RinnaiRuntimeData]  # type: ignore[type-arg]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.WATER_HEATER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
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
    _LOGGER.info(
        "Setting up Rinnai integration (entry_id=%s) in %s mode",
        entry.entry_id[:8],
        connection_mode,
    )

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
        _LOGGER.warning("No Rinnai devices found for account")
        raise ConfigEntryNotReady("No Rinnai devices found")

    _LOGGER.debug("Found %d Rinnai device(s): %s", len(device_ids), device_ids)

    # Convert MappingProxyType to dict for options
    options = (
        dict(entry.options) if not isinstance(entry.options, dict) else entry.options
    )

    # Create coordinators for each device
    _LOGGER.debug("Creating coordinators for %d device(s)", len(device_ids))
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
        _LOGGER.debug("Created coordinator for device %s", device_id)

    # Store runtime data using modern pattern
    entry.runtime_data = RinnaiRuntimeData(
        devices=coordinators,
        client=api_client,
        local_client=local_client,
        connection_mode=connection_mode,
        known_device_ids=set(device_ids),
        options=options,
    )

    # Initial data fetch for all devices
    _LOGGER.debug("Performing initial data fetch for %d device(s)", len(coordinators))
    tasks = [coordinator.async_refresh() for coordinator in coordinators]
    await asyncio.gather(*tasks)

    if not entry.options:
        await _async_options_updated(hass, entry)

    _LOGGER.debug("Forwarding setup to platforms: %s", [p.value for p in PLATFORMS])
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Set up periodic device discovery for cloud/hybrid modes
    if connection_mode in (CONNECTION_MODE_CLOUD, CONNECTION_MODE_HYBRID):
        _setup_device_discovery_listener(hass, entry)

    _LOGGER.info(
        "Rinnai integration setup complete with %d device(s)", len(coordinators)
    )
    return True


def _setup_device_discovery_listener(
    hass: HomeAssistant,
    entry: RinnaiConfigEntry,
) -> None:
    """Set up a listener to periodically check for new devices.

    Checks for device additions/removals every 10 minutes.
    """
    from homeassistant.helpers.event import async_track_time_interval
    from datetime import timedelta

    async def _check_devices(now: Any = None) -> None:  # noqa: ANN401
        """Check for device changes."""
        await async_check_device_changes(hass, entry)

    # Check for new devices every 10 minutes
    cancel_listener = async_track_time_interval(
        hass, _check_devices, timedelta(minutes=10)
    )
    # Store cancel callback in runtime_data for explicit cleanup in unload
    entry.runtime_data.cancel_device_discovery = cancel_listener
    _LOGGER.debug("Set up periodic device discovery (every 10 minutes)")


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
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    _LOGGER.debug("Setting up cloud client for %s", entry.data.get(CONF_EMAIL))

    # Use Home Assistant's shared session for connection pooling
    session = async_get_clientsession(hass)
    client = API(session=session)

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
        _LOGGER.warning("Token refresh failed: %s", err)

        # Attempt automatic re-login if password is stored
        stored_password = entry.data.get(CONF_STORED_PASSWORD)
        if stored_password:
            _LOGGER.info("Attempting automatic re-login with stored password")
            try:
                await client.async_login(entry.data[CONF_EMAIL], stored_password)
                user_info = await client.user.get_info()
                _LOGGER.info("Automatic re-login successful")

                # Persist the new tokens
                await _persist_tokens_if_changed(hass, entry, client)
            except Exception as login_err:
                _LOGGER.error("Automatic re-login failed: %s", login_err)
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    "reauth_required",
                    is_fixable=True,
                    is_persistent=True,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="reauth_required",
                )
                raise ConfigEntryAuthFailed from login_err
        else:
            _LOGGER.error(
                "Authentication error and no stored password for automatic re-login"
            )
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

    # Use public properties documented by aiorinnai API
    new_access = client.access_token
    new_refresh = client.refresh_token

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
    _LOGGER.info("Unloading Rinnai integration (entry_id=%s)", entry.entry_id[:8])

    # Cancel device discovery listener if it exists
    if hasattr(entry, "runtime_data") and entry.runtime_data is not None:
        if entry.runtime_data.cancel_device_discovery is not None:
            entry.runtime_data.cancel_device_discovery()
            entry.runtime_data.cancel_device_discovery = None
            _LOGGER.debug("Cancelled device discovery listener")

    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if result:
        _LOGGER.debug("Successfully unloaded all Rinnai platforms")
    else:
        _LOGGER.warning("Failed to unload some Rinnai platforms")
    return result


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
    _LOGGER.info("Removing device %s from Rinnai integration", device_entry.identifiers)
    return True


async def async_check_and_remove_stale_devices(
    hass: HomeAssistant,
    entry: RinnaiConfigEntry,
    current_device_ids: set[str],
) -> None:
    """Check for and remove devices that no longer exist in the account.

    This implements the HA Quality Scale 'stale_devices' requirement.
    Called periodically to sync device registry with actual devices.

    Args:
        hass: Home Assistant instance.
        entry: Config entry with runtime data.
        current_device_ids: Set of device IDs currently known to exist.
    """
    if not hasattr(entry, "runtime_data") or entry.runtime_data is None:
        return

    known_ids = entry.runtime_data.known_device_ids
    stale_ids = known_ids - current_device_ids

    if not stale_ids:
        return

    _LOGGER.info(
        "Detected %d stale device(s) to remove: %s",
        len(stale_ids),
        stale_ids,
    )

    device_registry = dr.async_get(hass)

    for device_id in stale_ids:
        # Find the device entry by its identifier
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, device_id)}
        )
        if device_entry:
            _LOGGER.info(
                "Removing stale device %s (%s) from registry",
                device_id,
                device_entry.name,
            )
            device_registry.async_remove_device(device_entry.id)

    # Update known device IDs
    entry.runtime_data.known_device_ids = current_device_ids

    # Remove coordinators for stale devices
    entry.runtime_data.devices = [
        coord for coord in entry.runtime_data.devices if coord.id not in stale_ids
    ]


async def async_discover_and_add_new_devices(
    hass: HomeAssistant,
    entry: RinnaiConfigEntry,
    current_device_ids: set[str],
) -> None:
    """Discover and add new devices that appeared in the account.

    This implements the HA Quality Scale 'dynamic_devices' requirement.
    Called periodically to discover and add new devices without reload.

    Args:
        hass: Home Assistant instance.
        entry: Config entry with runtime data.
        current_device_ids: Set of device IDs currently known to exist.
    """
    if not hasattr(entry, "runtime_data") or entry.runtime_data is None:
        return

    runtime_data = entry.runtime_data
    known_ids = runtime_data.known_device_ids
    new_ids = current_device_ids - known_ids

    if not new_ids:
        return

    _LOGGER.info(
        "Discovered %d new device(s) to add: %s",
        len(new_ids),
        new_ids,
    )

    # Create coordinators for new devices
    new_coordinators = []
    for device_id in new_ids:
        coordinator = RinnaiDeviceDataUpdateCoordinator(
            hass,
            device_id,
            runtime_data.options,
            entry,
            api_client=runtime_data.client,
            local_client=runtime_data.local_client,
            connection_mode=runtime_data.connection_mode,
        )
        new_coordinators.append(coordinator)
        runtime_data.devices.append(coordinator)
        _LOGGER.info("Created coordinator for new device %s", device_id)

    # Update known device IDs
    runtime_data.known_device_ids = current_device_ids

    # Perform initial data fetch for new devices
    tasks = [coordinator.async_refresh() for coordinator in new_coordinators]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Add entities for new devices using stored callbacks
    await _async_add_entities_for_new_devices(hass, entry, new_coordinators)


async def _async_add_entities_for_new_devices(
    hass: HomeAssistant,
    entry: RinnaiConfigEntry,
    new_coordinators: list[RinnaiDeviceDataUpdateCoordinator],
) -> None:
    """Add entities for newly discovered devices.

    Args:
        hass: Home Assistant instance.
        entry: Config entry with runtime data.
        new_coordinators: List of new device coordinators.
    """
    from .binary_sensor import BINARY_SENSOR_DESCRIPTIONS, RinnaiBinarySensor
    from .sensor import SENSOR_DESCRIPTIONS, RinnaiSensor
    from .switch import RinnaiRecirculationSwitch
    from .water_heater import RinnaiWaterHeater

    runtime_data = entry.runtime_data

    # Add water heater entities
    if Platform.WATER_HEATER in runtime_data.entity_adders:
        water_heater_entities = [
            RinnaiWaterHeater(device) for device in new_coordinators
        ]
        runtime_data.entity_adders[Platform.WATER_HEATER](water_heater_entities)
        _LOGGER.debug(
            "Added %d water heater entities for new devices", len(water_heater_entities)
        )

    # Add sensor entities
    if Platform.SENSOR in runtime_data.entity_adders:
        sensor_entities = [
            RinnaiSensor(device, description)
            for device in new_coordinators
            for description in SENSOR_DESCRIPTIONS
        ]
        runtime_data.entity_adders[Platform.SENSOR](sensor_entities)
        _LOGGER.debug("Added %d sensor entities for new devices", len(sensor_entities))

    # Add binary sensor entities
    if Platform.BINARY_SENSOR in runtime_data.entity_adders:
        binary_sensor_entities = [
            RinnaiBinarySensor(device, description)
            for device in new_coordinators
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
        runtime_data.entity_adders[Platform.BINARY_SENSOR](binary_sensor_entities)
        _LOGGER.debug(
            "Added %d binary sensor entities for new devices",
            len(binary_sensor_entities),
        )

    # Add switch entities
    if Platform.SWITCH in runtime_data.entity_adders:
        switch_entities = [
            RinnaiRecirculationSwitch(device, entry) for device in new_coordinators
        ]
        runtime_data.entity_adders[Platform.SWITCH](switch_entities)
        _LOGGER.debug("Added %d switch entities for new devices", len(switch_entities))


async def async_check_device_changes(
    hass: HomeAssistant,
    entry: RinnaiConfigEntry,
) -> None:
    """Check for device additions and removals.

    This is called periodically to sync devices with the cloud account.
    Implements both stale_devices and dynamic_devices requirements.

    Args:
        hass: Home Assistant instance.
        entry: Config entry with runtime data.
    """
    if not hasattr(entry, "runtime_data") or entry.runtime_data is None:
        return

    runtime_data = entry.runtime_data

    # Only check for cloud/hybrid modes (local mode has fixed devices)
    if runtime_data.connection_mode == CONNECTION_MODE_LOCAL:
        return

    if runtime_data.client is None:
        return

    try:
        user_info = await runtime_data.client.user.get_info()
        devices = user_info.get("devices", {}).get("items", [])
        current_device_ids = {device["id"] for device in devices}

        # Check for stale devices first
        await async_check_and_remove_stale_devices(hass, entry, current_device_ids)

        # Then check for new devices
        await async_discover_and_add_new_devices(hass, entry, current_device_ids)

    except Exception as err:
        _LOGGER.warning("Failed to check for device changes: %s", err)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version.

    Handles migration from two different legacy versions:
    - v1.5.9 (Cloud): Has email, conf_access_token, conf_refresh_token
    - v2.1.9 (Local-only): Has only host (IP address)

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
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        data = {**config_entry.data}

        # Detect which legacy version we're migrating from
        existing_host = data.get(CONF_HOST, "")
        existing_email = data.get(CONF_EMAIL, "")
        existing_access = data.get(CONF_ACCESS_TOKEN, "")
        existing_refresh = data.get(CONF_REFRESH_TOKEN, "")

        if existing_host and not existing_email:
            # v2.1.9 (Local-only) migration: has host but no email
            # This was a local-only setup, migrate to local mode
            _LOGGER.info(
                "Migrating from local-only version (v2.1.x) with host: %s",
                existing_host,
            )
            data[CONF_CONNECTION_MODE] = CONNECTION_MODE_LOCAL
            # Ensure no cloud credentials are set
            data.pop(CONF_EMAIL, None)
            data.pop(CONF_ACCESS_TOKEN, None)
            data.pop(CONF_REFRESH_TOKEN, None)

        elif existing_email:
            # v1.5.9 (Cloud) migration: has email and tokens
            _LOGGER.info(
                "Migrating from cloud version (v1.5.x) with email: %s", existing_email
            )
            data[CONF_CONNECTION_MODE] = CONNECTION_MODE_CLOUD

            if existing_access and existing_refresh:
                # Try to renew tokens using existing credentials
                session = async_get_clientsession(hass)
                client = API(session=session)
                try:
                    await client.async_renew_access_token(
                        existing_email,
                        existing_access,
                        existing_refresh,
                    )
                    _LOGGER.debug("Successfully renewed tokens during migration")

                    # Update tokens in data with refreshed values
                    data[CONF_ACCESS_TOKEN] = client.access_token
                    data[CONF_REFRESH_TOKEN] = client.refresh_token
                except Unauthenticated as err:
                    # Tokens expired or invalid - user needs to re-authenticate
                    _LOGGER.warning(
                        "Existing tokens are invalid, re-authentication required: %s",
                        err,
                    )
                    raise ConfigEntryAuthFailed(
                        "Migration requires re-authentication. "
                        "Please reconfigure the integration with your Rinnai credentials."
                    ) from err
                except RequestError as err:
                    _LOGGER.error("Request error during migration: %s", err)
                    raise ConfigEntryNotReady(
                        f"Unable to connect to Rinnai API during migration: {err}"
                    ) from err
            else:
                # We have email but no valid tokens - need re-authentication
                _LOGGER.warning(
                    "No valid tokens found for migration, re-authentication required"
                )
                raise ConfigEntryAuthFailed(
                    "Migration requires re-authentication. "
                    "Please reconfigure the integration with your Rinnai credentials."
                )
        else:
            # No recognizable config - entry is corrupted
            _LOGGER.error(
                "Config entry has neither email nor host - cannot determine migration path"
            )
            raise ConfigEntryAuthFailed(
                "Config entry format not recognized. Please remove and re-add the integration."
            )

        hass.config_entries.async_update_entry(config_entry, data=data, version=2)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
