import logging
import asyncio
import time
from datetime import datetime, timedelta

import async_timeout
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN

from .const import DOMAIN

from rinnaicontrolr import RinnaiWaterHeater

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["water_heater"]

RINNAI_SERVICE = 'rinnai_service'

NOTIFICATION_ID = 'rinnai_notification'

CONF_DEVICES = 'devices'
CONF_DEVICE_ID = 'device_id'

ATTR_DURATION = 'duration'

SCAN_INTERVAL = timedelta(seconds=300)

CONFIG_SCHEMA = vol.Schema({
    RINNAI_DOMAIN: vol.Schema({
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICES, default=[]): cv.ensure_list,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_START_RECIRCULATION = "start_recirculation"
START_RECIRCULATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required(ATTR_DURATION): cv.positive_int,
    }
)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Rinnai component"""
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Rinnai from config entry"""
    user = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    for ar in entry.data:
        _LOGGER.debug(ar)

    try:
        hass.data[DOMAIN][entry.entry_id][RINNAI] = rinnai = RinnaiWaterHeater(
            entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
        )
    except RequestError as err:
        raise ConfigEntryNotReady from err

    rinnai_devices = rinnai.getDevices()

    hass.data[DOMAIN][entry.entry_id]["devices"] = devices = [
        RinnaiDeviceDataUpdateCoordinator(hass, rinnai, device["thing_name"])
        for device in rinnai_devices["info"]
    ]
    
    tasks = [device.async_refresh() for device in devices]
    await asyncio.gather(*tasks)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    
    return True

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

    def service_callback(call):
        if call.service == SERVICE_START_RECIRCULATION:
            rinnai_start_recirculation(hass, call)

    async def async_service_callback(call):
        await hass.async_add_executor_job(service_callback, call)

    hass.services.async_register(
        RINNAI_DOMAIN,
        SERVICE_START_RECIRCULATION,
        async_service_callback,
        schema=START_RECIRCULATION_SCHEMA,
    )

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
        for component in ['sensor', 'water_heater']:
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

    def __init__(self, hass, name, device_id, user_uuid):
        """Store service upon init."""
        super().__init__(hass, name)

        self._device_id = device_id
        self._attrs['device_id'] = device_id
        self._user_uuid = user_uuid
        self._attrs['user_uuid'] = user_uuid

    @property
    def device_state(self):
        """Get device data shared from the Rinnai update coordinator"""
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

def get_entity_from_domain(hass, domains, entity_id):
    domains = domains if isinstance(domains, list) else [domains]
    for domain in domains:
        component = hass.data.get(domain)
        if component is None:
            raise HomeAssistantError("{} component not set up".format(domain))
        entity = component.get_entity(entity_id)
        if entity is not None:
            return entity
    raise HomeAssistantError("{} not found in {}".format(entity_id, ",".join(domains)))

def rinnai_start_recirculation(hass, call):
    for entity_id in call.data["entity_id"]:
        try:
            duration = call.data["duration"]
            device = get_entity_from_domain(
                hass, [WATER_HEATER_DOMAIN], entity_id
            )
            device.start_recirculation(duration=duration)
        except HomeAssistantError:
            LOG.info("{} water heater device not found".format(entity_id))
