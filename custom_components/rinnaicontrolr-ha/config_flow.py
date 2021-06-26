"""Config flow for Rinnai integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback

from .const import DOMAIN  # pylint:disable=unused-import; pylint:disable=unused-import

from rinnaicontrolr import RinnaiWaterHeater

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str
    }
)

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

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                print("EXCEPT")
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                LOG.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""