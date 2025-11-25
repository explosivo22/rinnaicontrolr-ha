"""Rinnai device object."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import jwt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_MAINT_INTERVAL_ENABLED,
    CONF_REFRESH_TOKEN,
    CONNECTION_MODE_CLOUD,
    CONNECTION_MODE_HYBRID,
    CONNECTION_MODE_LOCAL,
    DOMAIN as RINNAI_DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    from aiorinnai.api import API
    from .local import RinnaiLocalClient

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)
# Limit concurrent API calls per device
PARALLEL_UPDATES = 1
# Maximum retry attempts for transient errors
MAX_RETRY_ATTEMPTS = 3
# Delay between retries (seconds)
RETRY_DELAY = 2
# Refresh tokens 5 minutes before expiration
TOKEN_REFRESH_BUFFER_SECONDS = 300


def _convert_to_bool(value: Any) -> bool:
    """Convert a string 'true'/'false' to a boolean, or return the boolean value."""
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def _is_token_expired(
    token: str | None, buffer_seconds: int = TOKEN_REFRESH_BUFFER_SECONDS
) -> bool:
    """Check if a JWT token is expired or will expire within buffer_seconds.

    Args:
        token: The JWT token to check (can be None).
        buffer_seconds: Refresh this many seconds before actual expiration.

    Returns:
        True if token is None, invalid, or expiring soon.
    """
    if not token:
        return True

    try:
        # Decode without verification - we just need the expiration time
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp", 0)
        # Return True if token expires within buffer_seconds
        return time.time() > (exp - buffer_seconds)
    except jwt.DecodeError:
        LOGGER.warning("Failed to decode token, treating as expired")
        return True
    except Exception as err:
        LOGGER.warning("Error checking token expiration: %s", err)
        return True


class RinnaiDeviceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Rinnai device data update coordinator.

    Supports three connection modes:
    - Cloud: Uses aiorinnai API with token-based authentication
    - Local: Direct TCP connection to port 9798
    - Hybrid: Local primary with cloud fallback
    """

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        options: dict[str, Any],
        config_entry: ConfigEntry,
        *,
        api_client: API | None = None,
        local_client: RinnaiLocalClient | None = None,
        connection_mode: str = CONNECTION_MODE_CLOUD,
    ) -> None:
        """Initialize the device coordinator.

        Args:
            hass: Home Assistant instance
            device_id: Rinnai device identifier
            options: Config entry options
            config_entry: The config entry for token persistence
            api_client: Cloud API client (required for cloud/hybrid modes)
            local_client: Local TCP client (required for local/hybrid modes)
            connection_mode: One of cloud, local, or hybrid
        """
        self.hass: HomeAssistant = hass
        self.api_client: API | None = api_client
        self.local_client: RinnaiLocalClient | None = local_client
        self._connection_mode: str = connection_mode
        self._rinnai_device_id: str = device_id
        self._manufacturer: str = "Rinnai"
        self._device_information: dict[str, Any] | None = None
        self._local_data: dict[str, Any] | None = None
        self._using_fallback: bool = False
        self.options = options
        self._config_entry = config_entry
        self._consecutive_errors: int = 0
        self._last_error: Exception | None = None

        super().__init__(
            hass,
            LOGGER,
            name=f"{RINNAI_DOMAIN}-{device_id}",
            update_interval=timedelta(seconds=60),
        )

    @property
    def connection_mode(self) -> str:
        """Return the current connection mode."""
        return self._connection_mode

    @property
    def is_using_fallback(self) -> bool:
        """Return True if currently using cloud fallback in hybrid mode."""
        return self._using_fallback

    async def _ensure_valid_token(self) -> None:
        """Ensure the access token is valid, refreshing if necessary.

        Only applies to cloud and hybrid modes.

        Raises:
            ConfigEntryAuthFailed: When token refresh fails (triggers reauth flow).
        """
        if self._connection_mode == CONNECTION_MODE_LOCAL:
            return  # No tokens needed for local mode

        if self.api_client is None:
            return

        from aiorinnai.api import Unauthenticated
        from aiorinnai.errors import RequestError

        access_token = getattr(self.api_client, "access_token", None)

        if not _is_token_expired(access_token):
            LOGGER.debug("Access token is still valid")
            return

        LOGGER.info("Access token expired or expiring soon, refreshing...")

        current_access = self._config_entry.data.get(CONF_ACCESS_TOKEN)
        current_refresh = self._config_entry.data.get(CONF_REFRESH_TOKEN)
        email = self._config_entry.data.get(CONF_EMAIL)

        if not current_refresh:
            LOGGER.error("No refresh token available, cannot refresh access token")
            raise ConfigEntryAuthFailed("No refresh token available")

        try:
            await self.api_client.async_renew_access_token(
                email, current_access, current_refresh
            )
            LOGGER.info("Successfully refreshed access token")
            await self._persist_tokens_if_changed()

        except Unauthenticated as err:
            LOGGER.error("Refresh token expired or invalid: %s", err)
            raise ConfigEntryAuthFailed(
                "Authentication expired. Please re-authenticate."
            ) from err
        except RequestError as err:
            LOGGER.error("Failed to refresh token due to network error: %s", err)
            raise

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from device based on connection mode."""
        if self._connection_mode == CONNECTION_MODE_LOCAL:
            return await self._update_local()
        elif self._connection_mode == CONNECTION_MODE_HYBRID:
            return await self._update_hybrid()
        else:
            return await self._update_cloud()

    async def _update_local(self) -> dict[str, Any]:
        """Fetch data via local TCP connection."""
        if self.local_client is None:
            raise UpdateFailed("Local client not configured")

        try:
            data = await self.local_client.get_status()
            if data is None:
                raise UpdateFailed("Failed to get status from local controller")

            self._local_data = data
            self._consecutive_errors = 0
            self._last_error = None
            LOGGER.debug("Local device data: %s", data)
            return data

        except Exception as error:
            self._consecutive_errors += 1
            self._last_error = error
            LOGGER.error("Local update failed: %s", error)
            raise UpdateFailed(f"Local update failed: {error}") from error

    async def _update_cloud(self) -> dict[str, Any]:
        """Fetch data via cloud API with retry logic."""
        from aiorinnai.api import Unauthenticated
        from aiorinnai.errors import RequestError

        if self.api_client is None:
            raise UpdateFailed("Cloud API client not configured")

        last_error: Exception | None = None

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                await self._ensure_valid_token()

                async with asyncio.timeout(10):
                    device_info = await self.api_client.device.get_info(
                        self._rinnai_device_id
                    )

                self._consecutive_errors = 0
                self._last_error = None
                await self._persist_tokens_if_changed()

                if self.options.get(CONF_MAINT_INTERVAL_ENABLED, False):
                    try:
                        await self.async_do_maintenance_retrieval()
                    except Exception as error:
                        LOGGER.warning("Maintenance retrieval failed: %s", error)

                LOGGER.debug("Cloud device data: %s", device_info)
                self._device_information = device_info
                return device_info

            except Unauthenticated as error:
                LOGGER.error("Authentication error: %s", error)
                raise ConfigEntryAuthFailed from error

            except (RequestError, asyncio.TimeoutError) as error:
                last_error = error
                self._consecutive_errors += 1
                self._last_error = error

                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    LOGGER.warning(
                        "Cloud request failed (attempt %d/%d): %s. Retrying...",
                        attempt + 1,
                        MAX_RETRY_ATTEMPTS,
                        error,
                    )
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    LOGGER.error(
                        "Cloud request failed after %d attempts: %s",
                        MAX_RETRY_ATTEMPTS,
                        error,
                    )

        raise UpdateFailed(
            f"Failed to fetch device data after {MAX_RETRY_ATTEMPTS} attempts"
        ) from last_error

    async def _update_hybrid(self) -> dict[str, Any]:
        """Fetch data with local primary, cloud fallback."""
        # Try local first
        if self.local_client is not None:
            try:
                data = await self.local_client.get_status()
                if data is not None:
                    self._local_data = data
                    self._using_fallback = False
                    self._consecutive_errors = 0
                    self._last_error = None
                    LOGGER.debug("Hybrid mode: using local data")
                    return data
            except Exception as error:
                LOGGER.warning("Hybrid mode: local failed (%s), trying cloud...", error)

        # Fall back to cloud
        if self.api_client is not None:
            try:
                data = await self._update_cloud()
                self._using_fallback = True
                LOGGER.info("Hybrid mode: using cloud fallback")
                return data
            except Exception as error:
                LOGGER.error("Hybrid mode: cloud fallback also failed: %s", error)
                self._consecutive_errors += 1
                self._last_error = error
                raise

        raise UpdateFailed("No connection method available")

    async def _persist_tokens_if_changed(self) -> None:
        """Persist tokens to config entry if they've been refreshed."""
        if self.api_client is None:
            return

        current_access = self._config_entry.data.get(CONF_ACCESS_TOKEN)
        current_refresh = self._config_entry.data.get(CONF_REFRESH_TOKEN)

        new_access = getattr(self.api_client, "access_token", None)
        new_refresh = getattr(self.api_client, "refresh_token", None)

        if (
            new_access
            and new_refresh
            and (new_access != current_access or new_refresh != current_refresh)
        ):
            LOGGER.debug("Persisting refreshed tokens to config entry")
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={
                    **self._config_entry.data,
                    CONF_ACCESS_TOKEN: new_access,
                    CONF_REFRESH_TOKEN: new_refresh,
                },
            )

    # =========================================================================
    # Properties - Unified interface for both cloud and local data
    # =========================================================================

    def _get_cloud_value(self, *keys: str, default: Any = None) -> Any:
        """Get a nested value from cloud data."""
        if not self._device_information:
            return default
        data = self._device_information
        try:
            for key in keys:
                data = data[key]
            return data
        except (KeyError, TypeError):
            return default

    def _get_local_value(self, key: str, default: Any = None) -> Any:
        """Get a value from local data."""
        if not self._local_data:
            return default
        return self._local_data.get(key, default)

    def _get_value(
        self, cloud_keys: tuple[str, ...], local_key: str, default: Any = None
    ) -> Any:
        """Get value from appropriate data source based on connection mode."""
        if self._connection_mode == CONNECTION_MODE_LOCAL:
            return self._get_local_value(local_key, default)
        elif (
            self._connection_mode == CONNECTION_MODE_HYBRID and not self._using_fallback
        ):
            return self._get_local_value(local_key, default)
        else:
            return self._get_cloud_value(*cloud_keys, default=default)

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return (
            self._consecutive_errors < MAX_RETRY_ATTEMPTS and self.last_update_success
        )

    @property
    def id(self) -> str:
        """Return Rinnai device ID."""
        return self._rinnai_device_id

    @property
    def device_name(self) -> str | None:
        """Return device name."""
        cloud_name = self._get_cloud_value("data", "getDevice", "device_name")
        if cloud_name:
            return cloud_name
        # For local mode, use serial number as name
        serial = self._get_local_value("serial_number") or self._rinnai_device_id
        return f"Rinnai {serial}"

    @property
    def manufacturer(self) -> str:
        """Return manufacturer for device."""
        return self._manufacturer

    @property
    def model(self) -> str | None:
        """Return model for device."""
        return self._get_value(
            ("data", "getDevice", "model"),
            "model",
        )

    @property
    def firmware_version(self) -> str | None:
        """Return the firmware version for the device."""
        cloud_fw = self._get_cloud_value("data", "getDevice", "firmware")
        local_fw = self._get_local_value("module_firmware_version")
        if self._connection_mode == CONNECTION_MODE_LOCAL:
            return str(local_fw) if local_fw else None
        elif (
            self._connection_mode == CONNECTION_MODE_HYBRID and not self._using_fallback
        ):
            return str(local_fw) if local_fw else None
        return cloud_fw

    @property
    def thing_name(self) -> str | None:
        """Return the AWS IoT thing name (cloud only)."""
        return self._get_cloud_value("data", "getDevice", "thing_name")

    @property
    def user_uuid(self) -> str | None:
        """Return the user UUID (cloud only)."""
        return self._get_cloud_value("data", "getDevice", "user_uuid")

    @property
    def serial_number(self) -> str | None:
        """Return the serial number for the device."""
        return self._get_value(
            ("data", "getDevice", "info", "serial_id"),
            "heater_serial_number",
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current domestic temperature in degrees F."""
        temp = self._get_value(
            ("data", "getDevice", "info", "domestic_temperature"),
            "domestic_temperature",
        )
        return float(temp) if temp is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature in degrees F."""
        temp = self._get_value(
            ("data", "getDevice", "shadow", "set_domestic_temperature"),
            "set_domestic_temperature",
        )
        return float(temp) if temp is not None else None

    @property
    def last_known_state(self) -> str | None:
        """Return the last known activity state (cloud only)."""
        return self._get_cloud_value("data", "getDevice", "activity", "eventType")

    @property
    def is_heating(self) -> bool | None:
        """Return True if the device is actively heating water."""
        value = self._get_value(
            ("data", "getDevice", "info", "domestic_combustion"),
            "domestic_combustion",
        )
        if value is None:
            return None
        return _convert_to_bool(value)

    @property
    def is_on(self) -> bool | None:
        """Return True if the device is turned on."""
        value = self._get_value(
            ("data", "getDevice", "shadow", "set_operation_enabled"),
            "operation_enabled",
        )
        if value is None:
            return None
        return _convert_to_bool(value)

    @property
    def is_recirculating(self) -> bool | None:
        """Return True if recirculation is active."""
        value = self._get_value(
            ("data", "getDevice", "shadow", "recirculation_enabled"),
            "recirculation_enabled",
        )
        if value is None:
            return None
        return _convert_to_bool(value)

    @property
    def vacation_mode_on(self) -> bool | None:
        """Return True if vacation mode is enabled."""
        value = self._get_value(
            ("data", "getDevice", "shadow", "schedule_holiday"),
            "schedule_holiday",
        )
        if value is None:
            return None
        return _convert_to_bool(value)

    @property
    def outlet_temperature(self) -> float | None:
        """Return the outlet temperature in degrees F."""
        temp = self._get_value(
            ("data", "getDevice", "info", "m02_outlet_temperature"),
            "m02_outlet_temperature",
        )
        return float(temp) if temp is not None else None

    @property
    def inlet_temperature(self) -> float | None:
        """Return the inlet temperature in degrees F."""
        temp = self._get_value(
            ("data", "getDevice", "info", "m08_inlet_temperature"),
            "m08_inlet_temperature",
        )
        return float(temp) if temp is not None else None

    @property
    def water_flow_rate(self) -> float | None:
        """Return the water flow rate (raw value)."""
        rate = self._get_value(
            ("data", "getDevice", "info", "m01_water_flow_rate_raw"),
            "m01_water_flow_rate_raw",
        )
        return float(rate) if rate is not None else None

    @property
    def combustion_cycles(self) -> float | None:
        """Return the combustion cycles count."""
        cycles = self._get_value(
            ("data", "getDevice", "info", "m04_combustion_cycles"),
            "m04_combustion_cycles",
        )
        return float(cycles) if cycles is not None else None

    @property
    def operation_hours(self) -> float | None:
        """Return the operation hours."""
        # Cloud uses operation_hours, local uses m03_combustion_hours_raw
        cloud_hours = self._get_cloud_value(
            "data", "getDevice", "info", "operation_hours"
        )
        local_hours = self._get_local_value("m03_combustion_hours_raw")
        if self._connection_mode == CONNECTION_MODE_LOCAL:
            return float(local_hours) if local_hours is not None else None
        elif (
            self._connection_mode == CONNECTION_MODE_HYBRID and not self._using_fallback
        ):
            return float(local_hours) if local_hours is not None else None
        return float(cloud_hours) if cloud_hours is not None else None

    @property
    def pump_hours(self) -> float | None:
        """Return the pump hours."""
        hours = self._get_value(
            ("data", "getDevice", "info", "m19_pump_hours"),
            "m19_pump_hours",
        )
        return float(hours) if hours is not None else None

    @property
    def fan_current(self) -> float | None:
        """Return the fan current."""
        current = self._get_value(
            ("data", "getDevice", "info", "m09_fan_current"),
            "m09_fan_current",
        )
        return float(current) if current is not None else None

    @property
    def fan_frequency(self) -> float | None:
        """Return the fan frequency."""
        freq = self._get_value(
            ("data", "getDevice", "info", "m05_fan_frequency"),
            "m05_fan_frequency",
        )
        return float(freq) if freq is not None else None

    @property
    def pump_cycles(self) -> float | None:
        """Return the pump cycles count."""
        cycles = self._get_value(
            ("data", "getDevice", "info", "m20_pump_cycles"),
            "m20_pump_cycles",
        )
        return float(cycles) if cycles is not None else None

    # =========================================================================
    # Actions - Route to appropriate backend based on connection mode
    # =========================================================================

    async def _execute_action(
        self,
        action_name: str,
        local_action: Callable[[], Awaitable[bool]] | None = None,
        cloud_action: Callable[[], Awaitable[Any]] | None = None,
    ) -> None:
        """Execute a device action based on connection mode.

        Args:
            action_name: Human-readable name for logging.
            local_action: Callable that returns a coroutine for local execution.
            cloud_action: Callable that returns a coroutine for cloud execution.

        In hybrid mode, tries local first, then falls back to cloud.
        """
        if self._connection_mode == CONNECTION_MODE_LOCAL:
            if local_action is None:
                raise HomeAssistantError(f"{action_name} not supported in local mode")
            await self._execute_local_action(action_name, local_action)
        elif self._connection_mode == CONNECTION_MODE_HYBRID:
            # Try local first
            if local_action is not None and self.local_client is not None:
                try:
                    await self._execute_local_action(action_name, local_action)
                    return
                except Exception as error:
                    LOGGER.warning(
                        "Hybrid mode: local %s failed (%s), trying cloud...",
                        action_name,
                        error,
                    )
            # Fall back to cloud
            if cloud_action is not None and self.api_client is not None:
                await self._execute_cloud_action(action_name, cloud_action)
            else:
                raise HomeAssistantError(f"Failed to {action_name}")
        else:  # Cloud mode
            if cloud_action is None:
                raise HomeAssistantError(f"{action_name} not supported in cloud mode")
            await self._execute_cloud_action(action_name, cloud_action)

    async def _execute_local_action(
        self, action_name: str, action_factory: Callable[[], Awaitable[bool]]
    ) -> None:
        """Execute an action via local TCP connection."""
        try:
            result = await action_factory()
            if result is False:
                raise HomeAssistantError(f"Local {action_name} returned failure")
            LOGGER.debug("Local %s successful", action_name)
        except Exception as error:
            LOGGER.error("Local %s failed: %s", action_name, error)
            raise HomeAssistantError(f"Failed to {action_name}") from error

    async def _execute_cloud_action(
        self, action_name: str, action_factory: Callable[[], Awaitable[Any]]
    ) -> None:
        """Execute an action via cloud API with retry logic."""
        from aiorinnai.api import Unauthenticated
        from aiorinnai.errors import RequestError

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                await self._ensure_valid_token()
                await action_factory()
                await self._persist_tokens_if_changed()
                LOGGER.debug("Cloud %s successful", action_name)
                return
            except Unauthenticated as error:
                LOGGER.error("Authentication error during %s: %s", action_name, error)
                raise ConfigEntryAuthFailed from error
            except RequestError as error:
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    LOGGER.warning(
                        "%s failed (attempt %d/%d): %s. Retrying...",
                        action_name,
                        attempt + 1,
                        MAX_RETRY_ATTEMPTS,
                        error,
                    )
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    LOGGER.error(
                        "%s failed after %d attempts: %s",
                        action_name,
                        MAX_RETRY_ATTEMPTS,
                        error,
                    )
                    raise HomeAssistantError(
                        f"Failed to {action_name} after {MAX_RETRY_ATTEMPTS} attempts"
                    ) from error

    async def async_set_temperature(self, temperature: int) -> None:
        """Set the target temperature."""
        local_action = None
        cloud_action = None

        if self.local_client is not None:
            local_client = self.local_client  # Capture for closure

            def do_local() -> Awaitable[bool]:
                return local_client.set_temperature(temperature)

            local_action = do_local

        if self.api_client is not None and self._device_information:
            api_client = self.api_client  # Capture for closure
            device_info = self._device_information["data"]["getDevice"]

            def do_cloud() -> Awaitable[Any]:
                return api_client.device.set_temperature(device_info, temperature)

            cloud_action = do_cloud

        await self._execute_action("set temperature", local_action, cloud_action)

    async def async_start_recirculation(self, duration: int) -> None:
        """Start recirculation for the specified duration in minutes."""
        local_action = None
        cloud_action = None

        if self.local_client is not None:
            local_client = self.local_client  # Capture for closure

            def do_local() -> Awaitable[bool]:
                return local_client.start_recirculation(duration)

            local_action = do_local

        if self.api_client is not None and self._device_information:
            api_client = self.api_client  # Capture for closure
            device_info = self._device_information["data"]["getDevice"]

            def do_cloud() -> Awaitable[Any]:
                return api_client.device.start_recirculation(device_info, duration)

            cloud_action = do_cloud

        await self._execute_action("start recirculation", local_action, cloud_action)

    async def async_stop_recirculation(self) -> None:
        """Stop recirculation."""
        local_action = None
        cloud_action = None

        if self.local_client is not None:
            local_client = self.local_client  # Capture for closure

            def do_local() -> Awaitable[bool]:
                return local_client.stop_recirculation()

            local_action = do_local

        if self.api_client is not None and self._device_information:
            api_client = self.api_client  # Capture for closure
            device_info = self._device_information["data"]["getDevice"]

            def do_cloud() -> Awaitable[Any]:
                return api_client.device.stop_recirculation(device_info)

            cloud_action = do_cloud

        await self._execute_action("stop recirculation", local_action, cloud_action)

    async def async_enable_vacation_mode(self) -> None:
        """Enable vacation mode."""
        local_action = None
        cloud_action = None

        if self.local_client is not None:
            local_client = self.local_client  # Capture for closure

            def do_local() -> Awaitable[bool]:
                return local_client.enable_vacation_mode()

            local_action = do_local

        if self.api_client is not None and self._device_information:
            api_client = self.api_client  # Capture for closure
            device_info = self._device_information["data"]["getDevice"]

            def do_cloud() -> Awaitable[Any]:
                return api_client.device.enable_vacation_mode(device_info)

            cloud_action = do_cloud

        await self._execute_action("enable vacation mode", local_action, cloud_action)

    async def async_disable_vacation_mode(self) -> None:
        """Disable vacation mode."""
        local_action = None
        cloud_action = None

        if self.local_client is not None:
            local_client = self.local_client  # Capture for closure

            def do_local() -> Awaitable[bool]:
                return local_client.disable_vacation_mode()

            local_action = do_local

        if self.api_client is not None and self._device_information:
            api_client = self.api_client  # Capture for closure
            device_info = self._device_information["data"]["getDevice"]

            def do_cloud() -> Awaitable[Any]:
                return api_client.device.disable_vacation_mode(device_info)

            cloud_action = do_cloud

        await self._execute_action("disable vacation mode", local_action, cloud_action)

    async def async_turn_off(self) -> None:
        """Turn off the water heater."""
        local_action = None
        cloud_action = None

        if self.local_client is not None:
            local_client = self.local_client  # Capture for closure

            def do_local() -> Awaitable[bool]:
                return local_client.turn_off()

            local_action = do_local

        if self.api_client is not None and self._device_information:
            api_client = self.api_client  # Capture for closure
            device_info = self._device_information["data"]["getDevice"]

            def do_cloud() -> Awaitable[Any]:
                return api_client.device.turn_off(device_info)

            cloud_action = do_cloud

        await self._execute_action("turn off", local_action, cloud_action)

    async def async_turn_on(self) -> None:
        """Turn on the water heater."""
        local_action = None
        cloud_action = None

        if self.local_client is not None:
            local_client = self.local_client  # Capture for closure

            def do_local() -> Awaitable[bool]:
                return local_client.turn_on()

            local_action = do_local

        if self.api_client is not None and self._device_information:
            api_client = self.api_client  # Capture for closure
            device_info = self._device_information["data"]["getDevice"]

            def do_cloud() -> Awaitable[Any]:
                return api_client.device.turn_on(device_info)

            cloud_action = do_cloud

        await self._execute_action("turn on", local_action, cloud_action)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_do_maintenance_retrieval(self) -> None:
        """Perform maintenance data retrieval from the device."""
        local_action = None
        cloud_action = None

        if self.local_client is not None:
            local_client = self.local_client  # Capture for closure

            def do_local() -> Awaitable[bool]:
                return local_client.do_maintenance_retrieval()

            local_action = do_local

        if self.api_client is not None and self._device_information:
            api_client = self.api_client  # Capture for closure
            device_info = self._device_information["data"]["getDevice"]

            def do_cloud() -> Awaitable[Any]:
                return api_client.device.do_maintenance_retrieval(device_info)

            cloud_action = do_cloud

        try:
            await self._execute_action(
                "maintenance retrieval", local_action, cloud_action
            )
            LOGGER.debug("Rinnai maintenance retrieval started")
        except Exception as error:
            LOGGER.warning("Maintenance retrieval failed: %s", error)
