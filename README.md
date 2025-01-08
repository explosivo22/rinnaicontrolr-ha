# Rinnai Control-R for Home Assistant

Support for [Rinnai Control-R Water Heater monitoring and control device](https://www.rinnai.us/tankless-water-heater/accessories/wifi) for Home Assistant.

![release_badge](https://img.shields.io/github/v/release/explosivo22/rinnaicontrolr-ha?style=for-the-badge)
![release_date](https://img.shields.io/github/release-date/explosivo22/rinnaicontrolr-ha?style=for-the-badge)
[![License](https://img.shields.io/github/license/explosivo22/rinnaicontrolr-ha?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
[![HA integration usage](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.rinnai.total&style=for-the-badge&logo=home-assistant&label=integration%20usage&color=41BDF5)](https://analytics.home-assistant.io/custom_integrations.json)

<a href="https://www.buymeacoffee.com/Explosivo22" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-blue.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

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

#### With HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=explosivo22&repository=rinnaicontrolr-ha&category=integration)

#### Manual
1. Copy the `rinnai` directory from `custom_components` in this repository and place inside your Home Assistant's `custom_components` directory.
2. Restart Home Assistant
3. Follow the instructions in the `Setup` section

> [!WARNING]
> If installing manually, in order to be alerted about new releases, you will need to subscribe to releases from this repository.

# Setup
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=rinnai)

> [!Tip]
> If you are unable to use the button above, follow the steps below:
> 1. Navigate to the Home Assistant Integrations page `(Settings --> Devices & Services)`
> 2. Click the `+ ADD INTEGRATION` button in the lower right-hand corner
> 3. Search for `Rinnai Control-R Water Heater`