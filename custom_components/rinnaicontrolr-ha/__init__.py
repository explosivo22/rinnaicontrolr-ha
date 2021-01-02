import logging
import requests
import asyncio
import time
import voluptuous as vol

from requests.exceptions import HTTPError, ConnectTimeout
from datetime import datetime, timedelta

from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_EMAIL, CONF_PASSWORD, CONF_NAME, CONF_SCAN_INTERVAL, ATTR_ATTRIBUTION)
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.helpers.config_validation as cv

from .const import RINNAI_DOMAIN, ATTRIBUTION, ATTR_CACHE, ATTR_COORDINATOR

from rinnaicontrolr import RinnaiWaterHeater

LOG = logging.getLogger(__name__)

RINNAI_SERVICE = 'rinnai_service'

NOTIFICATION_ID = 'rinnai_notification'

CONF_DEVICES = 'devices'
CONF_DEVICE_ID = 'device_id'

SCAN_INTERVAL = timedelta(seconds=300)

CONFIG_SCHEMA = vol.Schema({
    RINNAI_DOMAIN: vol.Schema({
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICES, default=[]): cv.ensure_list,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup_entry(hass, entry):
    return

def setup(hass, config):
    """Set up the Rinnai Water Heater Control System"""

    conf = config.get(RINNAI_DOMAIN)
    if not conf:
        LOG.error(f"Configuration domain {RINNAI_DOMAIN} cannot be found in config, ignoring setup!")
        return

    email = conf.get(CONF_EMAIL)
    if not email:
        LOG.error(f"Cannot find {CONF_EMAIL} in config!")

    password = conf.get(CONF_PASSWORD)

    try:
        rinnai =  RinnaiWaterHeater(email,password)
        if not rinnai.is_connected:
            LOG.error(f"Could not connect to Rinnai service with {email}")
            return False

        hass.data[RINNAI_SERVICE] = rinnai
        hass.data[RINNAI_DOMAIN] = {
            ATTR_CACHE: {},
            ATTR_COORDINATOR: None
        }

    except (ConnectTimeout, HTTPError) as ex:
        LOG.error(f"Unable to connect to Rinnai service: {str(ex)}")
        hass.components.persistent_notification.create(
            f"Error: {ex}<br />You will need to restart Home Assistant after fixing.",
            title='Rinnai', notification_id=NOTIFICATION_ID
        )
        return False

    devices = conf.get(CONF_DEVICES)

    # if no locations specified, auto discover ALL Rinnai locations/devices for this account
    if not devices:
        for device in rinnai.getDevices():
            devices.append(device['thing_name'])
            LOG.info(
                f"Discovered Rinnai device {device['thing_name']} ({device['device_name']})")

        if not devices:
            LOG.error(
                f"No devices returned from Rinnai service for {email}")
            return True
    else:
        LOG.info(f"Using manually configured Rinnai Devices: {devices}")

    async def async_update_rinnai_data():
        await hass.async_add_executor_job(update_rinnai_data)

    def update_rinnai_data():
        rinnai = hass.data[RINNAI_SERVICE]

        cache = hass.data[RINNAI_DOMAIN][ATTR_CACHE]
        for device in rinnai.getDevices():
            thing_name = device['thing_name']
            cache[thing_name] = device

    # create the Rinnai service update coordinator
    async def async_initialize_coordinator():
        coordinator = DataUpdateCoordinator(
            hass, LOG,
            name=f"Rinnai Webservice",
            update_method=async_update_rinnai_data,
            # set polling intervale (will only be polled if there are subscribers)
            update_interval=conf[CONF_SCAN_INTERVAL]
        )
        hass.data[RINNAI_DOMAIN][ATTR_COORDINATOR] = coordinator
        hass.loop.create_task(coordinator.async_request_refresh())

    # start the coordinator initialization in the hass event loop
    asyncio.run_coroutine_threadsafe(async_initialize_coordinator(), hass.loop).result()

    # create sensors/switches for all configured locations
    for device_id in devices:
        discovery_info = {CONF_DEVICE_ID: device_id}
        for component in ['sensor']:
            discovery.load_platform(
                hass, component, RINNAI_DOMAIN, discovery_info, config)

    return True

class RinnaiEntity(Entity):
    """Base Entity class for Rinnai"""

    def __init__(self, hass, name):
        """Store service upon init"""
        self.hass = hass
        self._hass = hass
        self._name = name
        self._state = None
        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION
        }

    @property
    def rinnai_service(self):
        return self._hass.data[RINNAI_SERVICE]

    @property
    def name(self):
        """Return the display name for this sensor"""
        return self._name

    @property
    def should_poll(self):
        """Rinnai update coordinator notifies through listener when data has been updated"""
        return True # FIXME: temporarily enable polling until coordinator triggers work

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def state(self):
        return self._state

    def update_state(self, state):
        if state != self._state:
            self._state = state

            unit = ''
            if self.unit_of_measurement:
                unit = self.unit_of_measurement
            LOG.info(f"Updated {self.name} to {self.state} {unit}")

        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        self.async_on_remove(
            self._hass.data[RINNAI_DOMAIN][ATTR_COORDINATOR].async_add_listener(
                self.schedule_update_ha_state(force_refresh=True)
            )
        )

class RinnaiDeviceEntity(RinnaiEntity):
    """Base Entity class for Rinnai devices"""

    def __init__(self, hass, name, device_id):
        """Store service upon init."""
        super().__init__(hass, name)

        self._device_id = device_id
        self._attrs['device_id'] = device_id

    @property
    def device_state(self):
        """Get device data shared from the Flo update coordinator"""
        return self._hass.data[RINNAI_DOMAIN][ATTR_CACHE].get(self._device_id)

    def get_telemetry(self, field):
        value = None

        if self.device_state:
            telemetry = self.device_state.get('info')
            if telemetry:
                value = telemetry.get(field)

        if value is None:
            LOG.warning(
                f"Could not get current {field} from Rinnai telemetry: {self.device_state}")
        return value