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

## ⚠️ Breaking Change in v2.0.0 - Migration Required

Version 2.0.0 includes a **breaking change**: the integration directory has been renamed from `rinnaicontrolr-ha` to `rinnai`.

**You MUST perform a clean install:**

1. **Remove the integration** from Settings → Devices & Services
2. **Remove via HACS** → Integrations → Rinnai → Remove
3. **Manually delete** the old folder: `custom_components/rinnaicontrolr-ha/`
4. **Restart Home Assistant**
5. **Install v2.0.0** via HACS
6. **Restart Home Assistant** again
7. **Re-add the integration** via Settings → Add Integration

📖 **Full migration guide:** [MIGRATION.md](https://github.com/explosivo22/rinnaicontrolr-ha/blob/2.0.0-beta/MIGRATION.md)

> **Note:** Your entity IDs will be preserved since the domain (`rinnai`) has not changed.

{% else %}

## ⚠️ Upgrading to v2.0.0 - Migration Required

If you are upgrading from v1.x.x to v2.0.0, you **must** follow the migration guide due to a directory rename.

📖 **Full migration guide:** [MIGRATION.md](https://github.com/explosivo22/rinnaicontrolr-ha/blob/master/MIGRATION.md)

**Quick Steps:**
1. Remove the integration from Settings → Devices & Services
2. Remove via HACS
3. Delete `custom_components/rinnaicontrolr-ha/` manually
4. Restart Home Assistant
5. Install v2.0.0 via HACS
6. Restart and re-add the integration

Go to [Github](https://github.com/explosivo22/rinnaicontrolr-ha) for full documentation.

{% endif %}