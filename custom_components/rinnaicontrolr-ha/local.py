"""Local TCP client for Rinnai Control-R water heaters.

Communicates directly with the water heater controller via TCP port 9798.
No authentication required - direct local network access.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from .const import LOCAL_PORT, LOGGER

DEFAULT_TIMEOUT = 10.0


class RinnaiLocalClient:
    """Local TCP client for Rinnai water heater control."""

    def __init__(self, host: str) -> None:
        """Initialize the local client.

        Args:
            host: IP address or hostname of the Rinnai controller.
        """
        self.host = host

    async def _send_command(
        self, command: str, timeout: float = DEFAULT_TIMEOUT
    ) -> str | None:
        """Send a command to the water heater and return the response.

        Args:
            command: The command to send (e.g., "list", "sysinfo", "set prop value").
            timeout: Connection timeout in seconds.

        Returns:
            The response string, or None on error.
        """
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, LOCAL_PORT), timeout=timeout
            )
            assert writer is not None  # Connection succeeded

            # Read initial prompt
            await asyncio.wait_for(reader.read(1024), timeout=2)

            # Send command
            writer.write(f"{command}\n".encode("utf-8"))
            await writer.drain()

            # Read response with timeout
            chunks: list[str] = []
            read_timeout = 2.0
            last_read = time.monotonic()

            while True:
                elapsed = time.monotonic() - last_read
                if chunks and elapsed > read_timeout:
                    break
                if elapsed > read_timeout * 2:
                    break

                try:
                    data = await asyncio.wait_for(reader.read(8192), timeout=1)
                    if data:
                        chunks.append(data.decode("utf-8"))
                        last_read = time.monotonic()
                    else:
                        await asyncio.sleep(0.1)
                except TimeoutError:
                    break

            return "".join(chunks)

        except TimeoutError:
            LOGGER.error("Timeout connecting to Rinnai controller at %s", self.host)
        except ConnectionRefusedError:
            LOGGER.error("Connection refused by Rinnai controller at %s", self.host)
        except OSError as e:
            LOGGER.error("Socket error communicating with Rinnai controller: %s", e)
        except Exception as e:
            LOGGER.error("Unexpected error communicating with Rinnai controller: %s", e)
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()

        return None

    async def get_status(self) -> dict[str, Any] | None:
        """Get all device properties via the 'list' command.

        Returns:
            Dictionary of property name to value, or None on error.
        """
        LOGGER.debug("Getting status from water heater at %s", self.host)
        response = await self._send_command("list")

        if response is None:
            return None

        return self._parse_list_response(response)

    async def get_sysinfo(self) -> dict[str, Any] | None:
        """Get system information via the 'sysinfo' command.

        Returns:
            Dictionary with sysinfo data, or None on error.
        """
        LOGGER.debug("Getting sysinfo from water heater at %s", self.host)
        response = await self._send_command("sysinfo")

        if response is None:
            return None

        try:
            # Find JSON in response (skip any prompt lines)
            for line in response.split("\n"):
                line = line.strip()
                if line.startswith("{"):
                    return json.loads(line)
        except json.JSONDecodeError as e:
            LOGGER.error("Failed to parse sysinfo JSON: %s", e)

        return None

    async def set_temperature(self, temperature: int) -> bool:
        """Set the target water temperature.

        Args:
            temperature: Target temperature in Fahrenheit (110-140).

        Returns:
            True if successful, False otherwise.
        """
        LOGGER.debug("Setting temperature to %d°F", temperature)
        response = await self._send_command(
            f"set set_domestic_temperature {temperature}"
        )
        return self._check_set_response(response, "set_domestic_temperature")

    async def start_recirculation(self, duration: int = 5) -> bool:
        """Start recirculation for the specified duration.

        Args:
            duration: Duration in minutes (default 5).

        Returns:
            True if successful, False otherwise.
        """
        LOGGER.debug("Starting recirculation for %d minutes", duration)

        # Set duration first
        await self._send_command(f"set recirculation_duration {duration}")

        # Then enable recirculation
        response = await self._send_command("set set_recirculation_enabled true")
        return self._check_set_response(response, "set_recirculation_enabled")

    async def stop_recirculation(self) -> bool:
        """Stop recirculation.

        Returns:
            True if successful, False otherwise.
        """
        LOGGER.debug("Stopping recirculation")
        response = await self._send_command("set set_recirculation_enabled false")
        return self._check_set_response(response, "set_recirculation_enabled")

    async def turn_on(self) -> bool:
        """Turn on the water heater.

        Returns:
            True if successful, False otherwise.
        """
        LOGGER.debug("Turning on water heater")
        response = await self._send_command("set set_operation_enabled true")
        return self._check_set_response(response, "set_operation_enabled")

    async def turn_off(self) -> bool:
        """Turn off the water heater.

        Returns:
            True if successful, False otherwise.
        """
        LOGGER.debug("Turning off water heater")
        response = await self._send_command("set set_operation_enabled false")
        return self._check_set_response(response, "set_operation_enabled")

    async def enable_vacation_mode(self) -> bool:
        """Enable vacation/holiday mode.

        Returns:
            True if successful, False otherwise.
        """
        LOGGER.debug("Enabling vacation mode")
        response = await self._send_command("set schedule_holiday true")
        return self._check_set_response(response, "schedule_holiday")

    async def disable_vacation_mode(self) -> bool:
        """Disable vacation/holiday mode.

        Returns:
            True if successful, False otherwise.
        """
        LOGGER.debug("Disabling vacation mode")
        response = await self._send_command("set schedule_holiday false")
        return self._check_set_response(response, "schedule_holiday")

    async def do_maintenance_retrieval(self) -> bool:
        """Trigger maintenance data retrieval from the heater.

        Returns:
            True if successful, False otherwise.
        """
        LOGGER.debug("Triggering maintenance retrieval")
        response = await self._send_command("set do_maintenance_retrieval true")
        return self._check_set_response(response, "do_maintenance_retrieval")

    async def test_connection(self) -> bool:
        """Test if the controller is reachable.

        Returns:
            True if connection successful, False otherwise.
        """
        sysinfo = await self.get_sysinfo()
        return sysinfo is not None

    @staticmethod
    def _check_set_response(response: str | None, property_name: str) -> bool:
        """Check if a set command was successful.

        Args:
            response: The response from the controller.
            property_name: The property that was set.

        Returns:
            True if the response indicates success.
        """
        if response is None:
            return False
        # Success response format: #? set 'property_name' to value
        return f"set '{property_name}'" in response

    @staticmethod
    def _parse_list_response(data: str) -> dict[str, Any]:
        """Parse the response from the 'list' command.

        Args:
            data: Raw response string from the list command.

        Returns:
            Dictionary of property name to parsed value.
        """
        properties: dict[str, Any] = {}
        number_pattern = re.compile(r"(\d+)")

        for line in data.split("\n"):
            if ":" not in line:
                continue

            key, raw_value = line.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()

            if not key:
                continue

            # parsed_value can be str, int, float, bool, or None
            parsed_value: Any = raw_value

            # Handle special cases
            if key == "set_domestic_temperature":
                # Remove '+' prefix and extract number, fallback to domestic_temperature
                if "null" in raw_value.lower():
                    parsed_value = properties.get("domestic_temperature", None)
                else:
                    match = number_pattern.search(raw_value)
                    if match:
                        parsed_value = int(match.group(1))

            elif key == "schedule_holiday":
                # Remove '+' and metadata like '{70d}'
                parsed_value = raw_value.replace("+", "").strip()
                parsed_value = re.sub(r"\{.*?\}", "", parsed_value).strip()

            else:
                # General handling: extract first token, remove quotes
                match = re.match(r"([^\s]+)", raw_value)
                if match:
                    parsed_value = match.group(1).replace("'", "")

            # Convert types
            if isinstance(parsed_value, str):
                if parsed_value.lower() == "null":
                    parsed_value = None
                elif parsed_value.lower() == "true":
                    parsed_value = True
                elif parsed_value.lower() == "false":
                    parsed_value = False
                elif parsed_value.isdigit():
                    parsed_value = int(parsed_value)
                else:
                    try:
                        parsed_value = float(parsed_value)
                    except ValueError:
                        pass  # Keep as string

            properties[key] = parsed_value

        return properties
