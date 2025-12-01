## 🎯 Summary

This is a **major release** (v2.0.0) that introduces significant new features, architectural improvements, and a **breaking change** requiring manual migration steps.

> ⚠️ **BREAKING CHANGE**: The integration directory has been renamed from `custom_components/rinnaicontrolr-ha/` to `custom_components/rinnai/` to align with Home Assistant best practices. **HACS cannot handle this rename automatically.** See [Migration Required](#-migration-required) section below.

---

## 🔥 Breaking Changes

### Directory Rename (CRITICAL)

| Before (v1.x.x) | After (v2.0.0) |
|-----------------|----------------|
| `custom_components/rinnaicontrolr-ha/` | `custom_components/rinnai/` |

**Why this change?**
- Home Assistant best practices require the folder name to match the integration domain
- The integration domain has always been `rinnai`, but the folder was incorrectly named `rinnaicontrolr-ha`
- This alignment is required for future Home Assistant core submission

**Impact:**
- ✅ Entity IDs are **preserved** (they use the domain `rinnai.`, not the folder name)
- ✅ Configuration data is **preserved** (stored by domain, not folder)
- ❌ HACS **cannot** automatically handle folder renames
- ❌ Users **must** perform manual cleanup (see migration steps)

---

## 📦 Migration Required

### For HACS Users (Recommended Path)

**Clean Install Approach:**

1. **Remove the integration** from Settings → Devices & Services → Rinnai → Delete
2. **Remove via HACS** → Integrations → Rinnai Control-R → Remove
3. **Manually delete** the old folder:
   ```bash
   rm -rf /config/custom_components/rinnaicontrolr-ha
   ```
4. **Restart Home Assistant**
5. **Install v2.0.0** via HACS
6. **Restart Home Assistant** again
7. **Re-add the integration** via Settings → Add Integration

### For Manual Installation Users

Follow the same steps, but copy the new `custom_components/rinnai/` folder instead of using HACS.

### 📖 Full Migration Guide

A comprehensive migration guide is available at **[MIGRATION.md](MIGRATION.md)** covering:
- Clean install vs in-place migration options
- HACS-specific troubleshooting
- Handling duplicate entries
- Rollback instructions

---

## ✨ New Features

### Connection Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Cloud** | Uses Rinnai Control-R cloud API | Default, works from anywhere |
| **Local** | Direct TCP connection (port 9798) | Fastest, no cloud dependency |
| **Hybrid** | Local primary with cloud fallback | Best of both worlds |

### New Entities

#### Sensors
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

#### Binary Sensors
| Sensor | Description |
|--------|-------------|
| Heating | On when water heater is actively heating |
| Recirculation | On when recirculation pump is running |

#### Switches
| Switch | Description |
|--------|-------------|
| Recirculation | Toggle to start/stop recirculation with configurable duration |

### Additional Features

- 🌐 **Multi-language Support** - 14 languages (de, en, es, fr, it, ja, ko, nl, pl, pt, pt-BR, ru, sv, zh-Hans, zh-Hant)
- 🔄 **Proactive Token Refresh** - Credentials refresh before expiration, not after
- 🔍 **Dynamic Device Discovery** - New devices discovered without reload
- 🩺 **Diagnostics Support** - Integration diagnostics for troubleshooting
- ⚙️ **Configurable Maintenance Intervals** - Enable detailed sensor polling
- ♻️ **Reconfiguration Flow** - Change connection mode without removing integration

---

## 🏗️ Architecture Changes

### Code Quality Improvements

- **Full Type Annotations** - `py.typed` marker, strict typing throughout
- **Home Assistant Quality Scale** - Platinum tier compliance
- **Runtime Data Pattern** - Uses `ConfigEntry.runtime_data` dataclass
- **Shared Entity Base Class** - `RinnaiEntity` in `entity.py`
- **Proper Error Handling** - `ServiceValidationError`, `HomeAssistantError`
- **Async Dependencies** - Uses `aiorinnai` async library
- **Injected Web Session** - Proper `async_get_clientsession(hass)` usage

### File Structure

```
custom_components/rinnai/
├── __init__.py           # Integration setup and coordinator
├── binary_sensor.py      # Heating and recirculation status
├── config_flow.py        # Cloud/Local/Hybrid config flows
├── const.py              # Constants and configuration
├── device.py             # RinnaiDeviceCoordinator
├── diagnostics.py        # HA diagnostics support
├── entity.py             # Shared RinnaiEntity base class
├── local.py              # Local TCP connection client
├── manifest.json         # Integration manifest
├── quality_scale.yaml    # HA Quality Scale tracking
├── sensor.py             # Temperature, flow, and diagnostic sensors
├── services.yaml         # Service definitions
├── strings.json          # UI strings and translations
├── switch.py             # Recirculation switch
├── water_heater.py       # Main water heater entity
└── translations/         # 14 language translation files
```

---

## 🧪 Testing

### Test Coverage

- ✅ Config flow tests (all paths)
- ✅ Device coordinator tests
- ✅ Entity platform tests
- ✅ End-to-end config entry tests
- ✅ Setup entry tests

### CI/CD

- GitHub Actions workflow updated for HA testing
- Lint and type checking job added
- Uses `uv` for faster dependency installation

---

## 📊 Changes Summary

```
54 files changed, 9,740 insertions(+), 1,410 deletions(-)
```

### Key Changes by Area

| Area | Files Changed | Description |
|------|--------------|-------------|
| Integration Core | 11 new files | Complete rewrite with new architecture |
| Translations | 15 files | Multi-language support |
| Tests | 6 files | Comprehensive test coverage |
| Documentation | 3 files | README, MIGRATION.md, info.md |
| CI/CD | 2 files | Workflow improvements |

---

## 📋 Checklist

### Code Quality
- [x] Full type annotations (`py.typed`)
- [x] Home Assistant Quality Scale compliance
- [x] Proper error handling and translations
- [x] Entity naming follows HA conventions

### Testing
- [x] Config flow tests pass
- [x] Entity platform tests pass
- [x] Coordinator tests pass
- [x] E2E integration tests pass

### Documentation
- [x] README.md updated with new features
- [x] MIGRATION.md created with detailed steps
- [x] info.md updated for HACS
- [x] All new entities documented

### HACS Compatibility
- [x] `hacs.json` configuration correct
- [x] `info.md` includes migration warning
- [x] Version correctly set in `manifest.json`

---

## 🔗 Related Links

- **Migration Guide**: [MIGRATION.md](MIGRATION.md)
- **Upstream Library**: [aiorinnai](https://pypi.org/project/aiorinnai/)
- **Home Assistant Quality Scale**: [Documentation](https://developers.home-assistant.io/docs/core/integration-quality-scale)

---

## 🙏 Acknowledgments

Special thanks to contributors:
- @joyfulhouse for hybrid mode and local TCP control
- Community testers on the beta branch

---

## ⚠️ Important Notes for Reviewers

1. **This is a breaking change** - Users MUST follow migration steps
2. **HACS limitation** - HACS cannot auto-rename directories; users must manually delete old folder
3. **Entity IDs preserved** - Despite folder rename, entity IDs remain stable (based on `rinnai` domain)
4. **Backward compatibility** - Migration code handles both v1.5.x (cloud) and v2.1.x (local-only) configs
