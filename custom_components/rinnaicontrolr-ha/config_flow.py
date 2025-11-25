"""Config flow for Rinnai integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from aiorinnai import API
from aiorinnai.errors import RequestError

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CONNECTION_MODE,
    CONF_HOST,
    CONF_MAINT_INTERVAL_ENABLED,
    CONF_REFRESH_TOKEN,
    CONNECTION_MODE_CLOUD,
    CONNECTION_MODE_HYBRID,
    CONNECTION_MODE_LOCAL,
    DEFAULT_MAINT_INTERVAL_ENABLED,
    DOMAIN,
    LOGGER,
)
from .local import RinnaiLocalClient


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
        self._local_sysinfo: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - choose connection mode."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_CONNECTION_MODE, default=CONNECTION_MODE_CLOUD
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    {
                                        "value": CONNECTION_MODE_CLOUD,
                                        "label": "Cloud (Rinnai account)",
                                    },
                                    {
                                        "value": CONNECTION_MODE_LOCAL,
                                        "label": "Local (direct connection)",
                                    },
                                    {
                                        "value": CONNECTION_MODE_HYBRID,
                                        "label": "Hybrid (local + cloud fallback)",
                                    },
                                ],
                                translation_key=CONF_CONNECTION_MODE,
                            )
                        ),
                    }
                ),
            )

        self.connection_mode = user_input[CONF_CONNECTION_MODE]

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
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="cloud",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                errors=errors,
            )

        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]

        try:
            self.api = API()
            await self.api.async_login(self.username, self.password)
        except RequestError as request_error:
            LOGGER.error("Error connecting to the Rinnai API: %s", request_error)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="cloud",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                errors=errors,
            )

        user_info = await self.api.user.get_info()
        title = user_info["email"]

        # Set unique ID based on email to prevent duplicate entries
        await self.async_set_unique_id(self.username.lower())
        self._abort_if_unique_id_configured()

        data = {
            CONF_CONNECTION_MODE: CONNECTION_MODE_CLOUD,
            CONF_EMAIL: self.username,
            CONF_ACCESS_TOKEN: self.api.access_token,
            CONF_REFRESH_TOKEN: self.api.refresh_token,
        }

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
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="local",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                    }
                ),
                errors=errors,
                description_placeholders={
                    "port": "9798",
                },
            )

        self.host = user_input[CONF_HOST]

        # Test local connection
        client = RinnaiLocalClient(self.host)
        sysinfo = await client.get_sysinfo()

        if sysinfo is None:
            LOGGER.error("Cannot connect to Rinnai controller at %s", self.host)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="local",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=self.host): str,
                    }
                ),
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
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                errors=errors,
            )

        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]

        try:
            self.api = API()
            await self.api.async_login(self.username, self.password)
        except RequestError as request_error:
            LOGGER.error("Error connecting to the Rinnai API: %s", request_error)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="hybrid_cloud",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
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
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                    }
                ),
                errors=errors,
                description_placeholders={
                    "port": "9798",
                },
            )

        self.host = user_input[CONF_HOST]

        # Test local connection
        client = RinnaiLocalClient(self.host)
        sysinfo = await client.get_sysinfo()

        if sysinfo is None:
            LOGGER.error("Cannot connect to Rinnai controller at %s", self.host)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="hybrid_local",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=self.host): str,
                    }
                ),
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

        data = {
            CONF_CONNECTION_MODE: CONNECTION_MODE_HYBRID,
            CONF_EMAIL: self.username,
            CONF_ACCESS_TOKEN: self.api.access_token,
            CONF_REFRESH_TOKEN: self.api.refresh_token,
            CONF_HOST: self.host,
        }

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
        if user_input is None:
            return self.async_show_form(
                step_id="reauth",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_EMAIL, default=self.context.get(CONF_EMAIL, "")
                        ): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                errors=errors,
            )

        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]

        try:
            self.api = API()
            await self.api.async_login(self.username, self.password)
        except RequestError as request_error:
            LOGGER.error(
                "Reauth: Error connecting to the Rinnai API: %s", request_error
            )
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="reauth",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL, default=self.username): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                errors=errors,
            )
        except Exception as err:
            LOGGER.error("Reauth: Unexpected error: %s", err)
            errors["base"] = "unknown"
            return self.async_show_form(
                step_id="reauth",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL, default=self.username): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                errors=errors,
            )

        # Safely get entry_id from context
        entry_id = self.context.get("entry_id")
        if not entry_id:
            LOGGER.error("Reauth: No entry_id in context; cannot update tokens.")
            return self.async_abort(reason="reauth_failed")
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry:
            self.hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_EMAIL: self.username,
                    CONF_ACCESS_TOKEN: self.api.access_token,
                    CONF_REFRESH_TOKEN: self.api.refresh_token,
                },
            )
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

        if user_input is None:
            current_mode = entry.data.get(CONF_CONNECTION_MODE, CONNECTION_MODE_CLOUD)
            current_host = entry.data.get(CONF_HOST, "")

            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_CONNECTION_MODE, default=current_mode
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    {
                                        "value": CONNECTION_MODE_CLOUD,
                                        "label": "Cloud (Rinnai account)",
                                    },
                                    {
                                        "value": CONNECTION_MODE_LOCAL,
                                        "label": "Local (direct connection)",
                                    },
                                    {
                                        "value": CONNECTION_MODE_HYBRID,
                                        "label": "Hybrid (local + cloud fallback)",
                                    },
                                ],
                                translation_key=CONF_CONNECTION_MODE,
                            )
                        ),
                        vol.Optional(CONF_HOST, default=current_host): str,
                    }
                ),
                errors=errors,
            )

        new_mode = user_input[CONF_CONNECTION_MODE]
        new_host = user_input.get(CONF_HOST, "")

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
                            ): SelectSelector(
                                SelectSelectorConfig(
                                    options=[
                                        {
                                            "value": CONNECTION_MODE_CLOUD,
                                            "label": "Cloud (Rinnai account)",
                                        },
                                        {
                                            "value": CONNECTION_MODE_LOCAL,
                                            "label": "Local (direct connection)",
                                        },
                                        {
                                            "value": CONNECTION_MODE_HYBRID,
                                            "label": "Hybrid (local + cloud fallback)",
                                        },
                                    ],
                                    translation_key=CONF_CONNECTION_MODE,
                                )
                            ),
                            vol.Optional(CONF_HOST, default=new_host): str,
                        }
                    ),
                    errors=errors,
                )

            # Test connection
            client = RinnaiLocalClient(new_host)
            if not await client.test_connection():
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                CONF_CONNECTION_MODE, default=new_mode
                            ): SelectSelector(
                                SelectSelectorConfig(
                                    options=[
                                        {
                                            "value": CONNECTION_MODE_CLOUD,
                                            "label": "Cloud (Rinnai account)",
                                        },
                                        {
                                            "value": CONNECTION_MODE_LOCAL,
                                            "label": "Local (direct connection)",
                                        },
                                        {
                                            "value": CONNECTION_MODE_HYBRID,
                                            "label": "Hybrid (local + cloud fallback)",
                                        },
                                    ],
                                    translation_key=CONF_CONNECTION_MODE,
                                )
                            ),
                            vol.Optional(CONF_HOST, default=new_host): str,
                        }
                    ),
                    errors=errors,
                )

        # Update entry data
        new_data = {**entry.data, CONF_CONNECTION_MODE: new_mode}
        if new_host:
            new_data[CONF_HOST] = new_host

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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MAINT_INTERVAL_ENABLED,
                        default=self._config_entry.options.get(
                            CONF_MAINT_INTERVAL_ENABLED, DEFAULT_MAINT_INTERVAL_ENABLED
                        ),
                    ): bool,
                }
            ),
        )
