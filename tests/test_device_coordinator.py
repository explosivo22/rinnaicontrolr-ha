"""Tests for Rinnai device coordinator."""
import sys
import types
import pathlib
import importlib.util
import time

import pytest
import jwt
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

DOMAIN = "rinnai"


class _Unauthenticated(Exception):
    """Fake Unauthenticated exception."""
    pass


class _RequestError(Exception):
    """Fake RequestError exception."""
    pass


class _FakeUser:
    """Fake user API."""
    async def get_info(self):
        return {
            "email": "test@example.com",
            "devices": {"items": [{"id": "device-1"}]},
        }


class _FakeDevice:
    """Fake device API."""

    def __init__(self):
        self._should_fail = False
        self._fail_with_unauth = False
        self._call_count = 0

    async def get_info(self, device_id: str):
        self._call_count += 1
        if self._fail_with_unauth:
            raise _Unauthenticated("Token expired")
        if self._should_fail:
            raise _RequestError("Connection failed")
        return {
            "data": {
                "getDevice": {
                    "device_name": "Rinnai Water Heater",
                    "model": "RUR199",
                    "firmware": "1.0",
                    "thing_name": "thing123",
                    "user_uuid": "user123",
                    "shadow": {
                        "set_domestic_temperature": 120,
                        "set_operation_enabled": True,
                        "recirculation_enabled": False,
                        "schedule_holiday": False,
                    },
                    "info": {
                        "domestic_temperature": 118,
                        "serial_id": "SERIAL123",
                        "domestic_combustion": False,
                        "m02_outlet_temperature": 115,
                        "m08_inlet_temperature": 55,
                        "m01_water_flow_rate_raw": 25,
                        "m04_combustion_cycles": 1500,
                        "operation_hours": 2500,
                        "m19_pump_hours": 500,
                        "m09_fan_current": 150,
                        "m05_fan_frequency": 60,
                        "m20_pump_cycles": 3000,
                    },
                    "activity": {
                        "eventType": "idle",
                    },
                }
            }
        }

    async def set_temperature(self, device, temperature):
        if self._fail_with_unauth:
            raise _Unauthenticated("Token expired")
        if self._should_fail:
            raise _RequestError("Connection failed")

    async def start_recirculation(self, device, duration):
        if self._fail_with_unauth:
            raise _Unauthenticated("Token expired")
        if self._should_fail:
            raise _RequestError("Connection failed")

    async def stop_recirculation(self, device):
        if self._fail_with_unauth:
            raise _Unauthenticated("Token expired")
        if self._should_fail:
            raise _RequestError("Connection failed")

    async def enable_vacation_mode(self, device):
        pass

    async def disable_vacation_mode(self, device):
        pass

    async def turn_on(self, device):
        pass

    async def turn_off(self, device):
        pass

    async def do_maintenance_retrieval(self, device):
        pass


class _FakeAPI:
    """Fake aiorinnai API."""
    def __init__(self):
        self.user = _FakeUser()
        self.device = _FakeDevice()
        self.access_token = self._create_valid_token()
        self.refresh_token = "test_refresh_token"
        self._renew_called = False

    def _create_valid_token(self):
        """Create a JWT token that expires in 1 hour."""
        exp = int(time.time()) + 3600
        return jwt.encode({"exp": exp}, "secret", algorithm="HS256")

    def _create_expired_token(self):
        """Create a JWT token that expired."""
        exp = int(time.time()) - 600
        return jwt.encode({"exp": exp}, "secret", algorithm="HS256")

    def _create_expiring_soon_token(self):
        """Create a JWT token that expires in 2 minutes (within buffer)."""
        exp = int(time.time()) + 120  # 2 minutes, less than 5 min buffer
        return jwt.encode({"exp": exp}, "secret", algorithm="HS256")

    async def async_renew_access_token(self, email, access, refresh):
        self._renew_called = True
        self.access_token = self._create_valid_token()
        self.refresh_token = "renewed_refresh_token"


def _ensure_package_modules(repo_root: pathlib.Path):
    """Ensure custom_components packages exist."""
    cc_name = "custom_components"
    pkg_name = "custom_components.rinnai"
    cc = sys.modules.get(cc_name) or types.ModuleType(cc_name)
    cc.__path__ = [str(repo_root / "custom_components")]
    sys.modules[cc_name] = cc

    pkg = sys.modules.get(pkg_name) or types.ModuleType(pkg_name)
    pkg.__path__ = [str(repo_root / "custom_components" / "rinnaicontrolr-ha")]
    sys.modules[pkg_name] = pkg


