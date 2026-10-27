"""Tests that Rinnai readings follow the Home Assistant unit system.

The device always speaks Fahrenheit and gallons; Home Assistant converts for
display. These tests go through real entity state, not entity internals.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.const import UnitOfVolumeFlowRate
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM
from test_e2e_config_entry import _setup_entry

DOMAIN = "rinnai"
DEVICE_ID = "device-1"


def _entity_id(hass, platform: str, entity_type: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{DEVICE_ID}_{entity_type}"
    )
    assert entity_id is not None, f"{platform} {entity_type} not registered"
    return entity_id


@pytest.mark.asyncio
async def test_flow_rate_sensor_is_gallons_per_minute_in_us_system(
    hass, enable_custom_integrations, monkeypatch
):
    """Raw flow 5 means 0.5 gal/min; a US system shows it unchanged."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await _setup_entry(hass, monkeypatch)

    state = hass.states.get(_entity_id(hass, "sensor", "water_flow_rate"))

    assert state is not None
    assert state.attributes["unit_of_measurement"] == (
        UnitOfVolumeFlowRate.GALLONS_PER_MINUTE
    )
    assert float(state.state) == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_flow_rate_sensor_suggests_litres_per_minute_in_metric_system(
    hass, enable_custom_integrations, monkeypatch
):
    """A new metric install registers the flow sensor in L/min (0.5 gal/min = 1.89)."""
    hass.config.units = METRIC_SYSTEM
    await _setup_entry(hass, monkeypatch)

    state = hass.states.get(_entity_id(hass, "sensor", "water_flow_rate"))

    assert state is not None
    assert state.attributes["unit_of_measurement"] == (
        UnitOfVolumeFlowRate.LITERS_PER_MINUTE
    )
    assert float(state.state) == pytest.approx(1.89, abs=0.01)


@pytest.mark.asyncio
async def test_water_heater_attributes_are_fahrenheit_in_us_system(
    hass, enable_custom_integrations, monkeypatch
):
    """Fixture readings of 118 F and 70 F are shown as-is."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await _setup_entry(hass, monkeypatch)

    state = hass.states.get(_entity_id(hass, "water_heater", "water_heater"))

    assert state is not None
    assert state.attributes["outlet_temperature"] == 118.0
    assert state.attributes["inlet_temperature"] == 70.0


@pytest.mark.asyncio
async def test_water_heater_attributes_are_celsius_in_metric_system(
    hass, enable_custom_integrations, monkeypatch
):
    """118 F is 47.8 C and 70 F is 21.1 C."""
    hass.config.units = METRIC_SYSTEM
    await _setup_entry(hass, monkeypatch)

    state = hass.states.get(_entity_id(hass, "water_heater", "water_heater"))

    assert state is not None
    assert state.attributes["outlet_temperature"] == 47.8
    assert state.attributes["inlet_temperature"] == 21.1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("celsius", "expected_fahrenheit"),
    [
        (40, 104),  # 104.0 F is a valid setpoint
        (41, 106),  # 105.8 F rounds to 106
        (49, 120),  # 120.2 F rounds to 120
        (51, 125),  # 123.8 F rounds to 124, nearest setpoint is 125
        (60, 140),  # 140.0 F, the maximum
    ],
)
async def test_set_temperature_in_celsius_sends_valid_fahrenheit_setpoint(
    hass, enable_custom_integrations, monkeypatch, celsius, expected_fahrenheit
):
    """A Celsius setpoint reaches the device as a valid Fahrenheit setpoint."""
    hass.config.units = METRIC_SYSTEM
    entry, mod = await _setup_entry(hass, monkeypatch)
    # The default 110-140 F range would clamp 40 C, so open the full range.
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "min_temp": 98, "max_temp": 140}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    mock_set = AsyncMock(return_value=None)
    monkeypatch.setattr(
        mod.RinnaiDeviceDataUpdateCoordinator, "async_set_temperature", mock_set
    )

    await hass.services.async_call(
        "water_heater",
        "set_temperature",
        {
            "entity_id": _entity_id(hass, "water_heater", "water_heater"),
            "temperature": celsius,
        },
        blocking=True,
    )

    mock_set.assert_awaited_once_with(expected_fahrenheit)


@pytest.mark.asyncio
async def test_flow_rate_sensor_keeps_registered_unit_after_system_change(
    hass, enable_custom_integrations, monkeypatch
):
    """The metric suggestion applies on first registration only."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry, _ = await _setup_entry(hass, monkeypatch)
    await hass.config_entries.async_unload(entry.entry_id)
    hass.config.units = METRIC_SYSTEM

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(_entity_id(hass, "sensor", "water_flow_rate"))
    assert state is not None
    assert state.attributes["unit_of_measurement"] == (
        UnitOfVolumeFlowRate.GALLONS_PER_MINUTE
    )


async def _statistics_unit(hass, statistic_id: str) -> str | None:
    """Read the unit stored in the recorder metadata for a statistic."""
    from functools import partial

    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.statistics import get_metadata

    metadatas = await get_instance(hass).async_add_executor_job(
        partial(get_metadata, hass, statistic_ids={statistic_id})
    )
    return metadatas[statistic_id][1]["unit_of_measurement"] if metadatas else None


async def _seed_flow_statistics(hass, statistic_id: str, unit: str) -> None:
    """Record one hourly statistic for the flow sensor in the given unit."""
    from datetime import timedelta

    from homeassistant.components.recorder.models import (
        StatisticData,
        StatisticMetaData,
    )
    from homeassistant.components.recorder.statistics import async_import_statistics
    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.components.recorder.common import (
        async_wait_recording_done,
    )

    start = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(
        hours=2
    )
    async_import_statistics(
        hass,
        StatisticMetaData(
            has_mean=True,
            has_sum=False,
            mean_type=1,
            name=None,
            source="recorder",
            statistic_id=statistic_id,
            unit_class=None,
            unit_of_measurement=unit,
        ),
        [StatisticData(start=start, mean=1.0, min=0.0, max=2.0)],
    )
    await async_wait_recording_done(hass)


@pytest.mark.asyncio
async def test_legacy_gpm_statistics_are_relabelled_to_gal_per_min(
    recorder_mock, hass, enable_custom_integrations, monkeypatch
):
    """Statistics recorded as "gpm" are relabelled so they are not suppressed."""
    from pytest_homeassistant_custom_component.components.recorder.common import (
        async_wait_recording_done,
    )

    hass.config.units = US_CUSTOMARY_SYSTEM
    entry, _ = await _setup_entry(hass, monkeypatch)
    entity_id = _entity_id(hass, "sensor", "water_flow_rate")
    await hass.config_entries.async_unload(entry.entry_id)
    await _seed_flow_statistics(hass, entity_id, "gpm")
    assert await _statistics_unit(hass, entity_id) == "gpm"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    assert await _statistics_unit(hass, entity_id) == "gal/min"


@pytest.mark.asyncio
async def test_other_flow_statistics_units_are_left_alone(
    recorder_mock, hass, enable_custom_integrations, monkeypatch
):
    """Only the legacy "gpm" label is rewritten; a user-chosen unit is kept."""
    from pytest_homeassistant_custom_component.components.recorder.common import (
        async_wait_recording_done,
    )

    hass.config.units = US_CUSTOMARY_SYSTEM
    entry, _ = await _setup_entry(hass, monkeypatch)
    entity_id = _entity_id(hass, "sensor", "water_flow_rate")
    await hass.config_entries.async_unload(entry.entry_id)
    await _seed_flow_statistics(hass, entity_id, "L/min")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    assert await _statistics_unit(hass, entity_id) == "L/min"
