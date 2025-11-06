import sys
import types
import pathlib
import importlib.util
import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er

DOMAIN = "rinnai"


class _Unauthenticated(Exception):
    pass


class _RequestError(Exception):
    pass


class _FakeUser:
    async def get_info(self):
        return {
            "email": "test@example.com",
            "devices": {"items": [{"id": "device-1"}]},
        }


class _FakeDevice:
    async def get_info(self, device_id: str):
        return {
            "data": {
                "getDevice": {
                    "id": device_id,
                    "device_name": "Rinnai",
                    "model": "X",
                    "firmware": "1.0",
                    "shadow": {
                        "set_domestic_temperature": 120,
                        "set_operation_enabled": True,
                        "recirculation_enabled": False,
                        "schedule_holiday": False,
                    },
                    "info": {
                        "domestic_temperature": 118,
                        "m02_outlet_temperature": 118,
                        "m08_inlet_temperature": 70,
                        "m01_water_flow_rate_raw": 5,
                        "m04_combustion_cycles": 10,
                        "operation_hours": 100,
                        "m19_pump_hours": 30,
                        "m09_fan_current": 3,
                        "m05_fan_frequency": 60,
                        "serial_id": "SN-123",
                    },
                    "activity": {"eventType": "idle"},
                    "thing_name": "thing-1",
                    "user_uuid": "user-1",
                }
            }
        }


class _FakeAPI:
    def __init__(self):
        self.user = _FakeUser()
        self.device = _FakeDevice()
        self.access_token = "access"
        self.refresh_token = "refresh"

    async def async_renew_access_token(self, email: str, access: str, refresh: str):
        return None

    async def async_login(self, email: str, password: str):
        self.access_token = "new_access"
        self.refresh_token = "new_refresh"
        return None


# ----- Helpers to expose the integration package from the repo path -----

def _ensure_package_modules(repo_root: pathlib.Path):
    cc_name = "custom_components"
    pkg_name = "custom_components.rinnai"
    cc = sys.modules.get(cc_name) or types.ModuleType(cc_name)
    cc.__path__ = [str(repo_root / "custom_components")]
    sys.modules[cc_name] = cc

    pkg = sys.modules.get(pkg_name) or types.ModuleType(pkg_name)
    pkg.__path__ = [str(repo_root / "custom_components" / "rinnaicontrolr-ha")]
    sys.modules[pkg_name] = pkg


def _load(module_name: str, file_path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _preload_integration():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    _ensure_package_modules(repo_root)
    base = repo_root / "custom_components" / "rinnaicontrolr-ha"
    _load("custom_components.rinnai.const", base / "const.py")
    _load("custom_components.rinnai.entity", base / "entity.py")
    _load("custom_components.rinnai.device", base / "device.py")
    _load("custom_components.rinnai.binary_sensor", base / "binary_sensor.py")
    _load("custom_components.rinnai.sensor", base / "sensor.py")
    _load("custom_components.rinnai.water_heater", base / "water_heater.py")
    return _load("custom_components.rinnai", base / "__init__.py")


def _install_fake_aiorinnai(monkeypatch):
    mod_aiorinnai = types.ModuleType("aiorinnai")
    mod_ai = types.ModuleType("aiorinnai.api")
    mod_err = types.ModuleType("aiorinnai.errors")

    mod_aiorinnai.API = _FakeAPI  # type: ignore[attr-defined]
    mod_ai.API = _FakeAPI  # type: ignore[attr-defined]
    mod_ai.Unauthenticated = _Unauthenticated  # type: ignore[attr-defined]
    mod_err.RequestError = _RequestError  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "aiorinnai", mod_aiorinnai)
    monkeypatch.setitem(sys.modules, "aiorinnai.api", mod_ai)
    monkeypatch.setitem(sys.modules, "aiorinnai.errors", mod_err)


@pytest.mark.asyncio
async def test_end_to_end_config_entry_sets_up_platforms(hass, monkeypatch):
    _install_fake_aiorinnai(monkeypatch)
    mod = _preload_integration()

    # Speed up coordinator and avoid throttled maintenance side-effects
    async def _fake_refresh(self):
        # Simulate that _device_information is already fetched
        self._device_information = await self.api_client.device.get_info(self.id)
        return None

    monkeypatch.setattr(mod.RinnaiDeviceDataUpdateCoordinator, "async_refresh", _fake_refresh)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        version=2,
    )
    entry.add_to_hass(hass)

    # Act: set up entry end-to-end
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Assert integration data
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
    assert "devices" in hass.data[DOMAIN][entry.entry_id]
    assert len(hass.data[DOMAIN][entry.entry_id]["devices"]) == 1

    # Assert platform entities were created by checking entity registry
    registry = er.async_get(hass)
    created = [e for e in registry.entities.values() if e.config_entry_id == entry.entry_id]
    # Expect at least water_heater plus several sensors/binary_sensors
    assert any(e.domain == "water_heater" for e in created)
    assert any(e.domain == "sensor" for e in created)
    assert any(e.domain == "binary_sensor" for e in created)
