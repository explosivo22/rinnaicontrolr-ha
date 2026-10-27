"""Tests for Rinnai diagnostics redaction."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from homeassistant.components.diagnostics import REDACTED

from custom_components.rinnai.const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_STORED_PASSWORD,
    DOMAIN,
)
from custom_components.rinnai.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)

SERIAL = "SERIAL-ABC-12345"
SECRETS = {
    "email": "user@example.com",
    CONF_ACCESS_TOKEN: "access-token-value",
    CONF_REFRESH_TOKEN: "refresh-token-value",
    CONF_STORED_PASSWORD: "hunter2-password",
}


def _coordinator() -> SimpleNamespace:
    return SimpleNamespace(
        id=SERIAL,
        device_name="Water Heater",
        manufacturer="Rinnai",
        model="RE199iN",
        firmware_version="1.0",
        connection_mode="cloud",
        is_using_fallback=False,
        available=True,
        last_update_success=True,
        is_on=True,
        is_heating=False,
        is_recirculating=False,
        vacation_mode_on=False,
        target_temperature=120,
        current_temperature=110,
        outlet_temperature=110,
        inlet_temperature=70,
        water_flow_rate=0,
        temperature_table=2,
        combustion_cycles=1,
        operation_hours=2,
        pump_hours=3,
        pump_cycles=4,
        fan_current=5,
        fan_frequency=6,
        _device_information=None,
        _local_data=None,
        _consecutive_errors=0,
    )


def _entry() -> Any:
    return SimpleNamespace(
        entry_id="entry-id",
        version=1,
        domain=DOMAIN,
        title="Rinnai",
        data=dict(SECRETS),
        options={},
        runtime_data=SimpleNamespace(
            connection_mode="cloud",
            devices=[_coordinator()],
            known_device_ids={SERIAL},
        ),
    )


async def test_entry_diagnostics_redact_all_secrets() -> None:
    """Every secret stored in entry.data must be redacted."""
    result = await async_get_config_entry_diagnostics(None, _entry())  # type: ignore[arg-type]

    for key in SECRETS:
        assert result["entry"]["data"][key] == REDACTED, key


async def test_entry_diagnostics_redact_device_id() -> None:
    """The heater serial must not appear anywhere in entry diagnostics."""
    result = await async_get_config_entry_diagnostics(None, _entry())  # type: ignore[arg-type]

    assert SERIAL not in str(result)
    assert result["devices"][0]["device_id"] == REDACTED
    assert result["runtime"]["known_device_ids"] == [REDACTED]


async def test_device_diagnostics_redact_device_id() -> None:
    """Device diagnostics must redact the serial."""
    device = SimpleNamespace(identifiers={(DOMAIN, SERIAL)})

    result = await async_get_device_diagnostics(None, _entry(), device)  # type: ignore[arg-type]

    assert SERIAL not in str(result)
    assert result["device"]["device_id"] == REDACTED


async def test_device_diagnostics_not_found_redacts_identifiers() -> None:
    """The coordinator-not-found fallback must not leak the serial."""
    device = SimpleNamespace(identifiers={(DOMAIN, "OTHER-SERIAL-999")})

    result = await async_get_device_diagnostics(None, _entry(), device)  # type: ignore[arg-type]

    assert "OTHER-SERIAL-999" not in str(result)
    assert result["error"] == "Device coordinator not found"


async def test_entry_diagnostics_redact_title() -> None:
    """The entry title holds the email (cloud) or serial (local)."""
    entry = _entry()
    entry.title = f"Rinnai {SERIAL}"

    result = await async_get_config_entry_diagnostics(None, entry)  # type: ignore[arg-type]

    assert result["entry"]["title"] == REDACTED
    assert SERIAL not in str(result)


async def test_diagnostics_include_temperature_table() -> None:
    """The unparsed unit-table field is exposed to help identify regional units."""
    entry_result = await async_get_config_entry_diagnostics(None, _entry())  # type: ignore[arg-type]
    device = SimpleNamespace(identifiers={(DOMAIN, SERIAL)})
    device_result = await async_get_device_diagnostics(None, _entry(), device)  # type: ignore[arg-type]

    assert entry_result["devices"][0]["maintenance"]["temperature_table"] == 2
    assert device_result["maintenance"]["temperature_table"] == 2
