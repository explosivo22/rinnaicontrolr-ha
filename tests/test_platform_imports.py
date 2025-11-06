import sys
import pathlib
import importlib.util

PLATFORMS = [
    "sensor.py",
    "binary_sensor.py",
    "water_heater.py",
]


def _load_module(module_name: str, file_path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_platform_modules_importable():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    base_dir = repo_root / "custom_components" / "rinnaicontrolr-ha"

    # Load const first to satisfy relative imports
    _load_module("custom_components.rinnai.const", base_dir / "const.py")

    for fname in PLATFORMS:
        mod_name = f"custom_components.rinnai.{fname[:-3]}"
        _load_module(mod_name, base_dir / fname)
