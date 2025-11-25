# Rinnai Control-R for Home Assistant

Support for [Rinnai Control-R Water Heater monitoring and control device](https://www.rinnai.us/tankless-water-heater/accessories/wifi) for Home Assistant.

![release_badge](https://img.shields.io/github/v/release/joyfulhouse/rinnaicontrolr-ha?style=for-the-badge)
![release_date](https://img.shields.io/github/release-date/joyfulhouse/rinnaicontrolr-ha?style=for-the-badge)
[![License](https://img.shields.io/github/license/joyfulhouse/rinnaicontrolr-ha?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

> **Note:** This is a fork of [explosivo22/rinnaicontrolr-ha](https://github.com/explosivo22/rinnaicontrolr-ha) with enhanced features including local control, hybrid mode, and improved reliability.

## Features

### Water Heater Control
- **Temperature Control**: Set and monitor water temperature (110°F - 140°F)
- **Operation Mode**: Turn water heater on/off
- **Vacation Mode**: Enable/disable vacation mode for energy savings
- **Recirculation**: Start/stop hot water recirculation (on capable models)

### Connection Modes
- **Cloud Mode**: Uses Rinnai Control-R cloud API (original behavior)
- **Local Mode**: Direct TCP connection to water heater (port 9798) for faster, more reliable control
- **Hybrid Mode**: Local primary with automatic cloud fallback for best of both worlds

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

### Multi-Language Support
Translations available for: English, German, Spanish, French, Italian, Japanese, Korean, Dutch, Polish, Portuguese, Russian, Swedish, Chinese (Simplified & Traditional)

---

## Requirements

> [!WARNING]
> **THIS INTEGRATION ONLY WORKS IF YOU HAVE MIGRATED TO THE RINNAI 2.0 APP.**
> This requires a firmware update to your Control-R module.

- [iOS App](https://apps.apple.com/us/app/rinnai-control-r-2-0/id1180734911)
- [Android App](https://play.google.com/store/apps/details?id=com.controlr)

> [!IMPORTANT]
> **RINNAI DOESN'T PROVIDE ANY OFFICIALLY SUPPORTED API.**
> Their changes may break this integration at any time.

---

## Supported Devices

This integration supports Rinnai tankless water heaters equipped with the Control-R Wi-Fi module:

### Confirmed Compatible Models
| Series | Models | Recirculation |
|--------|--------|---------------|
| **RU Series** (Ultra) | RU160, RU180, RU199 | With external pump |
| **RUR Series** (Ultra with Recirculation) | RUR160, RUR180, RUR199 | Built-in |
| **RE Series** (Efficiency) | RE160, RE180, RE199 | With external pump |
| **RSC Series** (Sensei) | RSC160, RSC180, RSC199 | With external pump |

### Control-R Module Requirements
- **Firmware**: 2.0 or later (check in Rinnai app)
- **Module Type**: Control-R Wi-Fi module (not older modules)
- **Network**: 2.4 GHz Wi-Fi (5 GHz not supported by module)

### Local Mode Requirements
For local/hybrid modes:
- Control-R module must be accessible on your local network
- Port 9798 must not be blocked by firewall
- Static IP or DHCP reservation recommended

---

## Installation

### With HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=joyfulhouse&repository=rinnaicontrolr-ha&category=integration)

Or manually:
1. Open HACS in Home Assistant
2. Click the three dots menu → Custom repositories
3. Add `https://github.com/joyfulhouse/rinnaicontrolr-ha` as an Integration
4. Search for "Rinnai Control-R" and install
5. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/rinnaicontrolr-ha` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant
3. Follow the Setup instructions below

> [!WARNING]
> If installing manually, subscribe to releases to be notified of updates.

---

## Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=rinnai)

Or manually:
1. Navigate to **Settings → Devices & Services**
2. Click **+ ADD INTEGRATION**
3. Search for "Rinnai Control-R"
4. Choose your connection mode:
   - **Cloud**: Enter your Rinnai account email and password
   - **Local**: Enter the IP address of your Control-R module
   - **Hybrid**: Enter both cloud credentials and local IP

### Configuration Options
After setup, configure options via the integration's **Configure** button:

| Option | Description | Default |
|--------|-------------|---------|
| Enable maintenance data | Retrieves detailed sensor data every 5 minutes | Off |
| Recirculation duration | Default duration for recirculation switch (5-300 min) | 10 min |

---

## Services

The integration provides custom services for advanced control:

| Service | Parameters | Description |
|---------|------------|-------------|
| `rinnai.start_recirculation` | `entity_id`, `recirculation_minutes` (5-300) | Start recirculation for specified duration |
| `rinnai.stop_recirculation` | `entity_id` | Stop recirculation immediately |

### Service Example
```yaml
service: rinnai.start_recirculation
target:
  entity_id: water_heater.rinnai_xxxxx_water_heater
data:
  recirculation_minutes: 15
```

---

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

### Temperature Alert
Get notified if outlet temperature drops unexpectedly:

```yaml
automation:
  - alias: "Water Heater Temperature Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.rinnai_xxxxx_outlet_temperature
        below: 100
    condition:
      - condition: state
        entity_id: water_heater.rinnai_xxxxx_water_heater
        state: "gas"
    action:
      - service: notify.mobile_app
        data:
          title: "Water Heater Alert"
          message: "Outlet temperature dropped below 100°F while heating"
```

### Energy Dashboard Integration
Track water heater activity for energy monitoring:

```yaml
# configuration.yaml
template:
  - sensor:
      - name: "Water Heater Daily Cycles"
        state: "{{ states('sensor.rinnai_xxxxx_combustion_cycles') }}"
        unit_of_measurement: "cycles"
        state_class: total_increasing
```

---

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
This is a **known Rinnai firmware bug**. Rinnai has acknowledged this issue:

> "If you are referring to the on demand timers listed in the Control-R 2.0 app, then yes, that is a known issue... For now, if you need the unit to run longer than 5 minutes, I would suggest creating a schedule."

**Workaround**: Create automations that restart recirculation periodically.

#### "Recirculation not configured" error
Your water heater may not have a recirculation pump installed. The RUR series has built-in recirculation; other models require an external pump.

### Authentication Issues

#### "Authentication expired" notification
1. Go to **Settings → Devices & Services → Rinnai**
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
    custom_components.rinnaicontrolr-ha: debug
    aiorinnai: debug
```

After reproducing the issue, check your Home Assistant logs for detailed error messages.

---

## Known Issues

1. **5-minute recirculation limit**: Rinnai firmware bug limits on-demand recirculation to 5 minutes
2. **Cloud API changes**: Rinnai may change their API without notice, potentially breaking the integration
3. **Session injection**: The `aiorinnai` library doesn't support HA's aiohttp session (Platinum requirement blocker)

---

## Quality Scale Compliance

This integration targets Home Assistant Integration Quality Scale:

| Tier | Status |
|------|--------|
| Bronze | ✅ Complete (9/9) |
| Silver | ✅ Complete (7/7) |
| Gold | ⚠️ Partial (4/7) |
| Platinum | ⚠️ Partial (3/4) |

See [CHANGELOG.md](CHANGELOG.md) for detailed compliance information.

---

## Contributing

Contributions are welcome! Please:

1. Fork this repository
2. Create a feature branch
3. Make your changes with appropriate tests
4. Submit a pull request

## Support

- **Issues**: [GitHub Issues](https://github.com/joyfulhouse/rinnaicontrolr-ha/issues)
- **Discussions**: [GitHub Discussions](https://github.com/joyfulhouse/rinnaicontrolr-ha/discussions)

## Credits

- Original integration by [@explosivo22](https://github.com/explosivo22)
- Fork maintained by [@joyfulhouse](https://github.com/joyfulhouse)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
