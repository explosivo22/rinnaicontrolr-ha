"""Guard the water heater's pre-2026.11 temperature aliases.

Home Assistant 2026.11 renamed the water heater temperature members with a
``native_`` prefix and removes the old names in 2027.11:
https://developers.home-assistant.io/blog/2026/10/08/water-heater-native-temperature

RinnaiWaterHeater provides both names so it keeps working on older Home
Assistant versions. These tests keep the aliases correct while they are needed
and fail as a reminder to delete them once ``hacs.json`` declares a minimum
Home Assistant version of 2026.11 or later.
"""

from __future__ import annotations

import json
import pathlib
from unittest.mock import MagicMock

import pytest
from homeassistant.const import UnitOfTemperature

from custom_components.rinnai.water_heater import RinnaiWaterHeater

NATIVE_NAMES_SINCE = (2026, 11)

# Deprecated name -> its native_ replacement
LEGACY_ALIASES = {
    "_attr_temperature_unit": "_attr_native_temperature_unit",
    "target_temperature": "native_target_temperature",
    "current_temperature": "native_current_temperature",
}

HACS_JSON = pathlib.Path(__file__).resolve().parents[1] / "hacs.json"


def _min_supported_ha_version() -> tuple[int, ...] | None:
    """Return the minimum Home Assistant version from hacs.json, if declared."""
    declared = json.loads(HACS_JSON.read_text()).get("homeassistant")
    if declared is None:
        return None
    return tuple(int(part) for part in str(declared).split(".")[:2])


def _supports_pre_native_ha() -> bool:
    """Return True while Home Assistant versions before 2026.11 are supported."""
    min_version = _min_supported_ha_version()
    return min_version is None or min_version < NATIVE_NAMES_SINCE


def _entity_with_device() -> RinnaiWaterHeater:
    """Build a water heater without running entity setup."""
    entity = RinnaiWaterHeater.__new__(RinnaiWaterHeater)
    device = MagicMock()
    device.target_temperature = 120
    device.current_temperature = 118.5
    entity._device = device
    return entity


@pytest.mark.skipif(
    not _supports_pre_native_ha(),
    reason="Home Assistant < 2026.11 is no longer supported",
)
def test_legacy_aliases_mirror_native_members() -> None:
    """The deprecated names must return the same values as the native ones."""
    for legacy in LEGACY_ALIASES:
        assert legacy in vars(RinnaiWaterHeater), f"{legacy} alias is missing"

    entity = _entity_with_device()
    assert entity._attr_native_temperature_unit == UnitOfTemperature.FAHRENHEIT
    for legacy, native in LEGACY_ALIASES.items():
        assert getattr(entity, legacy) == getattr(entity, native), legacy


@pytest.mark.skipif(
    _supports_pre_native_ha(),
    reason="Home Assistant < 2026.11 is still supported",
)
def test_legacy_aliases_removed_once_min_ha_is_2026_11() -> None:
    """Fail until the aliases are removed after the minimum version bump."""
    leftover = [name for name in LEGACY_ALIASES if name in vars(RinnaiWaterHeater)]
    assert not leftover, (
        f"hacs.json requires Home Assistant >= {'.'.join(map(str, NATIVE_NAMES_SINCE))}, "
        f"so remove the deprecated aliases {leftover} from "
        "custom_components/rinnai/water_heater.py (see the TODO(HA>=2026.11) notes)"
    )
