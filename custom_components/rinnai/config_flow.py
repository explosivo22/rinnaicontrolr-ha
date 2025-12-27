"""Config flow for Rinnai integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from aiorinnai import API
from aiorinnai.errors import (
    RequestError,
    UserNotFound,
    UserNotConfirmed,
    PasswordChangeRequired,
)

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CONNECTION_MODE,
    CONF_HOST,
    CONF_MAINT_INTERVAL_ENABLED,
    CONF_MAINT_INTERVAL_MINUTES,
    CONF_RECIRCULATION_DURATION,
    CONF_REFRESH_TOKEN,
    CONF_SAVE_PASSWORD,
    CONF_STORED_PASSWORD,
    CONNECTION_MODE_CLOUD,
    CONNECTION_MODE_HYBRID,
    CONNECTION_MODE_LOCAL,
    DEFAULT_MAINT_INTERVAL_ENABLED,
    DEFAULT_MAINT_INTERVAL_MINUTES,
    DEFAULT_RECIRCULATION_DURATION,
    DEFAULT_SAVE_PASSWORD,
    DOMAIN,
    LOGGER,
    MAX_MAINT_INTERVAL_MINUTES,
    MIN_MAINT_INTERVAL_MINUTES,
)
from .local import RinnaiLocalClient

# Regex pattern for IPv4 addresses
_IPV4_PATTERN = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


def _is_hostname(host: str) -> bool:
    """Check if the host is a hostname (not an IP address).

    Returns True if the host contains letters or is a .local mDNS name,
    indicating it's a hostname that requires DNS resolution.
    """
    # Check for IPv4 pattern
    if _IPV4_PATTERN.match(host):
        return False
    # Check for IPv6 (contains colons)
    if ":" in host:
        return False
    # Anything else is likely a hostname
    return True


# Common schema components to reduce duplication
CONNECTION_MODE_OPTIONS: list[SelectOptionDict] = [
    {"value": CONNECTION_MODE_CLOUD, "label": "Cloud (Rinnai account)"},
    {"value": CONNECTION_MODE_LOCAL, "label": "Local (direct connection)"},
    {"value": CONNECTION_MODE_HYBRID, "label": "Hybrid (local + cloud fallback)"},
]


def _get_connection_mode_selector() -> SelectSelector:
    """Get the connection mode selector."""
    return SelectSelector(
        SelectSelectorConfig(
            options=CONNECTION_MODE_OPTIONS,
            translation_key=CONF_CONNECTION_MODE,
        )
    )


def _get_cloud_auth_schema(
    default_email: str = "",
    default_save_password: bool = DEFAULT_SAVE_PASSWORD,
) -> vol.Schema:
    """Get the cloud authentication schema.

    Args:
        default_email: Pre-filled email address.
        default_save_password: Default value for save password checkbox.

    Returns:
        Schema for cloud authentication form.
    """
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL, default=default_email): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_SAVE_PASSWORD, default=default_save_password): bool,
        }
    )


def _get_local_schema(default_host: str = "") -> vol.Schema:
    """Get the local connection schema."""
    if default_host:
        return vol.Schema({vol.Required(CONF_HOST, default=default_host): str})
    return vol.Schema({vol.Required(CONF_HOST): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for Rinnai."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.api: API | None = None
        self.username: str | None = None
        self.password: str | None = None
        self.host: str | None = None
        self.connection_mode: str | None = None
        self.save_password: bool = False
        self._local_sysinfo: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - choose connection mode."""
        LOGGER.debug("Config flow: user step initiated")
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_CONNECTION_MODE, default=CONNECTION_MODE_CLOUD
                        ): _get_connection_mode_selector(),
                    }
                ),
            )

        self.connection_mode = user_input[CONF_CONNECTION_MODE]
        LOGGER.debug(
            "Config flow: user selected connection mode '%s'", self.connection_mode
        )

        if self.connection_mode == CONNECTION_MODE_LOCAL:
            return await self.async_step_local()
        elif self.connection_mode == CONNECTION_MODE_HYBRID:
            return await self.async_step_hybrid_cloud()
        else:  # Cloud mode
            return await self.async_step_cloud()

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle cloud authentication step."""
        LOGGER.debug("Config flow: cloud authentication step")
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="cloud",
                data_schema=_get_cloud_auth_schema(),
                errors=errors,
            )

        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]
        self.save_password = user_input.get(CONF_SAVE_PASSWORD, False)
        LOGGER.debug("Config flow: attempting cloud login for %s", self.username)

        try:
            # Use Home Assistant's shared session for connection pooling
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            session = async_get_clientsession(self.hass)
            self.api = API(session=session)
            await self.api.async_login(self.username, self.password)
            LOGGER.debug("Config flow: cloud login successful")
        except UserNotFound:
            LOGGER.error("User account not found for %s", self.username)
            errors["base"] = "invalid_auth"
            return self.async_show_form(
                step_id="cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except UserNotConfirmed:
            LOGGER.error("User email not confirmed for %s", self.username)
            errors["base"] = "user_not_confirmed"
            return self.async_show_form(
                step_id="cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except PasswordChangeRequired:
            LOGGER.error("Password change required for %s", self.username)
            errors["base"] = "password_change_required"
            return self.async_show_form(
                step_id="cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except RequestError as request_error:
            LOGGER.error("Error connecting to the Rinnai API: %s", request_error)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )

        user_info = await self.api.user.get_info()
        title = user_info["email"]
        LOGGER.debug("Config flow: retrieved user info for %s", title)

        # Set unique ID based on email to prevent duplicate entries
        await self.async_set_unique_id(self.username.lower())
        self._abort_if_unique_id_configured()

        data: dict[str, Any] = {
            CONF_CONNECTION_MODE: CONNECTION_MODE_CLOUD,
            CONF_EMAIL: self.username,
            CONF_ACCESS_TOKEN: self.api.access_token,
            CONF_REFRESH_TOKEN: self.api.refresh_token,
        }

        # Store password for automatic re-authentication if user opted in
        if self.save_password and self.password:
            data[CONF_STORED_PASSWORD] = self.password
            LOGGER.debug("Config flow: password will be stored for auto re-auth")

        LOGGER.info("Config flow: creating cloud config entry for %s", title)
        return self.async_create_entry(
            title=title,
            data=data,
            options={
                CONF_MAINT_INTERVAL_ENABLED: DEFAULT_MAINT_INTERVAL_ENABLED,
            },
        )

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle local connection step."""
        LOGGER.debug("Config flow: local connection step")
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="local",
                data_schema=_get_local_schema(),
                errors=errors,
                description_placeholders={"port": "9798"},
            )

        self.host = user_input[CONF_HOST]

        # Test local connection
        client = RinnaiLocalClient(self.host)
        sysinfo = await client.get_sysinfo()

        if sysinfo is None:
            # Provide more specific error message for hostname resolution issues
            if _is_hostname(self.host):
                LOGGER.error(
                    "Cannot resolve hostname %s. mDNS hostnames like "
                    "'rinnai-control-r.local' often fail in containerized environments. "
                    "Please use the device's IP address instead.",
                    self.host,
                )
                errors["base"] = "hostname_resolution_failed"
            else:
                LOGGER.error(
                    "Cannot connect to Rinnai controller at %s on port 9798. "
                    "Please verify the IP address is correct and the device is accessible. "
                    "Consider using Cloud mode if local connection is not possible.",
                    self.host,
                )
                errors["base"] = "local_connection_failed"
            return self.async_show_form(
                step_id="local",
                data_schema=_get_local_schema(default_host=self.host),
                errors=errors,
            )

        # Extract device info
        sysinfo_data = sysinfo.get("sysinfo", {})
        serial_number = sysinfo_data.get("serial-number", "unknown")

        # Set unique ID based on serial number
        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()

        title = f"Rinnai {serial_number}"

        data = {
            CONF_CONNECTION_MODE: CONNECTION_MODE_LOCAL,
            CONF_HOST: self.host,
        }

        return self.async_create_entry(
            title=title,
            data=data,
            options={
                CONF_MAINT_INTERVAL_ENABLED: DEFAULT_MAINT_INTERVAL_ENABLED,
            },
        )

    async def async_step_hybrid_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle hybrid mode - cloud credentials step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="hybrid_cloud",
                data_schema=_get_cloud_auth_schema(),
                errors=errors,
            )

        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]
        self.save_password = user_input.get(CONF_SAVE_PASSWORD, False)

        try:
            # Use Home Assistant's shared session for connection pooling
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            session = async_get_clientsession(self.hass)
            self.api = API(session=session)
            await self.api.async_login(self.username, self.password)
        except UserNotFound:
            LOGGER.error("User account not found for %s", self.username)
            errors["base"] = "invalid_auth"
            return self.async_show_form(
                step_id="hybrid_cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except UserNotConfirmed:
            LOGGER.error("User email not confirmed for %s", self.username)
            errors["base"] = "user_not_confirmed"
            return self.async_show_form(
                step_id="hybrid_cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except PasswordChangeRequired:
            LOGGER.error("Password change required for %s", self.username)
            errors["base"] = "password_change_required"
            return self.async_show_form(
                step_id="hybrid_cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except RequestError as request_error:
            LOGGER.error("Error connecting to the Rinnai API: %s", request_error)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="hybrid_cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )

        # Proceed to local step
        return await self.async_step_hybrid_local()

    async def async_step_hybrid_local(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle hybrid mode - local connection step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="hybrid_local",
                data_schema=_get_local_schema(),
                errors=errors,
                description_placeholders={"port": "9798"},
            )

        self.host = user_input[CONF_HOST]

        # Test local connection
        client = RinnaiLocalClient(self.host)
        sysinfo = await client.get_sysinfo()

        if sysinfo is None:
            # Provide more specific error message for hostname resolution issues
            if _is_hostname(self.host):
                LOGGER.error(
                    "Cannot resolve hostname %s. mDNS hostnames like "
                    "'rinnai-control-r.local' often fail in containerized environments. "
                    "Please use the device's IP address instead.",
                    self.host,
                )
                errors["base"] = "hostname_resolution_failed"
            else:
                LOGGER.error(
                    "Cannot connect to Rinnai controller at %s on port 9798. "
                    "Please verify the IP address is correct and the device is accessible. "
                    "Consider using Cloud mode if local connection is not possible.",
                    self.host,
                )
                errors["base"] = "local_connection_failed"
            return self.async_show_form(
                step_id="hybrid_local",
                data_schema=_get_local_schema(default_host=self.host),
                errors=errors,
            )

        self._local_sysinfo = sysinfo

        # Create entry with both cloud and local config
        # These are set in async_step_hybrid_cloud before reaching this step
        assert self.api is not None
        assert self.username is not None

        user_info = await self.api.user.get_info()
        title = user_info["email"]

        # Set unique ID based on email to prevent duplicate entries
        await self.async_set_unique_id(self.username.lower())
        self._abort_if_unique_id_configured()

        data: dict[str, Any] = {
            CONF_CONNECTION_MODE: CONNECTION_MODE_HYBRID,
            CONF_EMAIL: self.username,
            CONF_ACCESS_TOKEN: self.api.access_token,
            CONF_REFRESH_TOKEN: self.api.refresh_token,
            CONF_HOST: self.host,
        }

        # Store password for automatic re-authentication if user opted in
        if self.save_password and self.password:
            data[CONF_STORED_PASSWORD] = self.password
            LOGGER.debug("Config flow: password will be stored for auto re-auth")

        return self.async_create_entry(
            title=title,
            data=data,
            options={
                CONF_MAINT_INTERVAL_ENABLED: DEFAULT_MAINT_INTERVAL_ENABLED,
            },
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with the user."""
        errors: dict[str, str] = {}
        default_email = str(self.context.get(CONF_EMAIL, ""))

        # Get existing save_password preference from entry
        entry_id = self.context.get("entry_id")
        entry = self.hass.config_entries.async_get_entry(entry_id) if entry_id else None
        default_save_password = bool(
            entry.data.get(CONF_STORED_PASSWORD) if entry else False
        )

        if user_input is None:
            return self.async_show_form(
                step_id="reauth",
                data_schema=_get_cloud_auth_schema(
                    default_email=default_email,
                    default_save_password=default_save_password,
                ),
                errors=errors,
            )

        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]
        self.save_password = user_input.get(CONF_SAVE_PASSWORD, False)

        try:
            # Use Home Assistant's shared session for connection pooling
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            session = async_get_clientsession(self.hass)
            self.api = API(session=session)
            await self.api.async_login(self.username, self.password)
        except UserNotFound:
            LOGGER.error("Reauth: User account not found for %s", self.username)
            errors["base"] = "invalid_auth"
            return self.async_show_form(
                step_id="reauth",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except UserNotConfirmed:
            LOGGER.error("Reauth: User email not confirmed for %s", self.username)
            errors["base"] = "user_not_confirmed"
            return self.async_show_form(
                step_id="reauth",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except PasswordChangeRequired:
            LOGGER.error("Reauth: Password change required for %s", self.username)
            errors["base"] = "password_change_required"
            return self.async_show_form(
                step_id="reauth",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except RequestError as request_error:
            LOGGER.error(
                "Reauth: Error connecting to the Rinnai API: %s", request_error
            )
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="reauth",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )

        # Safely get entry_id from context
        entry_id = self.context.get("entry_id")
        if not entry_id:
            LOGGER.error("Reauth: No entry_id in context; cannot update tokens.")
            return self.async_abort(reason="reauth_failed")

        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry:
            new_data = {
                **entry.data,
                CONF_EMAIL: self.username,
                CONF_ACCESS_TOKEN: self.api.access_token,
                CONF_REFRESH_TOKEN: self.api.refresh_token,
            }

            # Store or remove password based on user preference
            if self.save_password and self.password:
                new_data[CONF_STORED_PASSWORD] = self.password
            elif CONF_STORED_PASSWORD in new_data:
                del new_data[CONF_STORED_PASSWORD]

            self.hass.config_entries.async_update_entry(entry, data=new_data)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(entry.entry_id)
            )
        return self.async_abort(reason="reauth_successful")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration - allows changing connection mode."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None

        if user_input is None:
            current_mode = entry.data.get(CONF_CONNECTION_MODE, CONNECTION_MODE_CLOUD)
            current_host = entry.data.get(CONF_HOST, "")

            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_CONNECTION_MODE, default=current_mode
                        ): _get_connection_mode_selector(),
                        vol.Optional(CONF_HOST, default=current_host): str,
                    }
                ),
                errors=errors,
            )

        new_mode = user_input[CONF_CONNECTION_MODE]
        new_host = user_input.get(CONF_HOST, "")

        # Store for use in subsequent steps
        self.connection_mode = new_mode
        self.host = new_host

        # Validate host if local or hybrid mode
        if new_mode in (CONNECTION_MODE_LOCAL, CONNECTION_MODE_HYBRID):
            if not new_host:
                errors["base"] = "host_required"
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                CONF_CONNECTION_MODE, default=new_mode
                            ): _get_connection_mode_selector(),
                            vol.Optional(CONF_HOST, default=new_host): str,
                        }
                    ),
                    errors=errors,
                )

            # Test connection
            client = RinnaiLocalClient(new_host)
            if not await client.test_connection():
                # Provide more specific error message for hostname resolution issues
                if _is_hostname(new_host):
                    LOGGER.error(
                        "Reconfigure: Cannot resolve hostname %s. mDNS hostnames like "
                        "'rinnai-control-r.local' often fail in containerized environments. "
                        "Please use the device's IP address instead.",
                        new_host,
                    )
                    errors["base"] = "hostname_resolution_failed"
                else:
                    LOGGER.error(
                        "Reconfigure: Cannot connect to Rinnai controller at %s on port 9798. "
                        "Please verify the IP address is correct and the device is accessible. "
                        "Consider using Cloud mode if local connection is not possible.",
                        new_host,
                    )
                    errors["base"] = "local_connection_failed"
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                CONF_CONNECTION_MODE, default=new_mode
                            ): _get_connection_mode_selector(),
                            vol.Optional(CONF_HOST, default=new_host): str,
                        }
                    ),
                    errors=errors,
                )

        # Check if switching to a mode that requires cloud credentials
        needs_cloud = new_mode in (CONNECTION_MODE_CLOUD, CONNECTION_MODE_HYBRID)

        if needs_cloud:
            # Always prompt for cloud credentials to ensure they're valid
            # This handles both new setups and expired token scenarios
            return await self.async_step_reconfigure_cloud()

        # Local-only mode: just update the entry
        new_data = {**entry.data, CONF_CONNECTION_MODE: new_mode}
        if new_host:
            new_data[CONF_HOST] = new_host

        self.hass.config_entries.async_update_entry(entry, data=new_data)
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reconfigure_successful")

    async def async_step_reconfigure_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle cloud credentials for reconfiguration."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None

        # Pre-fill from existing entry
        default_email = entry.data.get(CONF_EMAIL, "")
        default_save_password = bool(entry.data.get(CONF_STORED_PASSWORD))

        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure_cloud",
                data_schema=_get_cloud_auth_schema(
                    default_email=default_email,
                    default_save_password=default_save_password,
                ),
                errors=errors,
            )

        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]
        self.save_password = user_input.get(CONF_SAVE_PASSWORD, False)

        try:
            # Use Home Assistant's shared session for connection pooling
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            session = async_get_clientsession(self.hass)
            self.api = API(session=session)
            await self.api.async_login(self.username, self.password)
        except UserNotFound:
            LOGGER.error("Reconfigure: User account not found for %s", self.username)
            errors["base"] = "invalid_auth"
            return self.async_show_form(
                step_id="reconfigure_cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except UserNotConfirmed:
            LOGGER.error("Reconfigure: User email not confirmed for %s", self.username)
            errors["base"] = "user_not_confirmed"
            return self.async_show_form(
                step_id="reconfigure_cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except PasswordChangeRequired:
            LOGGER.error("Reconfigure: Password change required for %s", self.username)
            errors["base"] = "password_change_required"
            return self.async_show_form(
                step_id="reconfigure_cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )
        except RequestError as request_error:
            LOGGER.error(
                "Reconfigure: Error connecting to the Rinnai API: %s", request_error
            )
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="reconfigure_cloud",
                data_schema=_get_cloud_auth_schema(default_email=self.username),
                errors=errors,
            )

        # Build new data with cloud credentials
        new_data: dict[str, Any] = {
            **entry.data,
            CONF_CONNECTION_MODE: self.connection_mode,
            CONF_EMAIL: self.username,
            CONF_ACCESS_TOKEN: self.api.access_token,
            CONF_REFRESH_TOKEN: self.api.refresh_token,
        }
        if self.host:
            new_data[CONF_HOST] = self.host

        # Store or remove password based on user preference
        if self.save_password and self.password:
            new_data[CONF_STORED_PASSWORD] = self.password
        elif CONF_STORED_PASSWORD in new_data:
            del new_data[CONF_STORED_PASSWORD]

        self.hass.config_entries.async_update_entry(entry, data=new_data)
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reconfigure_successful")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Rinnai."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    def _supports_maintenance_interval(self) -> bool:
        """Check if the connection mode supports configurable maintenance interval.

        Only local and hybrid modes support configurable maintenance intervals.
        Cloud mode uses the default interval.
        """
        connection_mode = self._config_entry.data.get(
            CONF_CONNECTION_MODE, CONNECTION_MODE_CLOUD
        )
        return connection_mode in (CONNECTION_MODE_LOCAL, CONNECTION_MODE_HYBRID)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            LOGGER.debug("Options flow: updating options %s", user_input)
            # For cloud mode, ensure default maintenance interval is used
            if not self._supports_maintenance_interval():
                user_input[CONF_MAINT_INTERVAL_MINUTES] = DEFAULT_MAINT_INTERVAL_MINUTES
            return self.async_create_entry(title="", data=user_input)

        # Build schema based on connection mode
        schema_dict: dict[vol.Optional, Any] = {
            vol.Optional(
                CONF_MAINT_INTERVAL_ENABLED,
                default=self._config_entry.options.get(
                    CONF_MAINT_INTERVAL_ENABLED, DEFAULT_MAINT_INTERVAL_ENABLED
                ),
            ): bool,
        }

        # Only show maintenance interval slider for local and hybrid modes
        if self._supports_maintenance_interval():
            schema_dict[
                vol.Optional(
                    CONF_MAINT_INTERVAL_MINUTES,
                    default=self._config_entry.options.get(
                        CONF_MAINT_INTERVAL_MINUTES, DEFAULT_MAINT_INTERVAL_MINUTES
                    ),
                )
            ] = NumberSelector(
                NumberSelectorConfig(
                    min=MIN_MAINT_INTERVAL_MINUTES,
                    max=MAX_MAINT_INTERVAL_MINUTES,
                    step=1,
                    mode=NumberSelectorMode.SLIDER,
                    unit_of_measurement="minutes",
                )
            )

        # Add recirculation duration option
        schema_dict[
            vol.Optional(
                CONF_RECIRCULATION_DURATION,
                default=self._config_entry.options.get(
                    CONF_RECIRCULATION_DURATION, DEFAULT_RECIRCULATION_DURATION
                ),
            )
        ] = vol.All(vol.Coerce(int), vol.Range(min=5, max=300))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
