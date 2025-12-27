import sys
import types
import pathlib
import importlib.util
import shutil
import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er

DOMAIN = "rinnai"


class _Unauthenticated(Exception):
    pass


class _RequestError(Exception):
    pass


class _UserNotFound(Exception):
    pass


class _UserNotConfirmed(Exception):
    pass


class _PasswordChangeRequired(Exception):
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
    """Fake aiorinnai API matching real aiorinnai.API signature."""

    def __init__(
        self,
        session=None,
        timeout: float = 30.0,
        retry_count: int = 3,
        retry_delay: float = 1.0,
        retry_multiplier: float = 2.0,
        executor_timeout: float = 30.0,
    ):
        # Match real API attributes
        self.session = session
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.retry_multiplier = retry_multiplier
        self.executor_timeout = executor_timeout
        self.username = None
        self.is_connected = False

        # Private token attributes (real API only has private ones)
        self._access_token = None
        self._refresh_token = None
        self._id_token = None

        # Sub-objects (populated immediately for e2e tests)
        self.user = _FakeUser()
        self.device = _FakeDevice()

    @property
    def access_token(self):
        """Public accessor for access token (for config_flow.py compatibility)."""
        return self._access_token

    @property
    def refresh_token(self):
        """Public accessor for refresh token (for config_flow.py compatibility)."""
        return self._refresh_token

    async def async_renew_access_token(
        self,
        email: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ):
        """Simulate token renewal."""
        self.username = email
        self.is_connected = True
        self._access_token = "renewed_access_token"
        self._refresh_token = "renewed_refresh_token"
        self._id_token = "renewed_id_token"
        return None

    async def async_login(self, email: str, password: str):
        """Simulate login."""
        self.username = email
        self.is_connected = True
        self._access_token = "new_access"
        self._refresh_token = "new_refresh"
        self._id_token = "new_id_token"
        return None

    async def async_check_token(self):
        """Check if token is valid."""
        pass

    def close(self):
        """Close the session."""
        pass


# ----- Helpers to expose the integration package from the repo path -----


def _ensure_package_modules(repo_root: pathlib.Path):
    cc_name = "custom_components"
    pkg_name = "custom_components.rinnai"
    cc = sys.modules.get(cc_name) or types.ModuleType(cc_name)
    cc.__path__ = [str(repo_root / "custom_components")]
    sys.modules[cc_name] = cc

    pkg = sys.modules.get(pkg_name) or types.ModuleType(pkg_name)
    pkg.__path__ = [str(repo_root / "custom_components" / "rinnai")]
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
    base = repo_root / "custom_components" / "rinnai"
    _load("custom_components.rinnai.const", base / "const.py")
    _load("custom_components.rinnai.device", base / "device.py")
    _load("custom_components.rinnai.entity", base / "entity.py")
    # Load __init__ first so RinnaiConfigEntry is available for platform imports
    init_mod = _load("custom_components.rinnai", base / "__init__.py")
    _load("custom_components.rinnai.binary_sensor", base / "binary_sensor.py")
    _load("custom_components.rinnai.sensor", base / "sensor.py")
    _load("custom_components.rinnai.water_heater", base / "water_heater.py")
    return init_mod


def _install_fake_aiorinnai(monkeypatch):
    mod_aiorinnai = types.ModuleType("aiorinnai")
    mod_ai = types.ModuleType("aiorinnai.api")
    mod_err = types.ModuleType("aiorinnai.errors")

    mod_aiorinnai.API = _FakeAPI  # type: ignore[attr-defined]
    mod_ai.API = _FakeAPI  # type: ignore[attr-defined]
    mod_ai.Unauthenticated = _Unauthenticated  # type: ignore[attr-defined]
    mod_err.RequestError = _RequestError  # type: ignore[attr-defined]
    mod_err.UserNotFound = _UserNotFound  # type: ignore[attr-defined]
    mod_err.UserNotConfirmed = _UserNotConfirmed  # type: ignore[attr-defined]
    mod_err.PasswordChangeRequired = _PasswordChangeRequired  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "aiorinnai", mod_aiorinnai)
    monkeypatch.setitem(sys.modules, "aiorinnai.api", mod_ai)
    monkeypatch.setitem(sys.modules, "aiorinnai.errors", mod_err)


def _materialize_custom_component(hass) -> pathlib.Path:
    """Copy the repo integration into the HA test config/custom_components/rinnai path.

    Home Assistant's integration loader expects custom components on disk with a
    manifest.json under config/custom_components/<domain>. This ensures the loader
    can discover the integration and read the manifest.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    src = repo_root / "custom_components" / "rinnai"
    dest = pathlib.Path(hass.config.path("custom_components")) / "rinnai"
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Copy the tree, overwriting if it exists
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


@pytest.mark.asyncio
async def test_end_to_end_config_entry_sets_up_platforms(
    hass, enable_custom_integrations, monkeypatch
):
    _install_fake_aiorinnai(monkeypatch)
    mod = _preload_integration()

    # Place the integration on disk where HA expects custom components
    _materialize_custom_component(hass)

    # Speed up coordinator and avoid throttled maintenance side-effects
    async def _fake_refresh(self):
        # Simulate that _device_information is already fetched
        self._device_information = await self.api_client.device.get_info(self.id)
        return None

    monkeypatch.setattr(
        mod.RinnaiDeviceDataUpdateCoordinator, "async_refresh", _fake_refresh
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={
            "maint_interval_enabled": False,
        },
        version=2,
    )
    entry.add_to_hass(hass)

    # Act: set up entry end-to-end
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Assert integration data using runtime_data pattern
    assert hasattr(entry, "runtime_data")
    assert entry.runtime_data is not None
    assert len(entry.runtime_data.devices) == 1

    # Assert platform entities were created by checking entity registry
    registry = er.async_get(hass)
    created = [
        e for e in registry.entities.values() if e.config_entry_id == entry.entry_id
    ]
    # Expect at least water_heater plus several sensors/binary_sensors
    assert any(e.domain == "water_heater" for e in created)
    assert any(e.domain == "sensor" for e in created)
    assert any(e.domain == "binary_sensor" for e in created)
