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
    
    def get_status(self):
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
            json_data = {"water_flow_rate": int(status[1] or None), "outlet_temperature": int(status[5]), "combustion_hours_raw": int(status[9] or None),"combustion_cycles": int(status[13] or None),
                     "fan_frequency": int(status[17] or None), "inlet_temperature": int(status[29]), "fan_current": int(status[33] or None),
                     "pump_hours": int(status[68] or None), "pump_cycles": int(status[72] or None), "exhaust_temperature": int(status[76] or None),
                     "domestic_combustion": bool(status[95]), "domestic_temperature": int(status[99]), "recirculation_capable": bool(status[103] or None),
                     "recirculation_duration": int(status[106] or None), "operation_enabled": bool(status[163]), "priority_status": bool(status[166]),
                     "recirculation_enabled": bool(status[169]), "set_domestic_temperature": int(status[175] or None), "schedule_enabled": bool(status[189] or None),
                     "schedule_holiday": bool(status[192] or None), "firmware_version": status[206]}
            LOGGER.debug(type(json_data))
        except IndexError as msg:
            LOGGER.debug(msg)
            raise IndexError(msg)
        
        self.s.close()
        
        return str(json_data)

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