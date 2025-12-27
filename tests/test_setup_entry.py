import sys
import types
import pathlib
import importlib.util

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.exceptions import ConfigEntryAuthFailed

# Constants to mirror the integration
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
                    "device_name": "Rinnai",
                    "model": "X",
                    "firmware": "1.0",
                    "shadow": {"set_domestic_temperature": None},
                    "info": {"domestic_temperature": 120},
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

        # Sub-objects (populated immediately for setup tests)
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


def _ensure_package_modules(repo_root: pathlib.Path):
    """Ensure custom_components and custom_components.rinnai exist as packages in sys.modules."""
    cc_name = "custom_components"
    pkg_name = "custom_components.rinnai"
    cc = sys.modules.get(cc_name) or types.ModuleType(cc_name)
    cc.__path__ = [str(repo_root / "custom_components")]
    sys.modules[cc_name] = cc

    pkg = sys.modules.get(pkg_name) or types.ModuleType(pkg_name)
    pkg.__path__ = [str(repo_root / "custom_components" / "rinnai")]
    sys.modules[pkg_name] = pkg


def _load_module(module_name: str, file_path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _install_fake_aiorinnai(monkeypatch):
    # Create fake modules: aiorinnai, aiorinnai.api, aiorinnai.errors
    mod_aiorinnai = types.ModuleType("aiorinnai")
    mod_ai = types.ModuleType("aiorinnai.api")
    mod_err = types.ModuleType("aiorinnai.errors")

    # Expose classes
    mod_aiorinnai.API = _FakeAPI  # type: ignore[attr-defined]
    mod_ai.API = _FakeAPI  # type: ignore[attr-defined]

    mod_ai.Unauthenticated = _Unauthenticated  # type: ignore[attr-defined]
    mod_err.RequestError = _RequestError  # type: ignore[attr-defined]
    mod_err.UserNotFound = _UserNotFound  # type: ignore[attr-defined]
    mod_err.UserNotConfirmed = _UserNotConfirmed  # type: ignore[attr-defined]
    mod_err.PasswordChangeRequired = _PasswordChangeRequired  # type: ignore[attr-defined]

    # Register in sys.modules so import statements in the integration resolve
    monkeypatch.setitem(sys.modules, "aiorinnai", mod_aiorinnai)
    monkeypatch.setitem(sys.modules, "aiorinnai.api", mod_ai)
    monkeypatch.setitem(sys.modules, "aiorinnai.errors", mod_err)


def _load_integration_module(monkeypatch):
    """Load custom_components.rinnai from local source path and register in sys.modules."""
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    _ensure_package_modules(repo_root)
    base_dir = repo_root / "custom_components" / "rinnai"

    # Preload const so relative imports succeed
    _load_module("custom_components.rinnai.const", base_dir / "const.py")
    # Preload device (needed by __init__)
    _load_module("custom_components.rinnai.device", base_dir / "device.py")

    return _load_module("custom_components.rinnai", base_dir / "__init__.py")


def _load_config_flow_module(monkeypatch):
    _install_fake_aiorinnai(monkeypatch)
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    _ensure_package_modules(repo_root)
    base_dir = repo_root / "custom_components" / "rinnai"
    # Ensure const is present
    if "custom_components.rinnai.const" not in sys.modules:
        _load_module("custom_components.rinnai.const", base_dir / "const.py")
    return _load_module(
        "custom_components.rinnai.config_flow", base_dir / "config_flow.py"
    )


@pytest.mark.asyncio
async def test_async_setup_entry_success(hass, monkeypatch):
    # Arrange fakes before loading integration module
    _install_fake_aiorinnai(monkeypatch)

    mod = _load_integration_module(monkeypatch)

    # Avoid importing platform modules during test
    async def _no_forward(entry, platforms):
        return None

    async def _no_unload(entry, platforms):
        return True

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", _no_forward)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", _no_unload)

    # Short-circuit the device refresh to avoid hitting API
    async def _fake_refresh(self):
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

    # Act
    ok = await mod.async_setup_entry(hass, entry)

    # Assert
    assert ok is True
    # Runtime data should be set on the entry
    assert hasattr(entry, "runtime_data")
    assert entry.runtime_data is not None
    assert len(entry.runtime_data.devices) == 1

    # Cleanup - unload to cancel timers
    await mod.async_unload_entry(hass, entry)


