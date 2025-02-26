"""Config flow for Rinnai integration."""
from typing import Any
from collections.abc import Mapping

from aiorinnai import API
from aiorinnai.errors import RequestError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import callback

from .const import (
    DOMAIN,
    LOGGER,
    CONF_MAINT_INTERVAL_ENABLED,
    DEFAULT_MAINT_INTERVAL_ENABLED,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rinnai."""

    VERSION = 2

    entry: config_entries.ConfigEntry | None

    def __init__(self):
        """Initialize the config flow."""  # Fixed typo from __int__ to __init__
        self.api = None
        self.username = None
        self.password = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_EMAIL): str,  # Changed "email" to CONF_EMAIL
                        vol.Required(CONF_PASSWORD): str,  # Changed "password" to CONF_PASSWORD
                    }
                ),
                errors=errors,
            )
        
        self.username = user_input[CONF_EMAIL]
        self.password = user_input[CONF_PASSWORD]

        try:
            #initialize the api
            self.api = API()
            #start authentication
            await self.api.async_login(self.username, self.password)

        except RequestError as request_error:
            LOGGER.error("Error connecting to the Rinnai API: %s", request_error)
            errors["base"] = "cannot_connect"
            return self.async_show_form(  # Changed from raise CannotConnect to return self.async_show_form
                step_id="user",
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
        first_device_name = user_info["devices"]["items"][0]["id"]
        device_info = await self.api.device.get_info(first_device_name)
        #title = device_info["data"]["getDevice"]["device_name"]

        data = {
            CONF_EMAIL: self.username,
            CONF_ACCESS_TOKEN: self.api.access_token,
            CONF_REFRESH_TOKEN: self.api.refresh_token,
        }

        return self.async_create_entry(
            title=title,
            data=data,
            options={
                CONF_MAINT_INTERVAL_ENABLED: DEFAULT_MAINT_INTERVAL_ENABLED,
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)

class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init", 
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MAINT_INTERVAL_ENABLED,
                        default=self.config_entry.options.get(CONF_MAINT_INTERVAL_ENABLED, DEFAULT_MAINT_INTERVAL_ENABLED),
                    ) : bool,
                }
            ),
        )

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""