import socket
import json

from time import sleep

from .const import LOGGER

PORT = 9798
BUFF_SIZE = 512

class WaterHeater(object):

    def __init__(self, host: str) -> None:
        self.host = host

    def init_connect(self):
        LOGGER.debug("connecting to socket with host: %s" % self.host)
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.host, PORT))
        #self.s.timeout(5)
        sleep(1) #sleep here just to make sure we have time to connect
        self.s.recv(32)
    
    def get_status(self) -> dict:
        self.init_connect()
        LOGGER.debug("connected to socket")

        data = b''
        try:
            LOGGER.debug("sending data to socket")
            self.s.sendall(bytes('list' + '\n', 'UTF-8'))
            sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            LOGGER.debug("Socket Error: %s" % msg)
        while True:
            part = self.s.recv(BUFF_SIZE)
            #LOGGER.debug(part)
            #length = len(part)
            data += part
            if len(part) < BUFF_SIZE:
                # either 0 or end of data
                break

        status = data.decode('UTF-8').split()
        json_data = ""
        try:
            json_data = ('{"water_flow_rate": %s, "outlet_temperature": %s, "combustion_hours_raw": %s,"combustion_cycles": %s,'
                     '"fan_frequency": %s, "inlet_temperature": %s, "fan_current": %s,'
                     '"pump_hours": %s, "pump_cycles": %s, "exhaust_temperature": %s,'
                     '"domestic_combustion": %s, "domestic_temperature": %s, "recirculation_capable": %s,'
                     '"recirculation_duration": %s, "operation_enabled": %s, "priority_status": %s,'
                     '"recirculation_enabled": %s, "set_domestic_temperature": %s, "schedule_enabled": %s,'
                     '"schedule_holiday": %s, "firmware_version": "%s"}') % (int(status[1]),int(status[5]),int(status[9]),int(status[13]),int(status[17]),
                                                                                    int(status[29]),int(status[33]),int(status[68]),int(status[72]),int(status[76]),
                                                                                    status[96],int(status[99]),status[103],int(status[106]),status[163],
                                                                                    status[166],status[169],int(status[175]),status[191],status[194],
                                                                                    status[206].strip("'"))

            LOGGER.debug(json.loads(json_data))
            LOGGER.debug(type(json.loads(json_data)))
        except IndexError as msg:
            LOGGER.debug(msg)
            raise IndexError(msg)
        
        self.s.close()
        
        return json.loads(json_data)

    def set_temperature(self, temp: int):
        self.connect()

        try:
            self.s.sendall(bytes('set set_domestic_temperature ' + str(temp) + '\n', 'UTF-8'))
            sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()
        return request

    def start_recirculation(self, duration: int):
        self.connect()

        try:
            self.s.sendall(bytes('set set_priority_status true' + '\n', 'UTF-8'))
            self.s.sendall(bytes('set recirculation_duration ' + str(duration) + '\n', 'UTF-8'))
            self.s.sendall(bytes('set set_recirculation_enabled true' + '\n', 'UTF-8'))
            sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()
        
        return request

    def stop_recirculation(self):
        self.connect()

        try:
            self.s.sendall(bytes('set set_recirculation_enabled false' + '\n', 'UTF-8'))
            sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()
        
        return request

    def vacation_mode_on(self):
        self.connect()

        try:
            self.s.sendall(bytes('set schedule_holiday true' + '\n', 'UTF-8'))
            sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()
        
        return request

    def vacation_mode_off(self):
        self.connect()

        try:
            self.s.sendall(bytes('set schedule_holiday false' + '\n', 'UTF-8'))
            sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()
        
        return request

    def turn_off(self):
        self.connect()

        try:
            self.s.sendall(bytes('set operation_enabled false' + '\n', 'UTF-8'))
            sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()
        
        return request

    def turn_on(self):
        self.connect()

        try:
            self.s.sendall(bytes('set operation_enabled false' + '\n', 'UTF-8'))
            sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()
        
        return request

    def do_maintenance_retrieval(self):
        self.connect()

        try:
            self.s.sendall(bytes('maintenance' + '\n', 'UTF-8'))
            sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()
        
        return request