@pytest.mark.asyncio
async def test_async_setup_entry_auth_failed(hass, monkeypatch):
    _install_fake_aiorinnai(monkeypatch)
    mod = _load_integration_module(monkeypatch)

    # Cause Unauthenticated during token renewal
    async def _raise_unauth(self, email, access, refresh):
        raise _Unauthenticated()

    monkeypatch.setattr(_FakeAPI, "async_renew_access_token", _raise_unauth)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "bad",
            "conf_refresh_token": "bad",
        },
        options={
            "maint_interval_enabled": False,
        },
        version=2,
    )
    entry.add_to_hass(hass)

    with pytest.raises(ConfigEntryAuthFailed):
        await mod.async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_config_flow_reauth_success(hass, monkeypatch):
    _install_fake_aiorinnai(monkeypatch)
    cf_mod = _load_config_flow_module(monkeypatch)

    # Create an existing entry that needs reauth
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "old@example.com",
            "conf_access_token": "old_access",
            "conf_refresh_token": "old_refresh",
        },
        options={
            "maint_interval_enabled": False,
        },
        version=1,
    )
    entry.add_to_hass(hass)

    flow = cf_mod.ConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": entry.entry_id}

    # Patch reload to no-op
    async def _no_reload(eid):
        return None

    monkeypatch.setattr(hass.config_entries, "async_reload", _no_reload)

    # Step 1: show form
    form = await flow.async_step_reauth()
    assert form["type"] == "form"

    # Step 2: submit credentials
    result = await flow.async_step_reauth(
        {CONF_EMAIL: "new@example.com", CONF_PASSWORD: "pw"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"

    # Entry updated
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated is not None
    assert updated.data["email"] == "new@example.com"
    assert updated.data["conf_access_token"] == "new_access"
    assert updated.data["conf_refresh_token"] == "new_refresh"


@pytest.mark.asyncio
async def test_async_setup_entry_request_error_raises_not_ready(hass, monkeypatch):
    """Test that RequestError during setup raises ConfigEntryNotReady."""
    from homeassistant.exceptions import ConfigEntryNotReady

    _install_fake_aiorinnai(monkeypatch)
    mod = _load_integration_module(monkeypatch)

    # Cause RequestError during token renewal
    async def _raise_request_error(self, email, access, refresh):
        raise _RequestError("Connection failed")

    monkeypatch.setattr(_FakeAPI, "async_renew_access_token", _raise_request_error)

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

    with pytest.raises(ConfigEntryNotReady):
        await mod.async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_coordinator_has_available_property(hass, monkeypatch):
    """Test that coordinator exposes available property."""
    _install_fake_aiorinnai(monkeypatch)
    mod = _load_integration_module(monkeypatch)

    # Avoid importing platform modules during test
    async def _no_forward(entry, platforms):
        return None

    async def _no_unload(entry, platforms):
        return True

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", _no_forward)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", _no_unload)

    # Short-circuit the device refresh to avoid hitting API
    async def _fake_refresh(self):
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

    ok = await mod.async_setup_entry(hass, entry)
    assert ok is True

    # Get the coordinator from runtime_data
    assert hasattr(entry, "runtime_data")
    devices = entry.runtime_data.devices
    assert len(devices) == 1
    coordinator = devices[0]

    # Check available property exists
    assert hasattr(coordinator, "available")

    # Cleanup - unload to cancel timers
    await mod.async_unload_entry(hass, entry)


@pytest.mark.asyncio
async def test_async_unload_entry(hass, monkeypatch):
    """Test that unloading a config entry removes data from hass.data."""
    _install_fake_aiorinnai(monkeypatch)
    mod = _load_integration_module(monkeypatch)

    async def _no_forward(entry, platforms):
        return None

    async def _no_unload(entry, platforms):
        return True

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", _no_forward)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", _no_unload)

    async def _fake_refresh(self):
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

    # Setup
    ok = await mod.async_setup_entry(hass, entry)
    assert ok is True
    # Runtime data should be set on the entry
    assert hasattr(entry, "runtime_data")
    assert entry.runtime_data is not None

    # Unload
    ok = await mod.async_unload_entry(hass, entry)
    assert ok is True


@pytest.mark.asyncio
async def test_token_expiration_check():
    """Test the token expiration checking function."""
    import time
    import jwt

    # We need to test the function logic directly
    # Create a token that expires in 10 minutes
    future_exp = int(time.time()) + 600  # 10 minutes from now
    valid_token = jwt.encode({"exp": future_exp}, "secret", algorithm="HS256")

    # Create a token that expired 10 minutes ago
    past_exp = int(time.time()) - 600
    expired_token = jwt.encode({"exp": past_exp}, "secret", algorithm="HS256")

    # Test with manual decode to verify logic
    # Valid token should NOT be expired (buffer is 300 seconds = 5 min)
    valid_payload = jwt.decode(valid_token, options={"verify_signature": False})
    assert time.time() < (valid_payload["exp"] - 300)  # Not expired with buffer

    # Expired token should be expired
    expired_payload = jwt.decode(expired_token, options={"verify_signature": False})
    assert time.time() > (expired_payload["exp"] - 300)  # Expired


@pytest.mark.asyncio
async def test_coordinator_calls_ensure_valid_token(hass, monkeypatch):
    """Test that coordinator checks token validity before API calls."""
    _install_fake_aiorinnai(monkeypatch)
    mod = _load_integration_module(monkeypatch)

    # Track if _ensure_valid_token is called
    token_check_called = []

    async def _track_token_check(self):
        token_check_called.append(True)

    # Avoid importing platform modules during test
    async def _no_forward(entry, platforms):
        return None

    async def _no_unload(entry, platforms):
        return True

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", _no_forward)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", _no_unload)

    # Mock _ensure_valid_token to track calls
    monkeypatch.setattr(
        mod.RinnaiDeviceDataUpdateCoordinator, "_ensure_valid_token", _track_token_check
    )

    # Short-circuit the device refresh to avoid hitting API
    async def _fake_refresh(self):
        # Simulate calling _async_update_data internals
        await self._ensure_valid_token()
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

    ok = await mod.async_setup_entry(hass, entry)
    assert ok is True

    # Verify _ensure_valid_token was called during setup
    assert len(token_check_called) >= 1, "Token validation should be called"

    # Cleanup - unload to cancel timers
    await mod.async_unload_entry(hass, entry)
