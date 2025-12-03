"""Diagnostics support for Rinnai Control-R integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import RinnaiConfigEntry
from .const import CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN

# Keys to redact from diagnostics output for privacy
TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_EMAIL,
    "email",
    "user_uuid",
    "thing_name",
    # Redact partial host for privacy but keep format visible
}

# Additional keys to redact from device data
TO_REDACT_DEVICE = {
    "serial_id",
    "serial_number",
    "heater_serial_number",
    "serial-number",
}


def _redact_device_data(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Redact sensitive device data."""
    if data is None:
        return None

    result = dict(data)

    # Redact nested structures
    if "data" in result and isinstance(result["data"], dict):
        result["data"] = dict(result["data"])
        if "getDevice" in result["data"] and isinstance(
            result["data"]["getDevice"], dict
        ):
            device_data = dict(result["data"]["getDevice"])
            # Redact user_uuid and thing_name
            if "user_uuid" in device_data:
                device_data["user_uuid"] = "**REDACTED**"
            if "thing_name" in device_data:
                device_data["thing_name"] = "**REDACTED**"
            if "device_name" in device_data:
                # Keep device name but truncate if too long
                pass  # Device name is user-visible, keep it

            # Redact info section
            if "info" in device_data and isinstance(device_data["info"], dict):
                info = dict(device_data["info"])
                if "serial_id" in info:
                    info["serial_id"] = "**REDACTED**"
                device_data["info"] = info

            result["data"]["getDevice"] = device_data

    return result


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: RinnaiConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    This provides debug information for troubleshooting integration issues.
    Sensitive data like tokens and email are automatically redacted.
    """
    runtime_data = entry.runtime_data

    # Collect device information
    devices_data: list[dict[str, Any]] = []
    for coordinator in runtime_data.devices:
        device_info: dict[str, Any] = {
            "device_id": coordinator.id,
            "device_name": coordinator.device_name,
            "model": coordinator.model,
            "firmware_version": coordinator.firmware_version,
            "connection_mode": coordinator.connection_mode,
            "is_using_fallback": coordinator.is_using_fallback,
            "available": coordinator.available,
            "last_update_success": coordinator.last_update_success,
        }

        # Add current state (non-sensitive operational data)
        device_info["state"] = {
            "is_on": coordinator.is_on,
            "is_heating": coordinator.is_heating,
            "is_recirculating": coordinator.is_recirculating,
            "vacation_mode_on": coordinator.vacation_mode_on,
            "target_temperature": coordinator.target_temperature,
            "current_temperature": coordinator.current_temperature,
            "outlet_temperature": coordinator.outlet_temperature,
            "inlet_temperature": coordinator.inlet_temperature,
        }

        # Add maintenance data if available
        device_info["maintenance"] = {
            "water_flow_rate": coordinator.water_flow_rate,
            "combustion_cycles": coordinator.combustion_cycles,
            "operation_hours": coordinator.operation_hours,
            "pump_hours": coordinator.pump_hours,
            "pump_cycles": coordinator.pump_cycles,
            "fan_current": coordinator.fan_current,
            "fan_frequency": coordinator.fan_frequency,
        }

        devices_data.append(device_info)

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "runtime": {
            "connection_mode": runtime_data.connection_mode,
            "device_count": len(runtime_data.devices),
            "known_device_ids": list(runtime_data.known_device_ids),
        },
        "devices": devices_data,
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: RinnaiConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a specific device.

    This provides detailed debug information for a single device.
    """
    runtime_data = entry.runtime_data

    # Find the coordinator for this device
    coordinator = None
    for coord in runtime_data.devices:
        # Check if this coordinator matches the device
        device_identifiers = {(entry.domain, coord.id)}
        if device.identifiers & device_identifiers:
            coordinator = coord
            break

    if coordinator is None:
        return {
            "error": "Device coordinator not found",
            "device_id": str(device.identifiers),
        }

    # Get raw device data (redacted)
    raw_cloud_data = None
    if coordinator._device_information:
        raw_cloud_data = _redact_device_data(coordinator._device_information)

    raw_local_data = None
    if coordinator._local_data:
        raw_local_data = async_redact_data(
            dict(coordinator._local_data), TO_REDACT_DEVICE
        )

    return {
        "device": {
            "device_id": coordinator.id,
            "device_name": coordinator.device_name,
            "manufacturer": coordinator.manufacturer,
            "model": coordinator.model,
            "firmware_version": coordinator.firmware_version,
        },
        "connection": {
            "mode": coordinator.connection_mode,
            "is_using_fallback": coordinator.is_using_fallback,
            "available": coordinator.available,
            "last_update_success": coordinator.last_update_success,
            "consecutive_errors": coordinator._consecutive_errors,
        },
        "state": {
            "is_on": coordinator.is_on,
            "is_heating": coordinator.is_heating,
            "is_recirculating": coordinator.is_recirculating,
            "vacation_mode_on": coordinator.vacation_mode_on,
            "target_temperature": coordinator.target_temperature,
            "current_temperature": coordinator.current_temperature,
            "outlet_temperature": coordinator.outlet_temperature,
            "inlet_temperature": coordinator.inlet_temperature,
        },
        "maintenance": {
            "water_flow_rate": coordinator.water_flow_rate,
            "combustion_cycles": coordinator.combustion_cycles,
            "operation_hours": coordinator.operation_hours,
            "pump_hours": coordinator.pump_hours,
            "pump_cycles": coordinator.pump_cycles,
            "fan_current": coordinator.fan_current,
            "fan_frequency": coordinator.fan_frequency,
        },
        "raw_data": {
            "cloud": raw_cloud_data,
            "local": raw_local_data,
        },
    }
