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
> If you have any other questions or concerns, feel free to reach out to us again.
>
> Nicholas Valencia
> Customer Care Agent

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
    * start recirculation (on capable models)(via [service](#special-rinnai-services))
- multiple Rinnai devices
- reduced polling of Rinnai webservice to avoid unintentional DDoS

## Special Rinnai Services
The Integration adds specific *Rinnai* services. Below is a list of the *Rinnai* specific services:

Service | Parameters | Description
:------------ | :------------ | :-------------
`rinnai.start_recirculation` | `entity_id` - Name of entity to start recirculation on.<br>`recirculation_minutes` - How long to run recirculation | Start recirculation for the amount of time specified
`rinnai.stop_recirculation` | `entity_id` - Name of entity to stop recirculation on. | Stop recirculation on the specified entity

## Installation

#### Versions

The 'master' branch of this custom component is considered unstable, alpha quality and not guaranteed to work.
Please make sure to use one of the official release branches when installing using HACS, see [what has changed in each version](https://github.com/explosivo22/rinnaicontrolr-ha/releases).

### Install Custom Components

1) Make sure that [Home Assistant Community Store (HACS)](https://github.com/custom-components/hacs) is setup.
2) Go to integrations in HACS
3) click the 3 dots in the top right corner and choose `custom repositories`
4) paste the following into the repository input field `https://github.com/explosivo22/rinnaicontrolr-ha` and choose category of `Integration`
5) click add and restart HA to let the integration load
6) Recommended to clear the cache and reload first before adding the integration.
7) Go to settings and choose `Devices & Services`.
8) Click `Add Integration` and search for `Rinnai Control-R Water Heater`
9) Configure the integration.