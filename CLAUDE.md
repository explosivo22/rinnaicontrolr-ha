# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration for Rinnai Control-R water heaters. It communicates with Rinnai's cloud API via the `aiorinnai` library to provide water heater control, temperature monitoring, and operational sensors.

**Domain**: `rinnai`
**IoT Class**: Cloud Polling (60-second update interval)
**Key Dependency**: `aiorinnai==0.4.0a2`

## Development Commands

```bash
# Run all tests with coverage
pytest tests/ -v --tb=short --cov=custom_components.rinnai

# Run specific test file
pytest tests/test_setup_entry.py -v

# Install test dependencies
pip install pytest pytest-asyncio pytest-homeassistant-custom-component pytest-cov

# Install runtime dependency
pip install aiorinnai==0.4.0a2
```

The CI pipeline (`.github/workflows/test-with-homeassistant.yaml`) runs hassfest validation, HACS validation, and tests against Python 3.12 and 3.13.

## Architecture

### Component Location
The integration lives in `custom_components/rinnaicontrolr-ha/` but registers with Home Assistant under the domain `rinnai` (defined in manifest.json).

### Core Pattern: Coordinator-Centric Design
- `RinnaiDeviceDataUpdateCoordinator` (in `device.py`) is the central data manager
- One coordinator instance per Rinnai device (supports multiple devices per account)
- All entities subscribe to the coordinator for updates
- Coordinator handles all API communication, including control actions

### Entity Hierarchy
```
RinnaiEntity (entity.py) - Base class providing device info and coordinator binding
├── RinnaiWaterHeater (water_heater.py) - Main control entity
├── Rinnai*Sensor (sensor.py) - 9 sensor types (temps, flow, cycles, hours)
└── Rinnai*BinarySensor (binary_sensor.py) - 2 binary sensors (heating, recirculating)
```

### Config Flow
- Version 2 config with token-based auth (migrated from v1 password storage)
- Supports reauth flow when tokens expire
- Options flow for maintenance interval toggle
- Config stored via Home Assistant's config entry system

### Key Files
- `__init__.py`: Entry point, handles setup/unload, platform forwarding, v1→v2 migration
- `config_flow.py`: Multi-step config UI with reauth support
- `device.py`: DataUpdateCoordinator with all device properties and control methods
- `entity.py`: Base entity class with device registration
- `services.yaml`: Custom services (start_recirculation, stop_recirculation)

### Error Handling
- `ConfigEntryAuthFailed`: Triggers reauth flow
- `ConfigEntryNotReady`: Network issues, causes retry
- `UpdateFailed`: Coordinator fetch failures

## Testing

Tests are in `tests/` directory:
- `test_platform_imports.py`: Validates platform module imports
- `test_setup_entry.py`: Unit tests with mocked aiorinnai (uses `_FakeAPI`, `_FakeDevice` fixtures)
- `test_e2e_config_entry.py`: Integration tests with full HA initialization

Tests use `pytest-homeassistant-custom-component` for HA test fixtures.

## Known Issues

The Rinnai app firmware has a bug where recirculation started from the app is limited to 5 minutes. This integration works around it by allowing recirculation durations from 5-300 minutes via custom services.

## Home Assistant Quality Scale Requirements

Target: **Silver** tier (with Gold aspirations)

### Bronze Requirements (Baseline)
- [x] `config_flow`: UI-based setup via config flow
- [x] `test_before_setup`: Validate connection before completing setup
- [x] `unique_config_entry`: Prevent duplicate config entries
- [x] `has_entity_name`: Entities use proper naming conventions
- [x] `entity_unique_id`: All entities have unique IDs
- [x] `docs_high_level_description`: Documentation describes what the integration does
- [x] `docs_installation_instructions`: Setup instructions in README
- [x] `appropriate_polling`: Uses DataUpdateCoordinator with 60s interval
- [x] `brands`: Integration has proper branding

### Silver Requirements (Reliability)
- [x] `config_entry_unloading`: Properly unloads config entries
- [x] `reauthentication_flow`: Handles expired credentials with reauth flow
- [x] `log_when_unavailable`: Logs errors when device/service unavailable
- [ ] `parallel_updates`: Limit concurrent updates (set `PARALLEL_UPDATES`)
- [ ] `stale_devices`: Remove stale devices when they disappear
- [ ] `entity_unavailable`: Mark entities unavailable on connection errors
- [x] `action_exceptions`: Raise proper exceptions for failed actions

### Gold Requirements (Premium UX)
- [ ] `discovery`: Auto-discovery via DHCP/SSDP/Zeroconf
- [x] `reconfiguration_flow`: Options flow for reconfiguration
- [ ] `dynamic_devices`: Support adding/removing devices without reload
- [x] `integration_owner`: Has active code owner (@explosivo22)
- [ ] `docs_use_cases`: Documentation includes use case examples
- [ ] `docs_supported_devices`: Lists supported device models
- [ ] `docs_troubleshooting`: Troubleshooting section in docs

### Platinum Requirements (Excellence)
- [ ] `async_dependency`: All external I/O is async
- [ ] `inject_websession`: Use HA's aiohttp session
- [ ] `strict_typing`: Full type annotations with strict mypy
- [ ] `runtime_data`: Use `entry.runtime_data` instead of `hass.data`

### Quality Scale Tracking
Track progress in `quality_scale.yaml` at integration root:
```yaml
rules:
  config_flow: done
  reauthentication_flow: done
  entity_unavailable:
    status: todo
    comment: Need to mark entities unavailable on connection errors
```

### References
- [HA Quality Scale Docs](https://developers.home-assistant.io/docs/core/integration-quality-scale)
- [HA Integration Checklist](https://developers.home-assistant.io/docs/development_checklist)
