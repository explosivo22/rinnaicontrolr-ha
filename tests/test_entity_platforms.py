"""Tests for Rinnai entity platforms (sensor, binary_sensor, water_heater)."""
import sys
import types
import pathlib
import importlib.util
from unittest.mock import MagicMock, PropertyMock

import pytest


# Constants to mirror the integration
DOMAIN = "rinnai"


def _ensure_package_modules(repo_root: pathlib.Path):
    """Ensure custom_components packages exist in sys.modules."""
    cc_name = "custom_components"
    pkg_name = "custom_components.rinnai"
    cc = sys.modules.get(cc_name) or types.ModuleType(cc_name)
    cc.__path__ = [str(repo_root / "custom_components")]
    sys.modules[cc_name] = cc

    pkg = sys.modules.get(pkg_name) or types.ModuleType(pkg_name)
    pkg.__path__ = [str(repo_root / "custom_components" / "rinnaicontrolr-ha")]
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

    class _FakeAPI:
        pass

    class _Unauthenticated(Exception):
        pass

    class _RequestError(Exception):
        pass

    mod_aiorinnai.API = _FakeAPI
    mod_ai.API = _FakeAPI
    mod_ai.Unauthenticated = _Unauthenticated
    mod_err.RequestError = _RequestError

    monkeypatch.setitem(sys.modules, "aiorinnai", mod_aiorinnai)
    monkeypatch.setitem(sys.modules, "aiorinnai.api", mod_ai)
    monkeypatch.setitem(sys.modules, "aiorinnai.errors", mod_err)


def _load_entity_modules(monkeypatch):
    """Load entity-related modules."""
    _install_fake_aiorinnai(monkeypatch)
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    _ensure_package_modules(repo_root)
    base_dir = repo_root / "custom_components" / "rinnaicontrolr-ha"

    # Preload dependencies
    _load_module("custom_components.rinnai.const", base_dir / "const.py")
    _load_module("custom_components.rinnai.device", base_dir / "device.py")
    _load_module("custom_components.rinnai.entity", base_dir / "entity.py")

    # Create a fake __init__ module with just the type alias
    init_mod = types.ModuleType("custom_components.rinnai")
    init_mod.__path__ = [str(base_dir)]
    # RinnaiConfigEntry is just a type alias, we can fake it
    from homeassistant.config_entries import ConfigEntry
    init_mod.RinnaiConfigEntry = ConfigEntry  # type: ignore[attr-defined]
    sys.modules["custom_components.rinnai"] = init_mod

    sensor_mod = _load_module("custom_components.rinnai.sensor", base_dir / "sensor.py")
    binary_sensor_mod = _load_module("custom_components.rinnai.binary_sensor", base_dir / "binary_sensor.py")

    return sensor_mod, binary_sensor_mod


def _create_mock_device():
    """Create a mock coordinator device with typical values."""
    device = MagicMock()
    device.device_name = "Rinnai Water Heater"
    device.id = "device-1"  # Used for unique_id and device registry
    device.serial_number = "SN123456"
    device.model = "RUR199"
    device.firmware_version = "1.0"
    device.manufacturer = "Rinnai"

    # Temperature properties
    device.outlet_temperature = 120.5
    device.inlet_temperature = 60.3
    device.current_temperature = 120.5
    device.target_temperature = 120

    # Sensor properties
    device.water_flow_rate = 25  # Will be multiplied by 0.1 = 2.5 gpm
    device.combustion_cycles = 150
    device.operation_hours = 500
    device.pump_hours = 100
    device.pump_cycles = 50
    device.fan_current = 100
    device.fan_frequency = 60

    # Boolean properties
    device.is_recirculating = True
    device.is_heating = False
    device.available = True

    return device


# =====================
# Sensor Tests
# =====================

