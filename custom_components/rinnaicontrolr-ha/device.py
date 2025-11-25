"""Rinnai device object."""
from __future__ import annotations

import asyncio
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import jwt

from aiorinnai.api import API, Unauthenticated
from aiorinnai.errors import RequestError
from async_timeout import timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_MAINT_INTERVAL_ENABLED,
    CONF_REFRESH_TOKEN,
    DOMAIN as RINNAI_DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

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
        return value.lower() == 'true'
    return bool(value)


def _is_token_expired(token: str | None, buffer_seconds: int = TOKEN_REFRESH_BUFFER_SECONDS) -> bool:
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

    Handles all communication with the Rinnai API including:
    - Periodic data fetching with automatic retry on transient errors
    - Token refresh and persistence across restarts
    - Entity availability tracking
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: API,
        device_id: str,
        options: dict[str, Any],
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the device coordinator.

        Args:
            hass: Home Assistant instance
            api_client: Authenticated aiorinnai API client
            device_id: Rinnai device identifier
            options: Config entry options
            config_entry: The config entry for token persistence
        """
        self.hass: HomeAssistant = hass
        self.api_client: API = api_client
        self._rinnai_device_id: str = device_id
        self._manufacturer: str = "Rinnai"
        self._device_information: dict[str, Any] | None = None
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

    async def _ensure_valid_token(self) -> None:
        """Ensure the access token is valid, refreshing if necessary.

        This is the KEY fix for the authentication issues. The aiorinnai library
        doesn't proactively refresh tokens, so we check before each API call
        and refresh if the token is expired or expiring soon.

        Raises:
            ConfigEntryAuthFailed: When token refresh fails (triggers reauth flow).
        """
        access_token = getattr(self.api_client, "access_token", None)

        if not _is_token_expired(access_token):
            LOGGER.debug("Access token is still valid")
            return

        LOGGER.info("Access token expired or expiring soon, refreshing...")

        # Get current tokens from config entry (may have been updated)
        current_access = self._config_entry.data.get(CONF_ACCESS_TOKEN)
        current_refresh = self._config_entry.data.get(CONF_REFRESH_TOKEN)
        email = self._config_entry.data.get(CONF_EMAIL)

        if not current_refresh:
            LOGGER.error("No refresh token available, cannot refresh access token")
            raise ConfigEntryAuthFailed("No refresh token available")

        try:
            # Use aiorinnai's token renewal method
            await self.api_client.async_renew_access_token(
                email, current_access, current_refresh
            )
            LOGGER.info("Successfully refreshed access token")

            # Persist the new tokens
            await self._persist_tokens_if_changed()

        except Unauthenticated as err:
            LOGGER.error("Refresh token expired or invalid: %s", err)
            # This will trigger the reauth flow in Home Assistant
            raise ConfigEntryAuthFailed(
                "Authentication expired. Please re-authenticate."
            ) from err
        except RequestError as err:
            LOGGER.error("Failed to refresh token due to network error: %s", err)
            # Don't raise ConfigEntryAuthFailed for network errors
            # Let the retry logic handle transient failures
            raise

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from device via API with retry logic.

        This method implements proactive token refresh to prevent authentication
        failures. Before each API call, it checks if the access token is expired
        or expiring soon, and refreshes it if necessary.

        Returns:
            Device information dictionary from the API.

        Raises:
            ConfigEntryAuthFailed: When authentication fails (triggers reauth flow).
            UpdateFailed: When the API request fails after all retries.
        """
        last_error: Exception | None = None

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                # PROACTIVE TOKEN REFRESH - Key fix for auth issues
                # Check and refresh token BEFORE making API calls
                await self._ensure_valid_token()

                async with timeout(10):
                    device_info = await self.api_client.device.get_info(
                        self._rinnai_device_id
                    )

                # Success - reset error tracking
                self._consecutive_errors = 0
                self._last_error = None

                # Persist tokens if they've been refreshed
                await self._persist_tokens_if_changed()

                # Optionally perform maintenance retrieval
                if self.options.get(CONF_MAINT_INTERVAL_ENABLED, False):
                    try:
                        await self.async_do_maintenance_retrieval()
                    except Unauthenticated as error:
                        LOGGER.error(
                            "Authentication error during maintenance retrieval: %s",
                            error,
                        )
                        raise ConfigEntryAuthFailed from error
                    except RequestError as error:
                        LOGGER.warning(
                            "Maintenance retrieval failed due to request error: %s",
                            error,
                        )
                else:
                    LOGGER.debug(
                        "Skipping maintenance retrieval (disabled in configuration)"
                    )

                LOGGER.debug("Rinnai device data: %s", device_info)
                self._device_information = device_info
                return device_info

            except Unauthenticated as error:
                LOGGER.error("Authentication error: %s", error)
                raise ConfigEntryAuthFailed from error

            except RequestError as error:
                last_error = error
                self._consecutive_errors += 1
                self._last_error = error

                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    LOGGER.warning(
                        "Request failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1,
                        MAX_RETRY_ATTEMPTS,
                        error,
                        RETRY_DELAY,
                    )
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    LOGGER.error(
                        "Request failed after %d attempts: %s",
                        MAX_RETRY_ATTEMPTS,
                        error,
                    )

            except asyncio.TimeoutError as error:
                last_error = error
                self._consecutive_errors += 1
                self._last_error = error

                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    LOGGER.warning(
                        "Request timeout (attempt %d/%d). Retrying in %ds...",
                        attempt + 1,
                        MAX_RETRY_ATTEMPTS,
                        RETRY_DELAY,
                    )
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    LOGGER.error(
                        "Request timeout after %d attempts", MAX_RETRY_ATTEMPTS
                    )

        # All retries exhausted
        raise UpdateFailed(
            f"Failed to fetch device data after {MAX_RETRY_ATTEMPTS} attempts"
        ) from last_error

    async def _persist_tokens_if_changed(self) -> None:
        """Persist tokens to config entry if they've been refreshed."""
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

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self._consecutive_errors < MAX_RETRY_ATTEMPTS and self.last_update_success

    @property
    def id(self) -> str:
        """Return Rinnai device ID."""
        return self._rinnai_device_id

    @property
    def device_name(self) -> str | None:
        """Return device name."""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["device_name"]

    @property
    def manufacturer(self) -> str:
        """Return manufacturer for device."""
        return self._manufacturer

    @property
    def model(self) -> str | None:
        """Return model for device."""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["model"]

    @property
    def firmware_version(self) -> str | None:
        """Return the firmware version for the device."""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["firmware"]

    @property
    def thing_name(self) -> str | None:
        """Return the AWS IoT thing name."""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["thing_name"]

    @property
    def user_uuid(self) -> str | None:
        """Return the user UUID."""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["user_uuid"]

    @property
    def current_temperature(self) -> float | None:
        """Return the current domestic temperature in degrees F."""
        if not self._device_information:
            return None
        temp = self._device_information["data"]["getDevice"]["info"]["domestic_temperature"]
        return float(temp) if temp is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature in degrees F."""
        if not self._device_information:
            return None
        temp = self._device_information["data"]["getDevice"]["shadow"]["set_domestic_temperature"]
        return float(temp) if temp is not None else None

    @property
    def serial_number(self) -> str | None:
        """Return the serial number for the device."""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["info"]["serial_id"]

    @property
    def last_known_state(self) -> str | None:
        """Return the last known activity state."""
        if not self._device_information:
            return None
        return self._device_information["data"]["getDevice"]["activity"]["eventType"]

    @property
    def is_heating(self) -> bool | None:
        """Return True if the device is actively heating water."""
        if not self._device_information:
            return None
        value = self._device_information["data"]["getDevice"]["info"]["domestic_combustion"]
        return _convert_to_bool(value)

    @property
    def is_on(self) -> bool | None:
        """Return True if the device is turned on."""
        if not self._device_information:
            return None
        value = self._device_information["data"]["getDevice"]["shadow"]["set_operation_enabled"]
        return _convert_to_bool(value)

    @property
    def is_recirculating(self) -> bool | None:
        """Return True if recirculation is active."""
        if not self._device_information:
            return None
        value = self._device_information["data"]["getDevice"]["shadow"]["recirculation_enabled"]
        return _convert_to_bool(value)

    @property
    def vacation_mode_on(self) -> bool | None:
        """Return True if vacation mode is enabled."""
        if not self._device_information:
            return None
        value = self._device_information["data"]["getDevice"]["shadow"]["schedule_holiday"]
        if value is None:
            return None
        return _convert_to_bool(value)

    @property
    def outlet_temperature(self) -> float | None:
        """Return the outlet temperature in degrees F."""
        if not self._device_information:
            return None
        temp = self._device_information["data"]["getDevice"]["info"]["m02_outlet_temperature"]
        return float(temp) if temp is not None else None

    @property
    def inlet_temperature(self) -> float | None:
        """Return the inlet temperature in degrees F."""
        if not self._device_information:
            return None
        temp = self._device_information["data"]["getDevice"]["info"]["m08_inlet_temperature"]
        return float(temp) if temp is not None else None

    @property
    def water_flow_rate(self) -> float | None:
        """Return the water flow rate (raw value)."""
        if not self._device_information:
            return None
        rate = self._device_information["data"]["getDevice"]["info"]["m01_water_flow_rate_raw"]
        return float(rate) if rate is not None else None

    @property
    def combustion_cycles(self) -> float | None:
        """Return the combustion cycles count."""
        if not self._device_information:
            return None
        cycles = self._device_information["data"]["getDevice"]["info"]["m04_combustion_cycles"]
        return float(cycles) if cycles is not None else None

    @property
    def operation_hours(self) -> float | None:
        """Return the operation hours."""
        if not self._device_information:
            return None
        hours = self._device_information["data"]["getDevice"]["info"]["operation_hours"]
        return float(hours) if hours is not None else None

    @property
    def pump_hours(self) -> float | None:
        """Return the pump hours."""
        if not self._device_information:
            return None
        hours = self._device_information["data"]["getDevice"]["info"]["m19_pump_hours"]
        return float(hours) if hours is not None else None

    @property
    def fan_current(self) -> float | None:
        """Return the fan current."""
        if not self._device_information:
            return None
        current = self._device_information["data"]["getDevice"]["info"]["m09_fan_current"]
        return float(current) if current is not None else None

    @property
    def fan_frequency(self) -> float | None:
        """Return the fan frequency."""
        if not self._device_information:
            return None
        freq = self._device_information["data"]["getDevice"]["info"]["m05_fan_frequency"]
        return float(freq) if freq is not None else None

    @property
    def pump_cycles(self) -> float | None:
        """Return the pump cycles count."""
        if not self._device_information:
            return None
        cycles = self._device_information["data"]["getDevice"]["info"]["m20_pump_cycles"]
        return float(cycles) if cycles is not None else None

    async def _execute_action(
        self,
        action_name: str,
        action_coro: Any,
    ) -> None:
        """Execute a device action with error handling and proactive token refresh.

        Args:
            action_name: Human-readable name of the action for logging.
            action_coro: The coroutine to execute.

        Raises:
            ConfigEntryAuthFailed: When authentication fails.
            HomeAssistantError: When the action fails after retries.
        """
        from homeassistant.exceptions import HomeAssistantError

        if not self._device_information:
            raise HomeAssistantError(
                f"Cannot {action_name}: device information not yet loaded"
            )

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                # PROACTIVE TOKEN REFRESH before action
                await self._ensure_valid_token()

                await action_coro
                await self._persist_tokens_if_changed()
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
        await self._execute_action(
            "set temperature",
            self.api_client.device.set_temperature(
                self._device_information["data"]["getDevice"], temperature
            ),
        )

    async def async_start_recirculation(self, duration: int) -> None:
        """Start recirculation for the specified duration in minutes."""
        await self._execute_action(
            "start recirculation",
            self.api_client.device.start_recirculation(
                self._device_information["data"]["getDevice"], duration
            ),
        )

    async def async_stop_recirculation(self) -> None:
        """Stop recirculation."""
        await self._execute_action(
            "stop recirculation",
            self.api_client.device.stop_recirculation(
                self._device_information["data"]["getDevice"]
            ),
        )

    async def async_enable_vacation_mode(self) -> None:
        """Enable vacation mode."""
        await self._execute_action(
            "enable vacation mode",
            self.api_client.device.enable_vacation_mode(
                self._device_information["data"]["getDevice"]
            ),
        )

    async def async_disable_vacation_mode(self) -> None:
        """Disable vacation mode."""
        await self._execute_action(
            "disable vacation mode",
            self.api_client.device.disable_vacation_mode(
                self._device_information["data"]["getDevice"]
            ),
        )

    async def async_turn_off(self) -> None:
        """Turn off the water heater."""
        await self._execute_action(
            "turn off",
            self.api_client.device.turn_off(
                self._device_information["data"]["getDevice"]
            ),
        )

    async def async_turn_on(self) -> None:
        """Turn on the water heater."""
        await self._execute_action(
            "turn on",
            self.api_client.device.turn_on(
                self._device_information["data"]["getDevice"]
            ),
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_do_maintenance_retrieval(self) -> None:
        """Perform maintenance data retrieval from the device."""
        if not self._device_information:
            LOGGER.debug(
                "Cannot perform maintenance retrieval: device information not yet loaded"
            )
            return
        try:
            await self.api_client.device.do_maintenance_retrieval(
                self._device_information["data"]["getDevice"]
            )
            LOGGER.debug("Rinnai maintenance retrieval started")
        except Unauthenticated as error:
            LOGGER.error("Authentication error: %s", error)
            raise ConfigEntryAuthFailed from error
        except RequestError as error:
            raise UpdateFailed(error) from error
