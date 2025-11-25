# Rinnai Control-R for Home Assistant

Support for [Rinnai Control-R Water Heater monitoring and control device](https://www.rinnai.us/tankless-water-heater/accessories/wifi) for Home Assistant.

![release_badge](https://img.shields.io/github/v/release/explosivo22/rinnaicontrolr-ha?style=for-the-badge)
![release_date](https://img.shields.io/github/release-date/explosivo22/rinnaicontrolr-ha?style=for-the-badge)
[![License](https://img.shields.io/github/license/explosivo22/rinnaicontrolr-ha?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

## KNOWN ISSUES

* **Rinnai currently has a known bug that will cause recirculation to only run for 5 minutes.**
* **OFFICIAL RESPONSE**
> Thank you for contacting Rinnai.
>
> If you are referring to the on demand timers listed in the Control-R 2.0 app, then yes, that is a known issue and I apologize for the inconvenience. I have been told that there's a large update planned for the app and these should issues should be addressed. For now, if you need the unit to run longer than 5 minutes, I would suggest creating a schedule, even if it's just for a short period like an hour.
>
> Nicholas Valencia
> Customer Care Agent

## WARNING

* **THIS LIBRARY ONLY WORKS IF YOU HAVE MIGRATED TO THE RINNAI 2.0 APP. THIS WILL REQUIRE A FIRMWARE UPDATE TO YOUR CONTROL-R MODULE.**
* [iOS](https://apps.apple.com/us/app/rinnai-control-r-2-0/id1180734911?app=itunes&ign-mpt=uo%3D4)
* [Android](https://play.google.com/store/apps/details?id=com.controlr)

## IMPORTANT NOTES

* **RINNAI DOESN'T PROVIDE ANY OFFICIALLY SUPPORTED API, THUS THEIR CHANGES MAY BREAK HASS INTEGRATIONS AT ANY TIME.**

## Features

### Connection Modes
- **Cloud**: Uses Rinnai Control-R cloud API (default)
- **Local**: Direct TCP connection to water heater (port 9798) for faster, more reliable control
- **Hybrid**: Local primary with automatic cloud fallback

### Water Heater Control
- Water temperature control (&deg;F)
- Set operating temperature (110-140&deg;F)
- Operation mode (on/off)
- Vacation/away mode
- Start/stop recirculation (on capable models)

### Sensors
| Sensor | Description |
|--------|-------------|
| Outlet Temperature | Current hot water outlet temperature |
| Inlet Temperature | Cold water inlet temperature |
| Water Flow Rate | Current water flow in GPM |
| Combustion Cycles | Total burner ignition cycles |
| Operation Hours | Total burner operation hours |
| Pump Hours | Recirculation pump run hours |
| Pump Cycles | Recirculation pump cycle count |
| Fan Current | Combustion fan current (mA) |
| Fan Frequency | Combustion fan speed (Hz) |

### Binary Sensors
| Sensor | Description |
|--------|-------------|
| Heating | On when water heater is actively heating |
| Recirculation | On when recirculation pump is running |

### Switch
| Switch | Description |
|--------|-------------|
| Recirculation | Toggle to start/stop recirculation with configurable duration |

### Additional Features
- Multiple Rinnai devices support
- Reduced polling of Rinnai webservice to avoid unintentional DDoS
- Multi-language support (14 languages)
- Proactive token refresh before expiration
- Dynamic device discovery without reload

## Supported Devices

This integration supports Rinnai tankless water heaters equipped with the Control-R Wi-Fi module:

| Series | Models | Recirculation |
|--------|--------|---------------|
| **RU Series** (Ultra) | RU160, RU180, RU199 | With external pump |
| **RUR Series** (Ultra with Recirculation) | RUR160, RUR180, RUR199 | Built-in |
| **RE Series** (Efficiency) | RE160, RE180, RE199 | With external pump |
| **RSC Series** (Sensei) | RSC160, RSC180, RSC199 | With external pump |

### Requirements
- **Firmware**: 2.0 or later (check in Rinnai app)
- **Module Type**: Control-R Wi-Fi module
- **Network**: 2.4 GHz Wi-Fi (5 GHz not supported by module)

### Local Mode Requirements
For local/hybrid modes:
- Control-R module must be accessible on your local network
- Port 9798 must not be blocked by firewall
- Static IP or DHCP reservation recommended

## Special Rinnai Services

Service | Parameters | Description
:------------ | :------------ | :-------------
`rinnai.start_recirculation` | `entity_id` - Name of entity to start recirculation on.<br>`recirculation_minutes` - How long to run recirculation (5-300) | Start recirculation for the amount of time specified
`rinnai.stop_recirculation` | `entity_id` - Name of entity to stop recirculation on. | Stop recirculation on the specified entity

## Installation

#### Versions

The 'master' branch of this custom component is considered unstable, alpha quality and not guaranteed to work.
Please make sure to use one of the official release branches when installing using HACS, see [what has changed in each version](https://github.com/explosivo22/rinnaicontrolr-ha/releases).

#### With HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=explosivo22&repository=rinnaicontrolr-ha&category=integration)

#### Manual
1. Copy the `rinnai` directory from `custom_components` in this repository and place inside your Home Assistant's `custom_components` directory.
2. Restart Home Assistant
3. Follow the instructions in the `Setup` section

> [!WARNING]
> If installing manually, in order to be alerted about new releases, you will need to subscribe to releases from this repository.

## Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=rinnai)

> [!TIP]
> If you are unable to use the button above, follow the steps below:
> 1. Navigate to the Home Assistant Integrations page `(Settings --> Devices & Services)`
> 2. Click the `+ ADD INTEGRATION` button in the lower right-hand corner
> 3. Search for `Rinnai Control-R Water Heater`

### Configuration Options

After setup, configure options via the integration's **Configure** button:

| Option | Description | Default |
|--------|-------------|---------|
| Enable maintenance data | Retrieves detailed sensor data every 5 minutes | Off |
| Recirculation duration | Default duration for recirculation switch (5-300 min) | 10 min |

## Use Cases & Automations

### Morning Hot Water Ready
Start recirculation before your typical shower time:

```yaml
automation:
  - alias: "Morning Hot Water"
    trigger:
      - platform: time
        at: "06:30:00"
    condition:
      - condition: workday
    action:
      - service: rinnai.start_recirculation
        target:
          entity_id: water_heater.rinnai_xxxxx_water_heater
        data:
          recirculation_minutes: 15
```

### Recirculation on Motion
Start recirculation when motion is detected in the bathroom:

```yaml
automation:
  - alias: "Bathroom Motion Recirculation"
    trigger:
      - platform: state
        entity_id: binary_sensor.bathroom_motion
        to: "on"
    condition:
      - condition: state
        entity_id: binary_sensor.rinnai_xxxxx_recirculation
        state: "off"
    action:
      - service: rinnai.start_recirculation
        target:
          entity_id: water_heater.rinnai_xxxxx_water_heater
        data:
          recirculation_minutes: 5
```

### Vacation Mode When Away
Enable vacation mode when everyone leaves:

```yaml
automation:
  - alias: "Enable Vacation Mode When Away"
    trigger:
      - platform: state
        entity_id: group.family
        to: "not_home"
        for:
          hours: 24
    action:
      - service: water_heater.set_away_mode
        target:
          entity_id: water_heater.rinnai_xxxxx_water_heater
        data:
          away_mode: true
```

## Troubleshooting

### Connection Issues

#### Cloud Mode: "Failed to connect" or "Invalid authentication"
1. **Verify credentials**: Ensure you can log into the Rinnai Control-R 2.0 app
2. **Check firmware**: Module must be on firmware 2.0+
3. **Token expiration**: Use the Reconfigure option to re-authenticate
4. **Rate limiting**: Wait a few minutes if you've made many requests

#### Local Mode: "Unable to connect to Rinnai controller"
1. **Verify IP address**: Ping the controller IP from your HA host
2. **Check port**: Ensure port 9798 is accessible (`nc -zv <IP> 9798`)
3. **Network segmentation**: If using VLANs, ensure HA can reach the IoT network
4. **Static IP**: Consider assigning a static IP or DHCP reservation

#### Hybrid Mode: Falling back to cloud frequently
1. Local connection may be unreliable - check network stability
2. Controller might be overloaded - reduce polling frequency
3. Check for firewall rules blocking local connections

### Entity Issues

#### Sensors showing "Unknown" or "Unavailable"
1. **Enable maintenance data**: Some sensors require the maintenance data option enabled
2. **Wait for update**: Sensors update every 60 seconds (maintenance data every 5 minutes)
3. **Check device state**: Ensure the water heater is powered on and connected

#### Temperature readings seem incorrect
1. Temperatures are reported in Fahrenheit from the device
2. Home Assistant converts based on your unit system settings
3. Inlet/outlet temps only update when water is flowing

### Recirculation Issues

#### Recirculation only runs for 5 minutes
This is a **known Rinnai firmware bug** (see Known Issues above).

**Workaround**: Create automations that restart recirculation periodically.

#### "Recirculation not configured" error
Your water heater may not have a recirculation pump installed. The RUR series has built-in recirculation; other models require an external pump.

### Authentication Issues

#### "Authentication expired" notification
1. Go to **Settings -> Devices & Services -> Rinnai**
2. Click **Reconfigure**
3. Re-enter your credentials

#### Frequent re-authentication required
The integration proactively refreshes tokens before expiration. If you're still seeing auth issues:
1. Check your Rinnai account isn't locked
2. Ensure you're not logged in on too many devices
3. Try removing and re-adding the integration

### Debug Logging

Enable debug logging to troubleshoot issues:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.rinnai: debug
    aiorinnai: debug
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
