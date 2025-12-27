"""Rinnai device object."""

from __future__ import annotations

import asyncio
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import jwt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_MAINT_INTERVAL_ENABLED,
    CONF_MAINT_INTERVAL_MINUTES,
    CONF_REFRESH_TOKEN,
    CONNECTION_MODE_CLOUD,
    CONNECTION_MODE_HYBRID,
    CONNECTION_MODE_LOCAL,
    DEFAULT_MAINT_INTERVAL_MINUTES,
    DOMAIN as RINNAI_DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    from aiorinnai.api import API

    from .local import RinnaiLocalClient
# Limit concurrent API calls per device
PARALLEL_UPDATES = 1
# Maximum retry attempts for transient errors (cloud mode)
MAX_RETRY_ATTEMPTS = 3
# Delay between retries (seconds, cloud mode)
RETRY_DELAY = 2
# Refresh tokens 5 minutes before expiration
TOKEN_REFRESH_BUFFER_SECONDS = 300
# Local mode retry settings
LOCAL_RETRY_WINDOW_SECONDS = 30.0
LOCAL_INITIAL_RETRY_DELAY = 1.0
LOCAL_MAX_RETRY_DELAY = 8.0
LOCAL_BACKOFF_MULTIPLIER = 2.0


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
        self._last_maintenance_retrieval: float = 0.0
        # Cache cloud device name for hybrid mode (persists even when using local data)
        self._cached_cloud_device_name: str | None = None

        super().__init__(
            hass,
            LOGGER,
            name=f"{RINNAI_DOMAIN}-{device_id}",
            update_interval=timedelta(seconds=60),
        )
        LOGGER.debug(
            "Initialized coordinator for device %s in %s mode",
            device_id,
            connection_mode,
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

        # Use public property documented by aiorinnai API
        access_token = self.api_client.access_token

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
        LOGGER.debug(
            "Fetching data for device %s via %s",
            self._rinnai_device_id,
            self._connection_mode,
        )
        if self._connection_mode == CONNECTION_MODE_LOCAL:
            return await self._update_local()
        elif self._connection_mode == CONNECTION_MODE_HYBRID:
            return await self._update_hybrid()
        else:
            return await self._update_cloud()

    async def _update_local(self) -> dict[str, Any]:
        """Fetch data via local TCP connection with retry and backoff.

        Retries with exponential backoff for up to LOCAL_RETRY_WINDOW_SECONDS
        before marking the device as unavailable. This handles transient network
        issues without impacting the normal polling schedule.
        """
        if self.local_client is None:
            LOGGER.error(
                "Local client not configured for device %s", self._rinnai_device_id
            )
            raise UpdateFailed("Local client not configured")

        start_time = time.monotonic()
        attempt = 0
        retry_delay = LOCAL_INITIAL_RETRY_DELAY
        last_error: Exception | None = None

        while True:
            attempt += 1
            elapsed = time.monotonic() - start_time

            try:
                data = await self.local_client.get_status()
                if data is not None:
                    self._local_data = data
                    self._consecutive_errors = 0
                    self._last_error = None
                    if attempt > 1:
                        LOGGER.info(
                            "Local update succeeded for device %s after %d attempts "
                            "(%.1fs elapsed)",
                            self._rinnai_device_id,
                            attempt,
                            elapsed,
                        )
                    else:
                        LOGGER.debug(
                            "Local update successful for device %s: temp=%s°F, "
                            "heating=%s",
                            self._rinnai_device_id,
                            data.get("domestic_temperature"),
                            data.get("domestic_combustion"),
                        )

                    # Trigger maintenance retrieval for diagnostic sensor fields
                    if self.options.get(CONF_MAINT_INTERVAL_ENABLED, False):
                        await self._maybe_do_maintenance_retrieval()

                    return data

                # data is None - treat as a retriable error
                last_error = Exception("No response from local controller")

            except Exception as error:
                last_error = error

            # Check if we've exceeded the retry window
            elapsed = time.monotonic() - start_time
            if elapsed >= LOCAL_RETRY_WINDOW_SECONDS:
                break

            # Calculate remaining time in window
            remaining = LOCAL_RETRY_WINDOW_SECONDS - elapsed
            actual_delay = min(retry_delay, remaining)

            if actual_delay > 0:
                LOGGER.debug(
                    "Local update attempt %d failed for device %s: %s. "
                    "Retrying in %.1fs (%.1fs remaining in window)",
                    attempt,
                    self._rinnai_device_id,
                    last_error,
                    actual_delay,
                    remaining,
                )
                await asyncio.sleep(actual_delay)

            # Exponential backoff with cap
            retry_delay = min(
                retry_delay * LOCAL_BACKOFF_MULTIPLIER, LOCAL_MAX_RETRY_DELAY
            )

        # All retries exhausted within the window
        self._consecutive_errors += 1
        self._last_error = last_error
        total_elapsed = time.monotonic() - start_time
        LOGGER.warning(
            "Local update failed for device %s after %d attempts over %.1fs: %s",
            self._rinnai_device_id,
            attempt,
            total_elapsed,
            last_error,
        )
        raise UpdateFailed(
            f"Local update failed after {attempt} attempts: {last_error}"
        ) from last_error

    async def _update_cloud(self) -> dict[str, Any]:
        """Fetch data via cloud API with retry logic."""
        from aiorinnai.api import Unauthenticated
        from aiorinnai.errors import RequestError

        if self.api_client is None:
            LOGGER.error(
                "Cloud API client not configured for device %s", self._rinnai_device_id
            )
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

                # Set device info BEFORE maintenance retrieval to avoid race
                # condition where _execute_cloud_action checks it before set
                self._device_information = device_info

                # Extract key values for logging
                device_data = device_info.get("data", {}).get("getDevice", {})
                info = device_data.get("info", {})
                LOGGER.debug(
                    "Cloud update successful for device %s: temp=%s°F, heating=%s",
                    self._rinnai_device_id,
                    info.get("domestic_temperature"),
                    info.get("domestic_combustion"),
                )

                # Maintenance retrieval after device info is set
                if self.options.get(CONF_MAINT_INTERVAL_ENABLED, False):
                    await self._maybe_do_maintenance_retrieval()

                # Cache cloud device name for hybrid mode
                cloud_name = device_data.get("device_name")
                if cloud_name:
                    self._cached_cloud_device_name = cloud_name
                return device_info

            except Unauthenticated as error:
                LOGGER.error("Authentication error: %s", error)
                raise ConfigEntryAuthFailed from error

            except (RequestError, TimeoutError) as error:
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
        local_error: Exception | None = None

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
                    # Fetch cloud device name once for user-friendly naming
                    if not self._cached_cloud_device_name and self.api_client:
                        await self._cache_cloud_device_name()

                    # Trigger maintenance retrieval for diagnostic sensor fields
                    if self.options.get(CONF_MAINT_INTERVAL_ENABLED, False):
                        await self._maybe_do_maintenance_retrieval()

                    return data
            except Exception as error:
                local_error = error
                LOGGER.warning("Hybrid mode: local failed (%s), trying cloud...", error)

        # Fall back to cloud
        if self.api_client is not None:
            try:
                data = await self._update_cloud()
                self._using_fallback = True
                LOGGER.info("Hybrid mode: using cloud fallback")
                return data
            except Exception as cloud_error:
                self._consecutive_errors += 1
                self._last_error = cloud_error
                # Include both errors in the message for better debugging
                if local_error:
                    raise UpdateFailed(
                        f"Both connection methods failed. "
                        f"Local: {local_error}, Cloud: {cloud_error}"
                    ) from cloud_error
                raise

        raise UpdateFailed("No connection method available")

    async def _cache_cloud_device_name(self) -> None:
        """Fetch and cache the cloud device name for hybrid mode.

        This is called once when hybrid mode uses local data, to get the
        user-friendly device name from the cloud API.
        """
        if self.api_client is None:
            return

        try:
            await self._ensure_valid_token()
            async with asyncio.timeout(10):
                device_info = await self.api_client.device.get_info(
                    self._rinnai_device_id
                )
            device_data = device_info.get("data", {}).get("getDevice", {})
            cloud_name = device_data.get("device_name")
            if cloud_name:
                self._cached_cloud_device_name = cloud_name
                LOGGER.debug(
                    "Cached cloud device name '%s' for hybrid mode", cloud_name
                )
        except Exception as error:
            # Non-fatal - we'll just use the serial number fallback
            LOGGER.debug("Could not fetch cloud device name: %s", error)

    async def _persist_tokens_if_changed(self) -> None:
        """Persist tokens to config entry if they've been refreshed."""
        if self.api_client is None:
            return

        current_access = self._config_entry.data.get(CONF_ACCESS_TOKEN)
        current_refresh = self._config_entry.data.get(CONF_REFRESH_TOKEN)

        # Use public properties documented by aiorinnai API
        new_access = self.api_client.access_token
        new_refresh = self.api_client.refresh_token

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
        """Return device name.

        Prioritizes cloud name (user-friendly) over local serial number.
        In hybrid mode, uses cached cloud name even when local data is active.
        """
        # Try current cloud data first
        cloud_name = self._get_cloud_value("data", "getDevice", "device_name")
        if cloud_name:
            return cloud_name
        # Use cached cloud name (for hybrid mode when using local data)
        if self._cached_cloud_device_name:
            return self._cached_cloud_device_name
        # Fall back to serial number for local-only mode
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
        return self._get_value(
            ("data", "getDevice", "firmware"),
            "module_firmware_version",
        )

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
        """Return the operation hours.

        Note: Cloud uses 'operation_hours', local uses 'm03_combustion_hours_raw'.
        """
        hours = self._get_value(
            ("data", "getDevice", "info", "operation_hours"),
            "m03_combustion_hours_raw",
        )
        return float(hours) if hours is not None else None

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

    @property
    def water_flow_control_position(self) -> float | None:
        """Return the water flow control position (percentage)."""
        position = self._get_value(
            ("data", "getDevice", "info", "m07_water_flow_control_position"),
            "m07_water_flow_control_position",
        )
        return float(position) if position is not None else None

    @property
    def heat_exchanger_outlet_temperature(self) -> float | None:
        """Return the heat exchanger outlet temperature in degrees F."""
        temp = self._get_value(
            ("data", "getDevice", "info", "m11_heat_exchanger_outlet_temperature"),
            "m11_heat_exchanger_outlet_temperature",
        )
        return float(temp) if temp is not None else None

    @property
    def bypass_servo_position(self) -> float | None:
        """Return the bypass servo position (percentage)."""
        position = self._get_value(
            ("data", "getDevice", "info", "m12_bypass_servo_position"),
            "m12_bypass_servo_position",
        )
        return float(position) if position is not None else None

    @property
    def outdoor_antifreeze_temperature(self) -> float | None:
        """Return the outdoor antifreeze temperature in degrees F."""
        temp = self._get_value(
            ("data", "getDevice", "info", "m17_outdoor_antifreeze_temperature"),
            "m17_outdoor_antifreeze_temperature",
        )
        return float(temp) if temp is not None else None

    @property
    def exhaust_temperature(self) -> float | None:
        """Return the exhaust temperature in degrees F."""
        temp = self._get_value(
            ("data", "getDevice", "info", "m21_exhaust_temperature"),
            "m21_exhaust_temperature",
        )
        return float(temp) if temp is not None else None

    # =========================================================================
    # Actions - Route to appropriate backend based on connection mode
    # =========================================================================

    async def _execute_action(
        self,
        action_name: str,
        local_method: str | None = None,
        cloud_method: str | None = None,
        *args: Any,
    ) -> None:
        """Execute a device action based on connection mode.

        Args:
            action_name: Human-readable name for logging.
            local_method: Method name on local_client to call.
            cloud_method: Method name on api_client.device to call.
            *args: Arguments to pass to the method.

        In hybrid mode, tries local first, then falls back to cloud.
        """
        if self._connection_mode == CONNECTION_MODE_LOCAL:
            if local_method is None:
                raise HomeAssistantError(f"{action_name} not supported in local mode")
            await self._execute_local_action(action_name, local_method, *args)
        elif self._connection_mode == CONNECTION_MODE_HYBRID:
            # Try local first
            if local_method is not None and self.local_client is not None:
                try:
                    await self._execute_local_action(action_name, local_method, *args)
                    return
                except Exception as error:
                    LOGGER.warning(
                        "Hybrid mode: local %s failed (%s), trying cloud...",
                        action_name,
                        error,
                    )
            # Fall back to cloud
            if cloud_method is not None and self.api_client is not None:
                await self._execute_cloud_action(action_name, cloud_method, *args)
            else:
                raise HomeAssistantError(f"Failed to {action_name}")
        else:  # Cloud mode
            if cloud_method is None:
                raise HomeAssistantError(f"{action_name} not supported in cloud mode")
            await self._execute_cloud_action(action_name, cloud_method, *args)

    async def _execute_local_action(
        self, action_name: str, method_name: str, *args: Any
    ) -> None:
        """Execute an action via local TCP connection."""
        if self.local_client is None:
            raise HomeAssistantError("Local client not configured")

        try:
            method = getattr(self.local_client, method_name)
            result = await method(*args)
            if result is False:
                raise HomeAssistantError(f"Local {action_name} returned failure")
            LOGGER.debug("Local %s successful", action_name)
        except HomeAssistantError:
            raise
        except Exception as error:
            LOGGER.error("Local %s failed: %s", action_name, error)
            raise HomeAssistantError(f"Failed to {action_name}") from error

    async def _execute_cloud_action(
        self, action_name: str, method_name: str, *args: Any
    ) -> None:
        """Execute an action via cloud API with retry logic."""
        from aiorinnai.api import Unauthenticated
        from aiorinnai.errors import RequestError

        if self.api_client is None or self._device_information is None:
            raise HomeAssistantError("Cloud client not configured or no device info")

        device_info = self._device_information["data"]["getDevice"]

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                await self._ensure_valid_token()
                method = getattr(self.api_client.device, method_name)
                await method(device_info, *args)
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
        LOGGER.info(
            "Setting temperature to %d°F on device %s",
            temperature,
            self._rinnai_device_id,
        )
        await self._execute_action(
            "set temperature", "set_temperature", "set_temperature", temperature
        )

    async def async_start_recirculation(self, duration: int = 5) -> None:
        """Start recirculation for the specified duration in minutes."""
        LOGGER.info(
            "Starting recirculation for %d minutes on device %s",
            duration,
            self._rinnai_device_id,
        )
        await self._execute_action(
            "start recirculation",
            "start_recirculation",
            "start_recirculation",
            duration,
        )

    async def async_stop_recirculation(self) -> None:
        """Stop recirculation."""
        LOGGER.info("Stopping recirculation on device %s", self._rinnai_device_id)
        await self._execute_action(
            "stop recirculation", "stop_recirculation", "stop_recirculation"
        )

    async def async_enable_vacation_mode(self) -> None:
        """Enable vacation mode."""
        LOGGER.info("Enabling vacation mode on device %s", self._rinnai_device_id)
        await self._execute_action(
            "enable vacation mode",
            "enable_vacation_mode",
            "enable_vacation_mode",
        )

    async def async_disable_vacation_mode(self) -> None:
        """Disable vacation mode."""
        LOGGER.info("Disabling vacation mode on device %s", self._rinnai_device_id)
        await self._execute_action(
            "disable vacation mode",
            "disable_vacation_mode",
            "disable_vacation_mode",
        )

    async def async_turn_off(self) -> None:
        """Turn off the water heater."""
        LOGGER.info("Turning off water heater on device %s", self._rinnai_device_id)
        await self._execute_action("turn off", "turn_off", "turn_off")

    async def async_turn_on(self) -> None:
        """Turn on the water heater."""
        LOGGER.info("Turning on water heater on device %s", self._rinnai_device_id)
        await self._execute_action("turn on", "turn_on", "turn_on")

    async def _maybe_do_maintenance_retrieval(self) -> None:
        """Perform maintenance data retrieval if enough time has passed."""
        now = time.monotonic()
        # Get configurable interval from options, default to 5 minutes
        interval_minutes = self.options.get(
            CONF_MAINT_INTERVAL_MINUTES, DEFAULT_MAINT_INTERVAL_MINUTES
        )
        min_time_between_maintenance = timedelta(minutes=interval_minutes)

        if (
            now - self._last_maintenance_retrieval
            < min_time_between_maintenance.total_seconds()
        ):
            return

        try:
            await self._execute_action(
                "maintenance retrieval",
                "do_maintenance_retrieval",
                "do_maintenance_retrieval",
            )
            self._last_maintenance_retrieval = now
            LOGGER.debug("Rinnai maintenance retrieval started")
        except Exception as error:
            LOGGER.warning("Maintenance retrieval failed: %s", error)

    async def async_do_maintenance_retrieval(self) -> None:
        """Perform maintenance data retrieval from the device."""
        await self._execute_action(
            "maintenance retrieval",
            "do_maintenance_retrieval",
            "do_maintenance_retrieval",
        )
        self._last_maintenance_retrieval = time.monotonic()
        LOGGER.debug("Rinnai maintenance retrieval started")
