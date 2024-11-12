"""Config flow for Rinnai integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import  CONF_HOST
from homeassistant.core import callback, HomeAssistant
from homeassistant.util.network import is_host_valid
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .rinnai import WaterHeater

from .const import (
    CONF_MAINT_REFRESH_INTERVAL,
    CONF_REFRESH_INTERVAL,
    DEFAULT_MAINT_REFRESH_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN,
    LOGGER,
    CONF_MAINT_INTERVAL_ENABLED,
    DEFAULT_MAINT_INTERVAL_ENABLED,
)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect.
    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    if not is_host_valid(data[CONF_HOST]):
        raise InvalidHost
    
    try:
        waterHeater = WaterHeater(data[CONF_HOST])
        sysinfo = await waterHeater.get_sysinfo()
        return {"title": sysinfo["sysinfo"]["serial-number"]}
    except ConnectionRefusedError:
        raise ConnectionRefusedError
    except TimeoutError:
        raise TimeoutError

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rinnai."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                    options={
                        CONF_MAINT_INTERVAL_ENABLED: DEFAULT_MAINT_INTERVAL_ENABLED,
                    },
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
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
                    vol.Optional(CONF_MAINT_REFRESH_INTERVAL, default=self.config_entry.options.get(CONF_MAINT_REFRESH_INTERVAL, DEFAULT_MAINT_REFRESH_INTERVAL)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            mode=NumberSelectorMode.SLIDER,
                            min=15,
                            max=300
                        )
                    ),
                    vol.Optional(CONF_REFRESH_INTERVAL, default=self.config_entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            mode=NumberSelectorMode.SLIDER,
                            min=15,
                            max=60
                        )
                    )
                }
            )
        )

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidHost(HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""

class AnotherDevice(HomeAssistantError):
    """Error to indicate that hostname/IP address belongs to another device."""