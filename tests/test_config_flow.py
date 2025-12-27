"""Tests for Rinnai config flow."""

import sys
import types
import pathlib
import importlib.util

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType

DOMAIN = "rinnai"


class _RequestError(Exception):
    """Fake RequestError."""

    pass


class _UserNotFound(Exception):
    """Fake UserNotFound."""

    pass


class _UserNotConfirmed(Exception):
    """Fake UserNotConfirmed."""

    pass


class _PasswordChangeRequired(Exception):
    """Fake PasswordChangeRequired."""

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

    async def get_info(self, device_id: str):
        return {
            "data": {
                "getDevice": {
                    "device_name": "Rinnai Water Heater",
                    "model": "RUR199",
                    "firmware": "1.0",
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

        # Sub-objects (None until login, like real API)
        self.user = None
        self.device = None

        # Test control flags
        self._fail_with_request_error = False

    @property
    def access_token(self):
        """Public accessor for access token (for config_flow.py compatibility)."""
        return self._access_token

    @property
    def refresh_token(self):
        """Public accessor for refresh token (for config_flow.py compatibility)."""
        return self._refresh_token

    async def async_login(self, email: str, password: str):
        """Simulate login - populates user/device and tokens."""
        if self._fail_with_request_error:
            raise _RequestError("Connection failed")
        self.username = email
        self.is_connected = True
        self._access_token = "new_access_token"
        self._refresh_token = "new_refresh_token"
        self._id_token = "new_id_token"
        # Populate sub-objects after login (like real API)
        self.user = _FakeUser()
        self.device = _FakeDevice()
        return None

    async def async_renew_access_token(
        self,
        email: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ):
        """Simulate token renewal."""
        if self._fail_with_request_error:
            raise _RequestError("Connection failed")
        self.username = email
        self.is_connected = True
        self._access_token = "renewed_access_token"
        self._refresh_token = "renewed_refresh_token"
        self._id_token = "renewed_id_token"
        # Populate sub-objects after token renewal (like real API)
        self.user = _FakeUser()
        self.device = _FakeDevice()
        return None

    async def async_check_token(self):
        """Check if token is valid."""
        pass

    def close(self):
        """Close the session."""
        pass


def _ensure_package_modules(repo_root: pathlib.Path):
    """Ensure custom_components packages exist in sys.modules."""
    cc_name = "custom_components"
    pkg_name = "custom_components.rinnai"
    cc = sys.modules.get(cc_name) or types.ModuleType(cc_name)
    cc.__path__ = [str(repo_root / "custom_components")]
    sys.modules[cc_name] = cc

    pkg = sys.modules.get(pkg_name) or types.ModuleType(pkg_name)
    pkg.__path__ = [str(repo_root / "custom_components" / "rinnai")]
    sys.modules[pkg_name] = pkg


def _load_module(module_name: str, file_path: pathlib.Path):
    """Load a module from file path."""
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _install_fake_aiorinnai(monkeypatch):
    """Install fake aiorinnai modules."""
    mod_aiorinnai = types.ModuleType("aiorinnai")
    mod_ai = types.ModuleType("aiorinnai.api")
    mod_err = types.ModuleType("aiorinnai.errors")

    mod_aiorinnai.API = _FakeAPI
    mod_ai.API = _FakeAPI
    mod_err.RequestError = _RequestError
    mod_err.UserNotFound = _UserNotFound
    mod_err.UserNotConfirmed = _UserNotConfirmed
    mod_err.PasswordChangeRequired = _PasswordChangeRequired

    monkeypatch.setitem(sys.modules, "aiorinnai", mod_aiorinnai)
    monkeypatch.setitem(sys.modules, "aiorinnai.api", mod_ai)
    monkeypatch.setitem(sys.modules, "aiorinnai.errors", mod_err)


def _load_config_flow_module(monkeypatch):
    """Load config_flow module."""
    _install_fake_aiorinnai(monkeypatch)
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    _ensure_package_modules(repo_root)
    base_dir = repo_root / "custom_components" / "rinnai"

    # Preload const
    _load_module("custom_components.rinnai.const", base_dir / "const.py")

    return _load_module(
        "custom_components.rinnai.config_flow", base_dir / "config_flow.py"
    )


@pytest.mark.asyncio
async def test_config_flow_user_step_shows_form(hass, monkeypatch):
    """Test that user step shows the connection mode selection form."""
    cf_mod = _load_config_flow_module(monkeypatch)

    flow = cf_mod.ConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    # User step now shows connection_mode selector first
    assert "connection_mode" in result["data_schema"].schema


@pytest.mark.asyncio
async def test_config_flow_user_step_success(hass, monkeypatch):
    """Test successful multi-step flow creates config entry."""
    import asyncio

    cf_mod = _load_config_flow_module(monkeypatch)

    flow = cf_mod.ConfigFlow()
    flow.hass = hass
    flow.context = {}

    # Step 1: Select connection mode
    result = await flow.async_step_user({"connection_mode": "cloud"})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cloud"

    # Step 2: Enter credentials
    result = await flow.async_step_cloud(
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "testpassword",
        }
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"][CONF_EMAIL] == "test@example.com"
    assert "conf_access_token" in result["data"]
    assert "conf_refresh_token" in result["data"]

    # Allow background tasks and executor shutdown to complete
    await hass.async_block_till_done()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_config_flow_user_step_connection_error(hass, monkeypatch):
    """Test cloud step handles connection errors."""
    cf_mod = _load_config_flow_module(monkeypatch)

    # Make API fail with RequestError
    original_init = _FakeAPI.__init__

    def failing_init(
        self,
        session=None,
        timeout=30.0,
        retry_count=3,
        retry_delay=1.0,
        retry_multiplier=2.0,
        executor_timeout=30.0,
    ):
        original_init(
            self,
            session=session,
            timeout=timeout,
            retry_count=retry_count,
            retry_delay=retry_delay,
            retry_multiplier=retry_multiplier,
            executor_timeout=executor_timeout,
        )
        self._fail_with_request_error = True

    monkeypatch.setattr(_FakeAPI, "__init__", failing_init)

    flow = cf_mod.ConfigFlow()
    flow.hass = hass
    flow.context = {}

    # Step 1: Select connection mode
    await flow.async_step_user({"connection_mode": "cloud"})

    # Step 2: Enter credentials - should fail
    result = await flow.async_step_cloud(
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "testpassword",
        }
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_config_flow_reauth_step_shows_form(hass, monkeypatch):
    """Test reauth step shows form with prefilled email."""
    cf_mod = _load_config_flow_module(monkeypatch)

    flow = cf_mod.ConfigFlow()
    flow.hass = hass
    flow.context = {CONF_EMAIL: "old@example.com"}

    result = await flow.async_step_reauth()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth"


@pytest.mark.asyncio
async def test_config_flow_reauth_step_success(hass, monkeypatch):
    """Test successful reauth updates config entry."""
    cf_mod = _load_config_flow_module(monkeypatch)

    # Create existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "old@example.com",
            "conf_access_token": "old_access",
            "conf_refresh_token": "old_refresh",
        },
        version=2,
    )
    entry.add_to_hass(hass)

    # Patch reload to no-op
    async def _no_reload(eid):
        return None

    monkeypatch.setattr(hass.config_entries, "async_reload", _no_reload)

    flow = cf_mod.ConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": entry.entry_id}

    # Submit reauth
    result = await flow.async_step_reauth(
        {
            CONF_EMAIL: "new@example.com",
            CONF_PASSWORD: "newpassword",
        }
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    # Verify entry was updated
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.data["email"] == "new@example.com"
    assert updated.data["conf_access_token"] == "new_access_token"


@pytest.mark.asyncio
async def test_config_flow_reauth_connection_error(hass, monkeypatch):
    """Test reauth handles connection errors."""
    cf_mod = _load_config_flow_module(monkeypatch)

    # Make API fail
    original_init = _FakeAPI.__init__

    def failing_init(
        self,
        session=None,
        timeout=30.0,
        retry_count=3,
        retry_delay=1.0,
        retry_multiplier=2.0,
        executor_timeout=30.0,
    ):
        original_init(
            self,
            session=session,
            timeout=timeout,
            retry_count=retry_count,
            retry_delay=retry_delay,
            retry_multiplier=retry_multiplier,
            executor_timeout=executor_timeout,
        )
        self._fail_with_request_error = True

    monkeypatch.setattr(_FakeAPI, "__init__", failing_init)

    flow = cf_mod.ConfigFlow()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_reauth(
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "testpassword",
        }
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_config_flow_reauth_no_entry_id(hass, monkeypatch):
    """Test reauth aborts if no entry_id in context."""
    cf_mod = _load_config_flow_module(monkeypatch)

    flow = cf_mod.ConfigFlow()
    flow.hass = hass
    flow.context = {}  # No entry_id

    result = await flow.async_step_reauth(
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "testpassword",
        }
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_failed"


@pytest.mark.asyncio
async def test_options_flow_init_shows_form(hass, monkeypatch):
    """Test options flow shows form with current values."""
    cf_mod = _load_config_flow_module(monkeypatch)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={
            "maint_interval_enabled": True,
        },
        version=2,
    )
    entry.add_to_hass(hass)

    # Use the proper HA options flow initialization via ConfigFlow
    config_flow = cf_mod.ConfigFlow()
    config_flow.hass = hass
    flow = config_flow.async_get_options_flow(entry)
    flow.hass = hass

    result = await flow.async_step_init()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_options_flow_submit(hass, monkeypatch):
    """Test options flow saves new options."""
    cf_mod = _load_config_flow_module(monkeypatch)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "conf_access_token": "access",
            "conf_refresh_token": "refresh",
        },
        options={
            "maint_interval_enabled": True,
        },
        version=2,
    )
    entry.add_to_hass(hass)

    # Use the proper HA options flow initialization via ConfigFlow
    config_flow = cf_mod.ConfigFlow()
    config_flow.hass = hass
    flow = config_flow.async_get_options_flow(entry)
    flow.hass = hass

    result = await flow.async_step_init(
        {
            "maint_interval_enabled": False,
        }
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["maint_interval_enabled"] is False
