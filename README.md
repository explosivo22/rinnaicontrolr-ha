# Rinnai Control-R for Home Assistant

Support for [Rinnai Control-R Water Heater monitoring and control device](https://www.rinnai.us/tankless-water-heater/accessories/wifi) for Home Assistant.

![release_badge](https://img.shields.io/github/v/release/explosivo22/rinnaicontrolr-ha?style=for-the-badge)
![release_date](https://img.shields.io/github/release-date/explosivo22/rinnaicontrolr-ha?style=for-the-badge)
[![License](https://img.shields.io/github/license/explosivo22/rinnaicontrolr-ha?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

## IMPORTANT NOTES

* **THIS LIBRARY ONLY WORKS IF YOU HAVE MIGRATED TO THE RINNAI 2.0 APP.  THIS WILL REQUIRE A FIRMWARE UPDATE TO YOUR CONTROL-R MODULE.**
* [IOS](https://apps.apple.com/us/app/rinnai-control-r-2-0/id1180734911?app=itunes&ign-mpt=uo%3D4)
* [Android](https://play.google.com/store/apps/details?id=com.controlr)

* **RINNAI DOESN'T PROVIDE ANY OFFICIALLY SUPPORTED API, THUS THEIR CHANGES MAY BREAK HASS INTEGRATIONS AT ANY TIME.**

### Features

- water heater:
    * water temperature (&deg;F)
    * set operating temperature
    * start recirculation (on capable models)
- multiple Rinnai devices
- reduced polling of Rinnai webservice to avoid unintentional DDoS

## Installation

#### Versions

The 'master' branch of this custom component is considered unstable, alpha quality and not guaranteed to work.
Please make sure to use one of the official release branches when installing using HACS, see [what has changed in each version](https://github.com/explosivo22/rinnaicontrolr-ha/releases).

### Step 1: Install Custom Components

Make sure that [Home Assistant Community Store (HACS)](https://github.com/custom-components/hacs) is setup, then add the "Integration" repository: `explosivo22/rinnaicontrolr-ha`.

### Step 2: Configuration

#### Configure via UI

Go to Configuration -> Integrations and click the + symbol to configure. Search for Rinnai Control-R Water Heater and enter your email and password.
