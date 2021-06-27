"""Config flow for Rinnai integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN  # pylint:disable=unused-import; pylint:disable=unused-import

from rinnaicontrolr import RinnaiWaterHeater

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required("email"): str, vol.Required("password"): str})

async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.
    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    try:
        water_heater = RinnaiWaterHeater(data[CONF_EMAIL], data[CONF_PASSWORD])
        result = await hass.async_add_executor_job(water_heater.auth())

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
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""