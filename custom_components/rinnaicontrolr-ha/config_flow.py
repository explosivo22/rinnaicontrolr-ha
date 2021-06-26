"""Config flow for Rinnai integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback

from .const import DOMAIN  # pylint:disable=unused-import; pylint:disable=unused-import

from rinnaicontrolr import RinnaiWaterHeater

_LOGGER = logging.getLogger(__name__)

async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.
    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    water_heater = RinnaiWaterHeater(data[CONF_EMAIL], data[CONF_PASSWORD])

    try:
        result = await hass.async_add_executor_job(water_heater.auth)

    except Exception as ex:
        raise InvalidAuth from ex

    if not result:
        _LOGGER.error("Failed to authenticate with Rinnai")
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": result.getDevices().get('info').get('thing_name')}

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rinnai."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        self.schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str
            })

        self._email = None
        self._password = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if not user_input:
            return self._show_form()

        self._email = user_input[CONF_EMAIL]
        self._password = user_input[CONF_PASSWORD]

        return await self._async_rinnai_login()

    async def _async_rinnai_login(self):

        errors = {}

        water_heater = RinnaiWaterHeater(self._email, self._password)

        try:
            result = await self.hass.async_add_executor_job(water_heater.auth)

        except Exception as ex:
            raise InvalidAuth from ex

        if not result:
            _LOGGER.error("Failed to authenticate with Rinnai")
            errors = {"base": "auth_error"}
            raise CannotConnect

        if errors:
            return self._show_form(errors=errors)

        return await self._async_create_entry()

    async def _async_create_entry(self):
        """Create the config entry."""
        config_data = {
            CONF_EMAIL: self._username,
            CONF_PASSWORD: self._password,
        }

        return self.async_create_entry(title=self._email, data=config_data)

    @callback
    def _show_form(self, error=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self.schema,
            error=errors if errors else {},
        )

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""