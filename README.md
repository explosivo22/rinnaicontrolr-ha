# Rinnai Control-R for Home Assistant

Support for [Rinnai Control-R Water Heater monitoring and control device](https://www.rinnai.us/tankless-water-heater/accessories/wifi) for Home Assistant.

![release_badge](https://img.shields.io/github/v/release/explosivo22/rinnaicontrolr-ha?style=for-the-badge)
![release_date](https://img.shields.io/github/release-date/explosivo22/rinnaicontrolr-ha?style=for-the-badge)
[![License](https://img.shields.io/github/license/explosivo22/rinnaicontrolr-ha?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

## IMPORTANT NOTES

* **RINNAI DOESN'T PROVIDE ANY OFFICIALLY SUPPORTED API, THUS THEIR CHANGES MAY BREAK HASS INTEGRATIONS AT ANY TIME.**

### Features

- sensors:
    * water temperature (&deg;F)
- multiple Rinnai devices
- ability to restrict devices (for users with multiple water heaters)
- reduced polling of Rinnai webservice to avoid unintentional DDoS

## Installation

#### Versions

The 'master' branch of this custom component is considered unstable, alpha quality and not guaranteed to work.
Please make sure to use one of the official release branches when installing using HACS, see [what has changed in each version](https://github.com/explosivo22/rinnaicontrolr-ha/releases).

### Step 1: Install Custom Components

Make sure that [Home Assistant Community Store (HACS)](https://github.com/custom-components/hacs) is setup, then add the "Integration" repository: `explosivo22/rinnaicontrolr-ha`.

### Step 2: Configuration

**DO NOT MANUALLY CONFIGURE SENSORS/SWITCHES, ONLY CONFIGURE USING `rinnai:` AS BELOW**. Configuration flow UI is being added in version 1.0 of this integration.

Example configuration:

```yaml
rinnai:
  email: your@email.com
  password: your_flo_password
```

The following is an advanced configuration to limit sensors to a single location (if multiple houses on a single account). The location_id can be found by turning logging to DEBUG for `pyflowater` component, or installing [`pyflowater`](https://github.com/rsnodgrass/pyflowater) and running the `example-client.py` script to show all information about your Flo devices.

```yaml
rinnai:
  email: your@email.com
  password: your_flo_password
  devices:
    - d6b2822a-f2ce-44b0-bbe2-3600a095d494
```

#### Alternative: Configure via UI

**THE UI CONFIGURATION IS CURRENTLY DISABLED**

Version 1.0 added the ability to configure credentials for Rinnai through the Home Assistant UI. Go to Configuration -> Integrations and click the + symbol to configure. Search for Rinnai and enter your username and password.
