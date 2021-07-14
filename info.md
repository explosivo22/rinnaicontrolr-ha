# // Rinnai Control-R for Home Assistant

Support for [Rinnai Control-R Water Heater monitoring and control device](https://www.rinnai.us/tankless-water-heater/accessories/wifi) for Home Assistant.

![release_badge](https://img.shields.io/github/v/release/explosivo22/rinnaicontrolr-ha?style=for-the-badge)
![release_date](https://img.shields.io/github/release-date/explosivo22/rinnaicontrolr-ha?style=for-the-badge)
[![License](https://img.shields.io/github/license/explosivo22/rinnaicontrolr-ha?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

## WARNING

* **THIS LIBRARY ONLY WORKS IF YOU HAVE MIGRATED TO THE RINNAI 2.0 APP.  THIS WILL REQUIRE A FIRMWARE UPDATE TO YOUR CONTROL-R MODULE.**
* [IOS](https://apps.apple.com/us/app/rinnai-control-r-2-0/id1180734911?app=itunes&ign-mpt=uo%3D4)
* [Android](https://play.google.com/store/apps/details?id=com.controlr)

## IMPORTANT NOTES

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

{% if prerelease %}
### NB!: This is a Beta version!

{% else %}

Version 1.0.33 is a total rewrite of the Rinnai Control-R Integration, and no longer supports configuration through Yaml. So if you upgrade to this version from a 1.0.32 release, then you need to do the following:

1. You must remove all references to *rinnai* from your configuration files, and restart HA to clear it.
2. Go back to HACS, and install the latest release. After the installation, you will have the option of entering the Integrations page to configure *Rinnai Control-R Water Heater*.
3. Go to *Settings* and then *Integration* and search for Rinnai Control-R Water Heater
4. Select the Integration, fill out the form and press Save. Once this is done, you should now have all Entities of Rinnai Control-R present in Home Assistance.

Go to [Github](https://github.com/explosivo22/rinnaicontrolr-ha) for Pre-requisites and Setup Instructions.

{% endif %}