@pytest.mark.asyncio
async def test_outlet_temperature_sensor(monkeypatch):
    """Test outlet temperature sensor returns correct value."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()

    sensor = sensor_mod.RinnaiOutletTemperatureSensor(device)

    assert sensor.native_value == 120.5
    assert sensor.native_unit_of_measurement == "°F"
    assert sensor.device_class.value == "temperature"
    assert sensor.state_class.value == "measurement"


@pytest.mark.asyncio
async def test_outlet_temperature_sensor_none(monkeypatch):
    """Test outlet temperature sensor returns None when value is None."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.outlet_temperature = None

    sensor = sensor_mod.RinnaiOutletTemperatureSensor(device)

    assert sensor.native_value is None


@pytest.mark.asyncio
async def test_inlet_temperature_sensor(monkeypatch):
    """Test inlet temperature sensor returns correct value."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()

    sensor = sensor_mod.RinnaiInletTemperatureSensor(device)

    assert sensor.native_value == 60.3
    assert sensor.native_unit_of_measurement == "°F"


@pytest.mark.asyncio
async def test_inlet_temperature_sensor_none(monkeypatch):
    """Test inlet temperature sensor returns None when value is None."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.inlet_temperature = None

    sensor = sensor_mod.RinnaiInletTemperatureSensor(device)

    assert sensor.native_value is None


@pytest.mark.asyncio
async def test_water_flow_rate_sensor(monkeypatch):
    """Test water flow rate sensor applies 0.1 multiplier."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.water_flow_rate = 25  # Should become 2.5 gpm

    sensor = sensor_mod.RinnaiWaterFlowRateSensor(device)

    assert sensor.native_value == 2.5
    assert sensor._attr_native_unit_of_measurement == "gpm"


@pytest.mark.asyncio
async def test_water_flow_rate_sensor_none(monkeypatch):
    """Test water flow rate sensor returns None when value is None."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.water_flow_rate = None

    sensor = sensor_mod.RinnaiWaterFlowRateSensor(device)

    assert sensor.native_value is None


@pytest.mark.asyncio
async def test_combustion_cycles_sensor(monkeypatch):
    """Test combustion cycles sensor returns correct value."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()

    sensor = sensor_mod.RinnaiCombustionCyclesSensor(device)

    assert sensor.native_value == 150
    assert sensor._attr_native_unit_of_measurement == "cycles"


@pytest.mark.asyncio
async def test_combustion_cycles_sensor_none(monkeypatch):
    """Test combustion cycles sensor returns None when value is None."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.combustion_cycles = None

    sensor = sensor_mod.RinnaiCombustionCyclesSensor(device)

    assert sensor.native_value is None


@pytest.mark.asyncio
async def test_operation_hours_sensor(monkeypatch):
    """Test operation hours sensor returns correct value."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()

    sensor = sensor_mod.RinnaiOperationHoursSensor(device)

    assert sensor.native_value == 500
    assert sensor.state_class.value == "measurement"


@pytest.mark.asyncio
async def test_operation_hours_sensor_none(monkeypatch):
    """Test operation hours sensor returns None when value is None."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.operation_hours = None

    sensor = sensor_mod.RinnaiOperationHoursSensor(device)

    assert sensor.native_value is None


@pytest.mark.asyncio
async def test_pump_hours_sensor(monkeypatch):
    """Test pump hours sensor returns correct value."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()

    sensor = sensor_mod.RinnaiPumpHoursSensor(device)

    assert sensor.native_value == 100
    assert sensor.state_class.value == "measurement"


@pytest.mark.asyncio
async def test_pump_hours_sensor_none(monkeypatch):
    """Test pump hours sensor returns None when value is None."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.pump_hours = None

    sensor = sensor_mod.RinnaiPumpHoursSensor(device)

    assert sensor.native_value is None


@pytest.mark.asyncio
async def test_pump_cycles_sensor(monkeypatch):
    """Test pump cycles sensor returns correct value."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()

    sensor = sensor_mod.RinnaiPumpCyclesSensor(device)

    assert sensor.native_value == 50
    assert sensor._attr_native_unit_of_measurement == "cycles"


@pytest.mark.asyncio
async def test_pump_cycles_sensor_none(monkeypatch):
    """Test pump cycles sensor returns None when value is None."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.pump_cycles = None

    sensor = sensor_mod.RinnaiPumpCyclesSensor(device)

    assert sensor.native_value is None