def _load_module(module_name: str, file_path: pathlib.Path):
    """Load module from file path."""
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _install_fake_aiorinnai(monkeypatch):
    """Install fake aiorinnai modules."""
    mod_aiorinnai = types.ModuleType("aiorinnai")
    mod_api = types.ModuleType("aiorinnai.api")
    mod_err = types.ModuleType("aiorinnai.errors")

    mod_aiorinnai.API = _FakeAPI
    mod_api.API = _FakeAPI
    mod_api.Unauthenticated = _Unauthenticated
    mod_err.RequestError = _RequestError

    monkeypatch.setitem(sys.modules, "aiorinnai", mod_aiorinnai)
    monkeypatch.setitem(sys.modules, "aiorinnai.api", mod_api)
    monkeypatch.setitem(sys.modules, "aiorinnai.errors", mod_err)


def _load_device_module(monkeypatch):
    """Load device module."""
    _install_fake_aiorinnai(monkeypatch)
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    _ensure_package_modules(repo_root)
    base_dir = repo_root / "custom_components" / "rinnaicontrolr-ha"

    _load_module("custom_components.rinnai.const", base_dir / "const.py")
    return _load_module("custom_components.rinnai.device", base_dir / "device.py")


# Token expiration tests

def test_is_token_expired_with_valid_token(monkeypatch):
    """Test token expiration check with valid token."""
    device_mod = _load_device_module(monkeypatch)

    # Token expires in 1 hour
    exp = int(time.time()) + 3600
    token = jwt.encode({"exp": exp}, "secret", algorithm="HS256")

    assert device_mod._is_token_expired(token) is False


def test_is_token_expired_with_expired_token(monkeypatch):
    """Test token expiration check with expired token."""
    device_mod = _load_device_module(monkeypatch)

    # Token expired 10 minutes ago
    exp = int(time.time()) - 600
    token = jwt.encode({"exp": exp}, "secret", algorithm="HS256")

    assert device_mod._is_token_expired(token) is True


def test_is_token_expired_with_expiring_soon_token(monkeypatch):
    """Test token expiration check with token expiring within buffer."""
    device_mod = _load_device_module(monkeypatch)

    # Token expires in 2 minutes (less than 5 min buffer)
    exp = int(time.time()) + 120
    token = jwt.encode({"exp": exp}, "secret", algorithm="HS256")

    assert device_mod._is_token_expired(token) is True


def test_is_token_expired_with_none(monkeypatch):
    """Test token expiration check with None token."""
    device_mod = _load_device_module(monkeypatch)

    assert device_mod._is_token_expired(None) is True


def test_is_token_expired_with_invalid_token(monkeypatch):
    """Test token expiration check with invalid token."""
    device_mod = _load_device_module(monkeypatch)

    assert device_mod._is_token_expired("invalid_token") is True


# Coordinator tests

@pytest.mark.asyncio
async def test_coordinator_properties(hass, monkeypatch):
    """Test coordinator device properties."""
    device_mod = _load_device_module(monkeypatch)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={"maint_interval_enabled": False},
        version=2,
    )
    entry.add_to_hass(hass)

    api = _FakeAPI()
    coordinator = device_mod.RinnaiDeviceDataUpdateCoordinator(
        hass, api, "device-1", dict(entry.options), entry
    )

    # Fetch data
    await coordinator._async_update_data()

    # Test properties
    assert coordinator.id == "device-1"
    assert coordinator.device_name == "Rinnai Water Heater"
    assert coordinator.manufacturer == "Rinnai"
    assert coordinator.model == "RUR199"
    assert coordinator.firmware_version == "1.0"
    assert coordinator.serial_number == "SERIAL123"
    assert coordinator.thing_name == "thing123"
    assert coordinator.user_uuid == "user123"


@pytest.mark.asyncio
async def test_coordinator_temperature_properties(hass, monkeypatch):
    """Test coordinator temperature properties."""
    device_mod = _load_device_module(monkeypatch)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={"maint_interval_enabled": False},
        version=2,
    )
    entry.add_to_hass(hass)

    api = _FakeAPI()
    coordinator = device_mod.RinnaiDeviceDataUpdateCoordinator(
        hass, api, "device-1", dict(entry.options), entry
    )

    await coordinator._async_update_data()

    assert coordinator.current_temperature == 118.0
    assert coordinator.target_temperature == 120.0
    assert coordinator.outlet_temperature == 115.0
    assert coordinator.inlet_temperature == 55.0


@pytest.mark.asyncio
async def test_coordinator_sensor_properties(hass, monkeypatch):
    """Test coordinator sensor properties."""
    device_mod = _load_device_module(monkeypatch)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={"maint_interval_enabled": False},
        version=2,
    )
    entry.add_to_hass(hass)

    api = _FakeAPI()
    coordinator = device_mod.RinnaiDeviceDataUpdateCoordinator(
        hass, api, "device-1", dict(entry.options), entry
    )

    await coordinator._async_update_data()

    assert coordinator.water_flow_rate == 25.0
    assert coordinator.combustion_cycles == 1500.0
    assert coordinator.operation_hours == 2500.0
    assert coordinator.pump_hours == 500.0
    assert coordinator.pump_cycles == 3000.0
    assert coordinator.fan_current == 150.0
    assert coordinator.fan_frequency == 60.0


