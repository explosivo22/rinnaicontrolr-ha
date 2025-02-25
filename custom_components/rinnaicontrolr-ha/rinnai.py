import asyncio
import json
import socket
import re
import time

from .const import LOGGER

PORT = 9798
BUFF_SIZE = 512

class WaterHeater(object):
    def __init__(self, host):
        self.host = host

    async def get_status(self):
        LOGGER.debug("Getting status from water heater")
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)
            LOGGER.debug("Connection established")

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')
            LOGGER.debug(f"Initial data received: {socket_data}")

            writer.write(b'list\n')
            await writer.drain()
            LOGGER.debug("Sent 'list' command")

            total_data = []
            timeout = 2

            begin = asyncio.get_event_loop().time()
            while True:
                if total_data and asyncio.get_event_loop().time() - begin > timeout:
                    break
                elif asyncio.get_event_loop().time() - begin > timeout * 2:
                    break

                try:
                    socket_data = await asyncio.wait_for(reader.read(8192), timeout=1)
                    if socket_data:
                        total_data.append(socket_data.decode())
                        begin = asyncio.get_event_loop().time()
                        LOGGER.debug(f"Data chunk received: {socket_data.decode()}")
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()
            LOGGER.debug("Connection closed")

            status = self.parse_data(''.join(total_data))
            LOGGER.debug(f"Parsed status: {status}")

            return status

        except asyncio.TimeoutError:
            LOGGER.error("Timeout error")
        except ConnectionRefusedError:
            LOGGER.error("Connection refused error")
        except socket.error as e:
            LOGGER.error(f"Socket error: {e}")
        except Exception as e:
            LOGGER.error(f"An unexpected error occurred: {e}")

        return None
    
    async def get_sysinfo(self):
        LOGGER.debug("Getting system info from water heater")
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)
            LOGGER.debug("Connection established")

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')
            LOGGER.debug(f"Initial data received: {socket_data}")

            writer.write(b'sysinfo\n')
            await writer.drain()
            LOGGER.debug("Sent 'sysinfo' command")

            total_data = []
            timeout = 2

            begin = asyncio.get_event_loop().time()
            while True:
                if total_data and asyncio.get_event_loop().time() - begin > timeout:
                    break
                elif asyncio.get_event_loop().time() - begin > timeout * 2:
                    break

                try:
                    socket_data = await asyncio.wait_for(reader.read(8192), timeout=1)
                    if socket_data:
                        total_data.append(socket_data.decode())
                        begin = asyncio.get_event_loop().time()
                        LOGGER.debug(f"Data chunk received: {socket_data.decode()}")
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()
            LOGGER.debug("Connection closed")

            sysinfo = ''.join(total_data)
            LOGGER.debug(f"System info received: {sysinfo}")

            return json.loads(sysinfo)

        except asyncio.TimeoutError:
            LOGGER.error("Timeout error")
        except ConnectionRefusedError:
            LOGGER.error("Connection refused error")
        except socket.error as e:
            LOGGER.error(f"Socket error: {e}")
        except Exception as e:
            LOGGER.error(f"An unexpected error occurred: {e}")

        return None

    @staticmethod
    def parse_data(data):
        LOGGER.debug(f"Parsing data: {data}")
        key_value_pairs = {}
        pattern = re.compile(r'([^\s]+)')  # Pattern to match valid value before extra data
        temp_pattern = re.compile(r'(\d+)')  # Pattern to match only numbers

        for line in data.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # Specific handling for set_domestic_temperature to remove '+'
                if key == "set_domestic_temperature":
                    match = temp_pattern.search(value)
                    if match:
                        value = match.group(1)

                # Specific handling for schedule_holiday to remove '+' and '{70d}'
                elif key == "schedule_holiday":
                    value = value.replace("+", "").strip()
                    value = re.sub(r'\{.*?\}', '', value).strip()

                # General handling to remove extra data in parentheses, braces, and single quotes
                else:
                    match = pattern.search(value)
                    if match:
                        value = match.group(1).replace("'", "")

                # Convert 'null' to None
                if value.lower() == 'null':
                    value = None
                # Convert numerical strings to integers or floats
                elif value.isdigit():
                    value = int(value)
                else:
                    try:
                        value = float(value)
                    except ValueError:
                        pass

                key_value_pairs[key] = value

        LOGGER.debug(f"Parsed key-value pairs: {key_value_pairs}")
        return key_value_pairs

    async def set_temperature(self, temp: int):
        LOGGER.debug(f"Setting temperature to {temp}")
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)
            LOGGER.debug("Connection established")

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')
            LOGGER.debug(f"Initial data received: {socket_data}")

            writer.write(bytes('set set_domestic_temperature ' + str(temp) + '\n', 'utf-8'))
            await writer.drain()
            LOGGER.debug("Sent 'set_domestic_temperature' command")

            total_data = []
            timeout = 2

            begin = asyncio.get_event_loop().time()
            while True:
                if total_data and asyncio.get_event_loop().time() - begin > timeout:
                    break
                elif asyncio.get_event_loop().time() - begin > timeout * 2:
                    break

                try:
                    socket_data = await asyncio.wait_for(reader.read(8192), timeout=1)
                    if socket_data:
                        total_data.append(socket_data.decode())
                        begin = asyncio.get_event_loop().time()
                        LOGGER.debug(f"Data chunk received: {socket_data.decode()}")
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()
            LOGGER.debug("Connection closed")

            request = ''.join(total_data)
            LOGGER.debug(f"Request response: {request}")

            pattern = r"#\? set 'set_domestic_temperature' to \d+ \(0x[0-9a-fA-F]+\)\n"
            if re.match(pattern, request):
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            LOGGER.error("Timeout error")
        except ConnectionRefusedError:
            LOGGER.error("Connection refused error")
        except socket.error as e:
            LOGGER.error(f"Socket error: {e}")
        except Exception as e:
            LOGGER.error(f"An unexpected error occurred: {e}")

        return None


    async def start_recirculation(self, duration: int):
        LOGGER.debug(f"Starting recirculation for {duration} minutes")
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)
            LOGGER.debug("Connection established")

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')
            LOGGER.debug(f"Initial data received: {socket_data}")

            writer.write(bytes('set recirculation_duration ' + str(duration) + '\n', 'utf-8'))
            await writer.drain()
            LOGGER.debug("Sent 'recirculation_duration' command")

            writer.write(bytes('set set_recirculation_enabled true' + '\n', 'utf-8'))
            await writer.drain()
            LOGGER.debug("Sent 'set_recirculation_enabled' command")

            total_data = []
            timeout = 2

            begin = asyncio.get_event_loop().time()
            while True:
                if total_data and asyncio.get_event_loop().time() - begin > timeout:
                    break
                elif asyncio.get_event_loop().time() - begin > timeout * 2:
                    break

                try:
                    socket_data = await asyncio.wait_for(reader.read(8192), timeout=1)
                    if socket_data:
                        total_data.append(socket_data.decode())
                        begin = asyncio.get_event_loop().time()
                        LOGGER.debug(f"Data chunk received: {socket_data.decode()}")
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()
            LOGGER.debug("Connection closed")

            request = ''.join(total_data)
            LOGGER.debug(f"Request response: {request}")

            if request == "#? set 'set_recirculation_enabled' to true\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            LOGGER.error("Timeout error")
        except ConnectionRefusedError:
            LOGGER.error("Connection refused error")
        except socket.error as e:
            LOGGER.error(f"Socket error: {e}")
        except Exception as e:
            LOGGER.error(f"An unexpected error occurred: {e}")

        return None


    async def stop_recirculation(self):
        LOGGER.debug("Stopping recirculation")
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)
            LOGGER.debug("Connection established")

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')
            LOGGER.debug(f"Initial data received: {socket_data}")

            writer.write(bytes('set set_recirculation_enabled false' + '\n', 'utf-8'))
            await writer.drain()
            LOGGER.debug("Sent 'set_recirculation_enabled' command")

            total_data = []
            timeout = 2

            begin = asyncio.get_event_loop().time()
            while True:
                if total_data and asyncio.get_event_loop().time() - begin > timeout:
                    break
                elif asyncio.get_event_loop().time() - begin > timeout * 2:
                    break

                try:
                    socket_data = await asyncio.wait_for(reader.read(8192), timeout=1)
                    if socket_data:
                        total_data.append(socket_data.decode())
                        begin = asyncio.get_event_loop().time()
                        LOGGER.debug(f"Data chunk received: {socket_data.decode()}")
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()
            LOGGER.debug("Connection closed")

            request = ''.join(total_data)
            LOGGER.debug(f"Request response: {request}")

            if request == "#? set 'set_recirculation_enabled' to false\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            LOGGER.error("Timeout error")
        except ConnectionRefusedError:
            LOGGER.error("Connection refused error")
        except socket.error as e:
            LOGGER.error(f"Socket error: {e}")
        except Exception as e:
            LOGGER.error(f"An unexpected error occurred: {e}")

        return None

    async def vacation_mode_on(self):
        LOGGER.debug("Turning vacation mode on")
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)
            LOGGER.debug("Connection established")

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')
            LOGGER.debug(f"Initial data received: {socket_data}")

            writer.write(bytes('set schedule_holiday true' + '\n', 'utf-8'))
            await writer.drain()
            LOGGER.debug("Sent 'schedule_holiday' command")

            total_data = []
            timeout = 2

            begin = asyncio.get_event_loop().time()
            while True:
                if total_data and asyncio.get_event_loop().time() - begin > timeout:
                    break
                elif asyncio.get_event_loop().time() - begin > timeout * 2:
                    break

                try:
                    socket_data = await asyncio.wait_for(reader.read(8192), timeout=1)
                    if socket_data:
                        total_data.append(socket_data.decode())
                        begin = asyncio.get_event_loop().time()
                        LOGGER.debug(f"Data chunk received: {socket_data.decode()}")
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()
            LOGGER.debug("Connection closed")

            request = ''.join(total_data)
            LOGGER.debug(f"Request response: {request}")

            if request == "#? set 'schedule_holiday' to true\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            LOGGER.error("Timeout error")
        except ConnectionRefusedError:
            LOGGER.error("Connection refused error")
        except socket.error as e:
            LOGGER.error(f"Socket error: {e}")
        except Exception as e:
            LOGGER.error(f"An unexpected error occurred: {e}")

        return None

    async def vacation_mode_off(self):
        LOGGER.debug("Turning vacation mode off")
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)
            LOGGER.debug("Connection established")

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')
            LOGGER.debug(f"Initial data received: {socket_data}")

            writer.write(bytes('set schedule_holiday false' + '\n', 'utf-8'))
            await writer.drain()
            LOGGER.debug("Sent 'schedule_holiday' command")

            total_data = []
            timeout = 2

            begin = asyncio.get_event_loop().time()
            while True:
                if total_data and asyncio.get_event_loop().time() - begin > timeout:
                    break
                elif asyncio.get_event_loop().time() - begin > timeout * 2:
                    break

                try:
                    socket_data = await asyncio.wait_for(reader.read(8192), timeout=1)
                    if socket_data:
                        total_data.append(socket_data.decode())
                        begin = asyncio.get_event_loop().time()
                        LOGGER.debug(f"Data chunk received: {socket_data.decode()}")
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()
            LOGGER.debug("Connection closed")

            request = ''.join(total_data)
            LOGGER.debug(f"Request response: {request}")

            if request == "#? set 'schedule_holiday' to false\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            LOGGER.error("Timeout error")
        except ConnectionRefusedError:
            LOGGER.error("Connection refused error")
        except socket.error as e:
            LOGGER.error(f"Socket error: {e}")
        except Exception as e:
            LOGGER.error(f"An unexpected error occurred: {e}")

        return None

    async def turn_off(self):
        LOGGER.debug("Turning off water heater")
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)
            LOGGER.debug("Connection established")

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')
            LOGGER.debug(f"Initial data received: {socket_data}")

            writer.write(bytes('set set_operation_enabled false' + '\n' ,'utf-8'))
            await writer.drain()
            LOGGER.debug("Sent 'set_operation_enabled' command")

            total_data = []
            timeout = 2

            begin = asyncio.get_event_loop().time()
            while True:
                if total_data and asyncio.get_event_loop().time() - begin > timeout:
                    break
                elif asyncio.get_event_loop().time() - begin > timeout * 2:
                    break

                try:
                    socket_data = await asyncio.wait_for(reader.read(8192), timeout=1)
                    if socket_data:
                        total_data.append(socket_data.decode())
                        begin = asyncio.get_event_loop().time()
                        LOGGER.debug(f"Data chunk received: {socket_data.decode()}")
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()
            LOGGER.debug("Connection closed")

            request = ''.join(total_data)
            LOGGER.debug(f"Request response: {request}")

            if request == "#? set 'set_operation_enabled' to false\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            LOGGER.error("Timeout error")
        except ConnectionRefusedError:
            LOGGER.error("Connection refused error")
        except socket.error as e:
            LOGGER.error(f"Socket error: {e}")
        except Exception as e:
            LOGGER.error(f"An unexpected error occurred: {e}")

        return None

    async def turn_on(self):
        LOGGER.debug("Turning on water heater")
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)
            LOGGER.debug("Connection established")

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')
            LOGGER.debug(f"Initial data received: {socket_data}")

            writer.write(bytes('set set_operation_enabled true' + '\n', 'utf-8'))
            await writer.drain()
            LOGGER.debug("Sent 'set_operation_enabled' command")

            total_data = []
            timeout = 2

            begin = asyncio.get_event_loop().time()
            while True:
                if total_data and asyncio.get_event_loop().time() - begin > timeout:
                    break
                elif asyncio.get_event_loop().time() - begin > timeout * 2:
                    break

                try:
                    socket_data = await asyncio.wait_for(reader.read(8192), timeout=1)
                    if socket_data:
                        total_data.append(socket_data.decode())
                        begin = asyncio.get_event_loop().time()
                        LOGGER.debug(f"Data chunk received: {socket_data.decode()}")
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()
            LOGGER.debug("Connection closed")

            request = ''.join(total_data)
            LOGGER.debug(f"Request response: {request}")

            if request == "#? set 'set_operation_enabled' to true\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            LOGGER.error("Timeout error")
        except ConnectionRefusedError:
            LOGGER.error("Connection refused error")
        except socket.error as e:
            LOGGER.error(f"Socket error: {e}")
        except Exception as e:
            LOGGER.error(f"An unexpected error occurred: {e}")

        return None

    async def do_maintenance_retrieval(self):
        LOGGER.debug("Performing maintenance retrieval")
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)
            LOGGER.debug("Connection established")

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')
            LOGGER.debug(f"Initial data received: {socket_data}")

            writer.write(bytes('set do_maintenance_retrieval true' + '\n', 'utf-8'))
            await writer.drain()
            LOGGER.debug("Sent 'do_maintenance_retrieval' command")

            total_data = []
            timeout = 2

            begin = asyncio.get_event_loop().time()
            while True:
                if total_data and asyncio.get_event_loop().time() - begin > timeout:
                    break
                elif asyncio.get_event_loop().time() - begin > timeout * 2:
                    break

                try:
                    socket_data = await asyncio.wait_for(reader.read(8192), timeout=1)
                    if socket_data:
                        total_data.append(socket_data.decode())
                        begin = asyncio.get_event_loop().time()
                        LOGGER.debug(f"Data chunk received: {socket_data.decode()}")
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()
            LOGGER.debug("Connection closed")

            request = ''.join(total_data)
            LOGGER.debug(f"Request response: {request}")

            if request == "#? set 'do_maintenance_retrieval' to true\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            LOGGER.error("Timeout error")
        except ConnectionRefusedError:
            LOGGER.error("Connection refused error")
        except socket.error as e:
            LOGGER.error(f"Socket error: {e}")
        except Exception as e:
            LOGGER.error(f"An unexpected error occurred: {e}")

        return None