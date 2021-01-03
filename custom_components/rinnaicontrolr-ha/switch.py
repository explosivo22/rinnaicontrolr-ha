"""
Support for Rinnai Control-R water heater control recirculation on/off
"""
import logging
import voluptuous as vol
from datetime import timedelta

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from homeassistant.const import ATTR_ENTITY_ID
from .const import ICON_RECIRCULATION, ICON_RECIRCULATION_DISABLED

from . import (
    RinnaiDeviceEntity,
    RINNAI_DOMAIN,
    RINNAI_SERVICE,
    CONF_DEVICE_ID
)

LOG = logging.getLogger(__name__)

# default to 1 minute, don't DDoS Flo servers
SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE_ID): cv.string
})

SERVICE_START_RECIRCULATION = 'start_recirculation'
SERVICE_START_RECIRCULATION_SCHEMA = { vol.Required(ATTR_ENTITY_ID): cv.time_period }
SERVICE_START_RECIRCULATION_SIGNAL = f"{SERVICE_START_RECIRCULATION}_%s"

STATE_RECIRCULATION_ENABLED = 'True'
STATE_RECIRCULATION_DISABLED = 'False'
STATE_RECIRCULATION_DURATION = 30
STATE_PRIORITY_STATUS = 'True'

# pylint: disable=unused-argument
def setup_platform(hass, config, add_switches_callback, discovery_info=None):
    """Setup the Rinnai Control-R Water heater integration."""

    rinnai = hass.data[RINNAI_SERVICE]
    if rinnai == None or not rinnai.is_connected:
        LOG.warning("No connection to Rinnai service, ignoring platform setup")
        return False

    if discovery_info:
        device_id = discovery_info[CONF_DEVICE_ID]
    else:  # manual config
        device_id = config[CONF_DEVICE_ID]

    device = rinnai.getDevices()
    
    # iterate all devices and create a valve switch for each device
    switches = []
    for device_details in device:
        info = device_details.get('info')
        if info.get('recirculation_capable') == "true":
            switch = RinnaiRecirculationToggle(hass, device_details['thing_name'])
            switches.append(switch)

    add_switches_callback(switches)
            
    # register any exposed services
    # NOTE: would have used async_register_entity_service if this platform setup was async

    def start_recirculation_handler(call):
        entity_id = call.data[ATTR_ENTITY_ID]
        async_dispatcher_send(hass, SERVICE_START_RCIRCULATION_SIGNAL.format(entity_id))
    hass.services.register(RINNAI_DOMAIN, SERVICE_START_RECIRCULATION, start_recirculation_handler, SERVICE_START_RECIRCULATION_SCHEMA)

class RinnaiRecirculationToggle(RinnaiDeviceEntity, ToggleEntity):
    """Rinnai switch to turn on/off recirculation."""

    def __init__(self, hass, device_id, user_uuid):
        super().__init__(hass, 'Recirculation Switch', device_id, user_uuid)

        state = self.device_state
        if state:
            self.update()
 
    @property
    def icon(self):
        if self.state == STATE_RECIRCULATION_ENABLED:
            return ICON_RECIRCULATION
        elif self.state == STATE_RECIRCULATION_DISABLED:
            return ICON_RECIRCULATION_DISABLED
        else:
            return ICON_RECIRCULATION_DISABLED

    @property
    def is_on(self):
        """Return true if Flo control valve TARGET is set to open (even if valve has not closed entirely yet)."""
        switch = self.device_state.get('shadow')
        if switch:
            # if target is set to turn on, then return True that the device is on (even if last known is not on)
            recirculation = switch.get('set_recirculation_enabled')
            if recirculation:
                if recirculation == 'true':
                    return True
                else:
                    return False

            return None

    def turn_on(self):
        self.rinnai_service.start_recirculation(self._device_id)

         # Flo device's valve adjustments are NOT instanenous, so update state to indiciate that it WILL be on (eventually)
        self.update_state(STATE_RECIRCULATION_ENABLED)

        # trigger update coordinator to read latest state from service
        self.schedule_update_ha_state(force_refresh=True)

    def turn_off(self):
        self.rinnai_service.stop_recirculation(self._device_id)

        # Flo device's valve adjustments are NOT instanenous, so update state to indiciate that it WILL be off (eventually)
        self.update_state(STATE_RECIRCULATION_DISABLED)

        # trigger update coordinator to read latest state from service
        self.schedule_update_ha_state(force_refresh=True)

    def start_recirculation(self):
        """Run a health test."""
        self.rinnai_service.start_recirculation_test(self._device_id)

    async def async_added_to_hass(self):
        """Run when entity is about to be added to hass."""
        super().async_added_to_hass()

        # register the trigger to handle run_health_test service call
        async_dispatcher_connect(
            self._hass,
            SERVICE_START_RECIRCULATION_SIGNAL.format(self.entity_id),
            self.start_recirculation
        )

    def update_attributes(self):
        """Update various attributes about the valve"""
        switch = self.device_state.get('shadow')
        if switch:
            self._attrs['switch'] = switch
            LOG.debug(f"WOW: {self.device_state}")
            #self._attrs['nickname'] = self.device_state.get['nickname']

            #fwProperties = self.device_state.get('fwProperties')
            #if fwProperties:
            #    self._attrs['valve_actuation_count'] = fwProperties.get('valve_actuation_count')

            #healthTest = self.device_state.get('healthTest')
            #if healthTest:
            #    self._attrs['healthTest'] = healthTest.get('config')

            #self._attrs['lastHeardFromTime'] = self.device_state.get('lastHeardFromTime')

    def update(self):
        if not self.device_state:
            return

        switch = self.device_state.get('shadow')
        if switch:
            recirculation = switch.get('set_recirculation_enabled')

            self.update_attributes()

            # determine if the valve is open or closed
            is_open = None
            if recirculation:
                is_open = recirculation == 'true'

            if is_open == True:
                self.update_state(STATE_RECIRCULATION_ENABLED)
            elif is_open == False:
                self.update_state(STATE_RECIRCULATION_DISABLED)
            else:
                self.update_state(None)

    @property
    def unique_id(self):
        return f"rinnai_recirculation_{self._device_id}"