@pytest.mark.asyncio
async def test_coordinator_boolean_properties(hass, monkeypatch):
    """Test coordinator boolean properties."""
    device_mod = _load_device_module(monkeypatch)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={"maint_interval_enabled": False},
        version=2,
    )
    entry.add_to_hass(hass)

    api = _FakeAPI()
    coordinator = device_mod.RinnaiDeviceDataUpdateCoordinator(
        hass, api, "device-1", dict(entry.options), entry
    )

    await coordinator._async_update_data()

    assert coordinator.is_on is True
    assert coordinator.is_heating is False
    assert coordinator.is_recirculating is False
    assert coordinator.vacation_mode_on is False
    assert coordinator.last_known_state == "idle"


@pytest.mark.asyncio
async def test_coordinator_available_property(hass, monkeypatch):
    """Test coordinator available property."""
    device_mod = _load_device_module(monkeypatch)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={"maint_interval_enabled": False},
        version=2,
    )
    entry.add_to_hass(hass)

    api = _FakeAPI()
    coordinator = device_mod.RinnaiDeviceDataUpdateCoordinator(
        hass, api, "device-1", dict(entry.options), entry
    )

    # Initially should be available (no errors)
    assert coordinator._consecutive_errors == 0


@pytest.mark.asyncio
async def test_coordinator_token_refresh_on_expiring_token(hass, monkeypatch):
    """Test that coordinator refreshes token when expiring soon."""
    device_mod = _load_device_module(monkeypatch)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={"maint_interval_enabled": False},
        version=2,
    )
    entry.add_to_hass(hass)

    api = _FakeAPI()
    # Set token to expire soon
    api.access_token = api._create_expiring_soon_token()

    coordinator = device_mod.RinnaiDeviceDataUpdateCoordinator(
        hass, api, "device-1", dict(entry.options), entry
    )

    await coordinator._async_update_data()

    # Token should have been renewed
    assert api._renew_called is True


@pytest.mark.asyncio
async def test_coordinator_auth_failure_raises_config_entry_auth_failed(hass, monkeypatch):
    """Test that auth failures raise ConfigEntryAuthFailed."""
    device_mod = _load_device_module(monkeypatch)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={"maint_interval_enabled": False},
        version=2,
    )
    entry.add_to_hass(hass)

    api = _FakeAPI()
    api.device._fail_with_unauth = True

    coordinator = device_mod.RinnaiDeviceDataUpdateCoordinator(
        hass, api, "device-1", dict(entry.options), entry
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_request_error_raises_update_failed(hass, monkeypatch):
    """Test that request errors raise UpdateFailed after retries."""
    device_mod = _load_device_module(monkeypatch)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={"maint_interval_enabled": False},
        version=2,
    )
    entry.add_to_hass(hass)

    api = _FakeAPI()
    api.device._should_fail = True

    coordinator = device_mod.RinnaiDeviceDataUpdateCoordinator(
        hass, api, "device-1", dict(entry.options), entry
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    # Should have tried MAX_RETRY_ATTEMPTS times
    assert api.device._call_count == 3  # MAX_RETRY_ATTEMPTS


@pytest.mark.asyncio
async def test_coordinator_properties_return_none_without_data(hass, monkeypatch):
    """Test that properties return None when no data loaded."""
    device_mod = _load_device_module(monkeypatch)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={"maint_interval_enabled": False},
        version=2,
    )
    entry.add_to_hass(hass)

    api = _FakeAPI()
    coordinator = device_mod.RinnaiDeviceDataUpdateCoordinator(
        hass, api, "device-1", dict(entry.options), entry
    )

    # Don't call _async_update_data, so no device info loaded
    assert coordinator.device_name is None
    assert coordinator.model is None
    assert coordinator.current_temperature is None
    assert coordinator.is_on is None


# Helper function tests

def test_convert_to_bool_with_string_true(monkeypatch):
    """Test _convert_to_bool with string 'true'."""
    device_mod = _load_device_module(monkeypatch)
    assert device_mod._convert_to_bool("true") is True
    assert device_mod._convert_to_bool("True") is True
    assert device_mod._convert_to_bool("TRUE") is True


def test_convert_to_bool_with_string_false(monkeypatch):
    """Test _convert_to_bool with string 'false'."""
    device_mod = _load_device_module(monkeypatch)
    assert device_mod._convert_to_bool("false") is False
    assert device_mod._convert_to_bool("False") is False


def test_convert_to_bool_with_bool(monkeypatch):
    """Test _convert_to_bool with actual booleans."""
    device_mod = _load_device_module(monkeypatch)
    assert device_mod._convert_to_bool(True) is True
    assert device_mod._convert_to_bool(False) is False


def test_convert_to_bool_with_other_values(monkeypatch):
    """Test _convert_to_bool with other values."""
    device_mod = _load_device_module(monkeypatch)
    assert device_mod._convert_to_bool(1) is True
    assert device_mod._convert_to_bool(0) is False
    assert device_mod._convert_to_bool("") is False