@pytest.mark.asyncio
async def test_fan_current_sensor(monkeypatch):
    """Test fan current sensor returns correct value."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()

    sensor = sensor_mod.RinnaiFanCurrentSensor(device)

    assert sensor.native_value == 100
    assert sensor.native_unit_of_measurement == "mA"
    assert sensor.state_class.value == "measurement"


@pytest.mark.asyncio
async def test_fan_current_sensor_none(monkeypatch):
    """Test fan current sensor returns None when value is None."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.fan_current = None

    sensor = sensor_mod.RinnaiFanCurrentSensor(device)

    assert sensor.native_value is None


@pytest.mark.asyncio
async def test_fan_frequency_sensor(monkeypatch):
    """Test fan frequency sensor returns correct value."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()

    sensor = sensor_mod.RinnaiFanFrequencySensor(device)

    assert sensor.native_value == 60
    assert sensor.native_unit_of_measurement == "Hz"
    assert sensor.state_class.value == "measurement"


@pytest.mark.asyncio
async def test_fan_frequency_sensor_none(monkeypatch):
    """Test fan frequency sensor returns None when value is None."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.fan_frequency = None

    sensor = sensor_mod.RinnaiFanFrequencySensor(device)

    assert sensor.native_value is None


# =====================
# Binary Sensor Tests
# =====================

@pytest.mark.asyncio
async def test_recirculating_binary_sensor_on(monkeypatch):
    """Test recirculating binary sensor when on."""
    _, binary_sensor_mod = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.is_recirculating = True

    sensor = binary_sensor_mod.RinnaiIsRecirculatingBinarySensor(device)

    assert sensor.is_on is True
    assert sensor.icon == "mdi:autorenew"


@pytest.mark.asyncio
async def test_recirculating_binary_sensor_off(monkeypatch):
    """Test recirculating binary sensor when off."""
    _, binary_sensor_mod = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.is_recirculating = False

    sensor = binary_sensor_mod.RinnaiIsRecirculatingBinarySensor(device)

    assert sensor.is_on is False
    assert sensor.icon == "mdi:circle-off-outline"


@pytest.mark.asyncio
async def test_heating_binary_sensor_on(monkeypatch):
    """Test heating binary sensor when on."""
    _, binary_sensor_mod = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.is_heating = True

    sensor = binary_sensor_mod.RinnaiIsHeatingBinarySensor(device)

    assert sensor.is_on is True
    assert sensor.icon == "mdi:fire"


@pytest.mark.asyncio
async def test_heating_binary_sensor_off(monkeypatch):
    """Test heating binary sensor when off."""
    _, binary_sensor_mod = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.is_heating = False

    sensor = binary_sensor_mod.RinnaiIsHeatingBinarySensor(device)

    assert sensor.is_on is False
    assert sensor.icon == "mdi:fire-off"


# =====================
# Entity Base Tests
# =====================

@pytest.mark.asyncio
async def test_entity_unique_id(monkeypatch):
    """Test entity unique_id is correctly generated."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.id = "device-12345"

    sensor = sensor_mod.RinnaiOutletTemperatureSensor(device)

    # unique_id should be {device.id}_{entity_type}
    assert sensor.unique_id == "device-12345_outlet_temperature"


@pytest.mark.asyncio
async def test_entity_device_info(monkeypatch):
    """Test entity device_info is correctly populated."""
    sensor_mod, _ = _load_entity_modules(monkeypatch)
    device = _create_mock_device()
    device.id = "device-12345"
    device.model = "RUR199"
    device.firmware_version = "2.0"
    device.device_name = "My Water Heater"
    device.manufacturer = "Rinnai"

    sensor = sensor_mod.RinnaiOutletTemperatureSensor(device)
    device_info = sensor.device_info

    assert device_info["identifiers"] == {("rinnai", "device-12345")}
    assert device_info["name"] == "My Water Heater"
    assert device_info["manufacturer"] == "Rinnai"
    assert device_info["model"] == "RUR199"
    assert device_info["sw_version"] == "2.0"
