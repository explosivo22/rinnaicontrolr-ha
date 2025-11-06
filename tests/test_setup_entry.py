import sys
import types
import pathlib
from typing import Optional
from importlib.machinery import SourceFileLoader
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


class _FakeUser:
    async def get_info(self):
        return {
            "email": "test@example.com",
            "devices": {"items": [{"id": "device-1"}]},
        }


class _FakeDevice:
    async def get_info(self, device_id: str):
        return {"data": {"getDevice": {"device_name": "Rinnai", "model": "X", "firmware": "1.0", "shadow": {"set_domestic_temperature": None}, "info": {"domestic_temperature": 120}}}}


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


def _ensure_package_modules(repo_root: pathlib.Path):
    """Ensure custom_components and custom_components.rinnai exist as packages in sys.modules."""
    cc_name = "custom_components"
    pkg_name = "custom_components.rinnai"
    cc = sys.modules.get(cc_name) or types.ModuleType(cc_name)
    cc.__path__ = [str(repo_root / "custom_components")]
    sys.modules[cc_name] = cc

    pkg = sys.modules.get(pkg_name) or types.ModuleType(pkg_name)
    pkg.__path__ = [str(repo_root / "custom_components" / "rinnaicontrolr-ha")]
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

    # Register in sys.modules so import statements in the integration resolve
    monkeypatch.setitem(sys.modules, "aiorinnai", mod_aiorinnai)
    monkeypatch.setitem(sys.modules, "aiorinnai.api", mod_ai)
    monkeypatch.setitem(sys.modules, "aiorinnai.errors", mod_err)


def _load_integration_module(monkeypatch):
    """Load custom_components.rinnai from local source path and register in sys.modules."""
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    _ensure_package_modules(repo_root)
    base_dir = repo_root / "custom_components" / "rinnaicontrolr-ha"

    # Preload const so relative imports succeed
    _load_module("custom_components.rinnai.const", base_dir / "const.py")
    # Preload device (needed by __init__)
    _load_module("custom_components.rinnai.device", base_dir / "device.py")

    return _load_module("custom_components.rinnai", base_dir / "__init__.py")


def _load_config_flow_module():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    _ensure_package_modules(repo_root)
    base_dir = repo_root / "custom_components" / "rinnaicontrolr-ha"
    # Ensure const is present
    if "custom_components.rinnai.const" not in sys.modules:
        _load_module("custom_components.rinnai.const", base_dir / "const.py")
    return _load_module("custom_components.rinnai.config_flow", base_dir / "config_flow.py")


@pytest.mark.asyncio
async def test_async_setup_entry_success(hass, monkeypatch):
    # Arrange fakes before loading integration module
    _install_fake_aiorinnai(monkeypatch)

    mod = _load_integration_module(monkeypatch)

    # Avoid importing platform modules during test
    async def _no_forward(entry, platforms):
        return None

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", _no_forward)

    # Short-circuit the device refresh to avoid hitting API
    async def _fake_refresh(self):
        return None

    monkeypatch.setattr(mod.RinnaiDeviceDataUpdateCoordinator, "async_refresh", _fake_refresh)

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
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]


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
    cf_mod = _load_config_flow_module()

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
    result = await flow.async_step_reauth({CONF_EMAIL: "new@example.com", CONF_PASSWORD: "pw"})
    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"

    # Entry updated
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated is not None
    assert updated.data["email"] == "new@example.com"
    assert updated.data["conf_access_token"] == "new_access"
    assert updated.data["conf_refresh_token"] == "new_refresh"
