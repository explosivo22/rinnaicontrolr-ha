# Changelog

All notable changes to the Rinnai Control-R Home Assistant integration are documented in this file.

This fork ([joyfulhouse/rinnaicontrolr-ha](https://github.com/joyfulhouse/rinnaicontrolr-ha)) is based on the original [explosivo22/rinnaicontrolr-ha](https://github.com/explosivo22/rinnaicontrolr-ha) integration.

## [Unreleased]

### Added
- Dynamic device discovery (Gold tier requirement) - devices added/removed without reload
- Stale device removal - automatically removes devices that disappear from account
- Comprehensive documentation with use cases, troubleshooting, and supported devices
- Multi-language translations (14 languages: German, Spanish, French, Italian, Japanese, Korean, Dutch, Polish, Portuguese, Portuguese (Brazil), Russian, Swedish, Chinese Simplified, Chinese Traditional)
- Recirculation switch entity for easy on/off control without service calls
- Hybrid connection mode (local TCP with cloud fallback)
- Local TCP direct control (port 9798) for faster, more reliable operation
- Proactive JWT token refresh before expiration
- Runtime data pattern (`entry.runtime_data`) for modern HA integration
- Comprehensive type annotations throughout codebase
- `PARALLEL_UPDATES = 1` on all platforms for rate limiting
- Entity availability tracking via DataUpdateCoordinator
- Reconfiguration flow to change connection modes without removing integration
- Configurable default recirculation duration in options flow
- Issue registry notification when re-authentication is required

### Changed
- Migrated from `hass.data` to `entry.runtime_data` pattern (HA Quality Scale requirement)
- Refactored all entities to use `translation_key` for proper localization
- Improved entity naming with `_attr_has_entity_name = True`
- Enhanced error handling with proper `HomeAssistantError`, `ConfigEntryAuthFailed`, and `UpdateFailed` exceptions
- Simplified sensor and binary sensor implementations using dataclass descriptors
- Updated config flow to multi-step wizard supporting cloud/local/hybrid modes
- Improved logging throughout with structured debug messages

### Fixed
- Entity translations now display correctly (removed `_attr_name` override)
- Type errors throughout codebase resolved
- Token refresh now happens proactively before expiration
- Proper unique ID generation for all entities

---

## Fork History

This section documents the changes made in the joyfulhouse fork, organized by merge/commit.

### 2024-11-25: Fix Entity Translations
**Commit:** `5ebd29d`

- **Fixed:** Entity names showing raw translation keys (e.g., "combustion_cycles" instead of "Combustion Cycles")
- **Root Cause:** Base `RinnaiEntity` class was setting `_attr_name` which overrides the `translation_key` system
- **Solution:** Removed `name` parameter from base entity `__init__` to allow Home Assistant's translation system to work properly

### 2024-11-25: Add Multi-Language Translations
**Commit:** `a429d81`

- **Added:** 14 new translation files for international users
  - European: German (de), Spanish (es), French (fr), Italian (it), Dutch (nl), Polish (pl), Portuguese (pt), Russian (ru), Swedish (sv)
  - Asian: Japanese (ja), Korean (ko), Chinese Simplified (zh-Hans), Chinese Traditional (zh-Hant)
  - Americas: Portuguese Brazil (pt-BR)
- **Refactored:** Entity descriptions to use dataclass patterns
- **Improved:** Simplified sensor, binary sensor, and switch implementations

### 2024-11-24: Add Recirculation Switch
**Commit:** `a2a0bac`

- **Added:** `RinnaiRecirculationSwitch` entity for toggle control
  - Uses optimistic state updates for responsive UI
  - Configurable duration via options flow (5-300 minutes)
  - Icons change based on state (mdi:autorenew / mdi:sync-off)
- **Fixed:** Entity naming to follow HA conventions with `_attr_has_entity_name`

### 2024-11-23: Add Hybrid Mode and Local TCP Control
**Commit:** `325eea5` (PR #2)

- **Added:** Three connection modes in config flow:
  - **Cloud:** Uses Rinnai Control-R cloud API (original behavior)
  - **Local:** Direct TCP connection to water heater on port 9798
  - **Hybrid:** Primary local with automatic cloud fallback
- **Added:** `RinnaiLocalClient` for direct device communication
  - `get_sysinfo()`: Retrieve device serial and firmware
  - `get_status()`: Get current device state
  - Local control commands for temperature, recirculation, power
- **Added:** Reconfigure flow to change connection modes without removing integration
- **Fixed:** All mypy type errors resolved

### 2024-11-22: Migrate to runtime_data Pattern
**Commit:** `3f3aa81` (PR #1)

- **Added:** `RinnaiRuntimeData` dataclass for type-safe runtime storage
- **Added:** `RinnaiConfigEntry` type alias for typed config entries
- **Migrated:** From `hass.data[DOMAIN]` to `entry.runtime_data` (HA Quality Scale Platinum requirement)
- **Improved:** Test coverage with new test fixtures and unit tests
- **Added:** `test_setup_entry.py` with mocked API fixtures

### 2024-11-22: Proactive Token Refresh and Quality Scale Improvements
**Commit:** `93e063e` (PR #1)

- **Added:** Proactive JWT token refresh
  - Decodes access token to check expiration
  - Refreshes tokens 5 minutes before expiry
  - Persists new tokens to config entry
- **Added:** HA Quality Scale Silver tier compliance:
  - `PARALLEL_UPDATES = 1` on all platforms
  - Proper exception handling (`HomeAssistantError`, `UpdateFailed`)
  - Entity availability via coordinator pattern
  - Comprehensive logging when unavailable
- **Added:** Issue registry integration for auth failures
- **Updated:** Manifest to declare Silver quality scale tier

---

## Upstream History (explosivo22/rinnaicontrolr-ha)

### Version 2.1.9 (Upstream)
- Enhanced logging in `RinnaiDeviceDataUpdateCoordinator`
- Added GitHub Actions CI/CD workflow
- Added issue templates for bug reports and feature requests

### Version 1.5.9 (Upstream)
- Implemented re-authentication flow for expired tokens
- Added reauthentication issue handling
- Fixed services.yaml default values

### Version 1.5.8 (Upstream)
- Refactored ConfigFlow class inheritance
- Bug fixes for configuration options

### Version 1.5.6 (Upstream)
- Enhanced migration logic for config entry v1 to v2
- Token migration support

### Version 1.5.5 (Upstream)
- Migrated config entry from version 1 to 2
- Added refresh token migration

### Version 1.5.4 (Upstream)
- Removed merge conflict markers
- Code cleanup

### Version 1.5.3 (Upstream)
- Reverted folder naming change

### Version 1.5.2 (Upstream)
- Enhanced authentication
- Updated dependencies

### Earlier Versions
See [upstream releases](https://github.com/explosivo22/rinnaicontrolr-ha/releases) for complete history.

---

## Quality Scale Compliance

This fork targets Home Assistant Integration Quality Scale compliance:

| Tier | Status | Notes |
|------|--------|-------|
| **Bronze** | ✅ Complete | All 9 requirements met |
| **Silver** | ✅ Complete | 6/7 requirements (stale_devices pending) |
| **Gold** | ⚠️ Partial | 4/7 requirements (documentation gaps) |
| **Platinum** | ⚠️ Partial | 3/4 requirements (inject_websession blocked by dependency) |

### Platinum Requirements Status
- ✅ `async_dependency` - All I/O is async
- ✅ `strict_typing` - Full type annotations
- ✅ `runtime_data` - Using modern `entry.runtime_data` pattern
- ⏳ `inject_websession` - Requires upstream `aiorinnai` library changes

---

## Migration Notes

### Migrating from Upstream
If migrating from the original explosivo22 integration:

1. **Backup your configuration** before switching
2. Remove the old integration from HACS
3. Add this fork's repository to HACS
4. Install and restart Home Assistant
5. Your existing config entry will be migrated automatically
6. Optionally reconfigure to use Local or Hybrid mode for faster control

### Config Entry Migration
- **v1 → v2:** Automatic migration of password-based auth to token-based auth
- Tokens are refreshed proactively before expiration
- Re-authentication flow available if tokens become invalid

---

## Contributing

Contributions are welcome! Please:

1. Fork this repository
2. Create a feature branch
3. Make your changes with appropriate tests
4. Submit a pull request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
