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
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')

            writer.write(b'list\n')
            await writer.drain()

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
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()

            status = self.parse_data(''.join(total_data))

            LOGGER.debug(status)

            return status

        except asyncio.TimeoutError:
            print("Timeout error")
        except ConnectionRefusedError:
            print("Connection refused error")
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None
    
    async def get_sysinfo(self):

        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')

            writer.write(b'sysinfo\n')
            await writer.drain()

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
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()

            sysinfo = ''.join(total_data)

            LOGGER.debug(sysinfo)

            return json.loads(sysinfo)

        except asyncio.TimeoutError:
            print("Timeout error")
        except ConnectionRefusedError:
            print("Connection refused error")
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None

    @staticmethod
    def parse_data(data):
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

                # Convert numerical strings to integers or floats
                if value.isdigit():
                    value = int(value)
                else:
                    try:
                        value = float(value)
                    except ValueError:
                        pass

                key_value_pairs[key] = value

        return key_value_pairs

    async def set_temperature(self, temp: int):
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')

            writer.write(b'set set_domestic_temperature ' + str(temp) + '\n')
            await writer.drain()

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
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()

            request = ''.join(total_data)

            LOGGER.debug(request)

            if request == f"#? set 'set_domestic_temperature' to {temp} ({hex(temp)})\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            print("Timeout error")
        except ConnectionRefusedError:
            print("Connection refused error")
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None


    async def start_recirculation(self, duration: int):
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')

            writer.write(b'set recirculation_duration ' + str(duration) + '\n')
            await writer.drain()

            writer.write(b'set set_recirculation_enabled true' + '\n')
            await writer.drain()

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
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()

            request = ''.join(total_data)

            LOGGER.debug(request)

            if request == "#? set 'set_recirculation_enabled' to true\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            print("Timeout error")
        except ConnectionRefusedError:
            print("Connection refused error")
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None


    async def stop_recirculation(self):
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')

            writer.write(b'set set_recirculation_enabled false' + '\n')
            await writer.drain()

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
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()

            request = ''.join(total_data)

            LOGGER.debug(request)

            if request == "#? set 'set_recirculation_enabled' to false\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            print("Timeout error")
        except ConnectionRefusedError:
            print("Connection refused error")
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None

    async def vacation_mode_on(self):
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')

            writer.write(b'set schedule_holiday true' + '\n')
            await writer.drain()

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
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()

            request = ''.join(total_data)

            LOGGER.debug(request)

            if request == "#? set 'schedule_holiday' to true\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            print("Timeout error")
        except ConnectionRefusedError:
            print("Connection refused error")
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None

    async def vacation_mode_off(self):
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')

            writer.write(b'set schedule_holiday false' + '\n')
            await writer.drain()

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
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()

            request = ''.join(total_data)

            LOGGER.debug(request)

            if request == "#? set 'schedule_holiday' to false\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            print("Timeout error")
        except ConnectionRefusedError:
            print("Connection refused error")
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None

    async def turn_off(self):
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')

            writer.write(b'set set_operation_enabled false' + '\n')
            await writer.drain()

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
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()

            request = ''.join(total_data)

            LOGGER.debug(request)

            if request == "#? set 'set_operation_enabled' to false\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            print("Timeout error")
        except ConnectionRefusedError:
            print("Connection refused error")
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None

    async def turn_on(self):
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')

            writer.write(b'set set_operation_enabled true' + '\n')
            await writer.drain()

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
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()

            request = ''.join(total_data)

            LOGGER.debug(request)

            if request == "#? set 'set_operation_enabled' to true\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            print("Timeout error")
        except ConnectionRefusedError:
            print("Connection refused error")
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None

    async def do_maintenance_retrieval(self):
        try:
            # Create a socket object
            reader, writer = await asyncio.open_connection(self.host, PORT)

            # Assuming the server sends data upon connection
            socket_data = await reader.read(1024)
            socket_data = socket_data.decode('utf-8')

            writer.write(b'set do_maintenance_retrieval true' + '\n')
            await writer.drain()

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
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    break  # If reading data takes too long, break out

            writer.close()
            await writer.wait_closed()

            request = ''.join(total_data)

            LOGGER.debug(request)

            if request == "#? set \'do_maintenance_retrieval\' to true\n":
                return json.loads('{"success": true}')
            else:
                return json.loads('{"success": false}')

        except asyncio.TimeoutError:
            print("Timeout error")
        except ConnectionRefusedError:
            print("Connection refused error")
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        return None