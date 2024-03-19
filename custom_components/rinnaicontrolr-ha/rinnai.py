import socket
import json
import time

from .const import LOGGER

PORT = 9798
BUFF_SIZE = 512

class WaterHeater(object):

    def __init__(self, host: str) -> None:
        self.host = host

    def recv_timeout(self,timeout=2):
        #make socket non blocking
        self.s.setblocking(0)
        
        #total data partwise in an array
        total_data=[]
        data=''
        
        #beginning time
        begin=time.time()
        while 1:
            #if you got some data, then break after timeout
            if total_data and time.time()-begin > timeout:
                break
            
            #if you got no data at all, wait a little longer, twice the timeout
            elif time.time()-begin > timeout*2:
                break
            
            #recv something
            try:
                data = self.s.recv(8192)
                if data:
                    total_data.append(data.decode())
                    #change the beginning time for measurement
                    begin=time.time()
                else:
                    #sleep for sometime to indicate a gap
                    time.sleep(0.1)
            except:
                pass
    
        #join all parts to make final string
        return ''.join(total_data)

    def connect(self):
        LOGGER.debug("connecting to socket with host: %s" % self.host)
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.host, PORT))
        #self.s.timeout(5)
        time.sleep(1) #sleep here just to make sure we have time to connect
        self.s.recv(32)
    
    def get_status(self) -> dict:
        self.connect()
        LOGGER.debug("connected to socket")

        self.s.sendall(bytes('list' + '\n', 'UTF-8'))

        receive = self.recv_timeout().replace('\n',',')
        status = receive.split()
        json_data = ""
        try:
            json_data = ('{"water_flow_rate": %s, "outlet_temperature": %s, "combustion_hours_raw": %s,"combustion_cycles": %s,'
                     '"fan_frequency": %s, "inlet_temperature": %s, "fan_current": %s,'
                     '"pump_hours": %s, "pump_cycles": %s, "exhaust_temperature": %s,'
                     '"domestic_combustion": %s, "domestic_temperature": %s, "recirculation_capable": %s,'
                     '"recirculation_duration": %s, "operation_enabled": %s, "priority_status": %s,'
                     '"recirculation_enabled": %s, "set_domestic_temperature": %s, "schedule_enabled": %s,'
                     '"schedule_holiday": %s, "firmware_version": "%s"}') % (int(status[1] or None),int(status[5] or None),int(status[9] or None),int(status[13] or None),int(status[17] or None),
                                                                                    int(status[29] or None),int(status[33] or None),int(status[68] or None),int(status[72] or None),int(status[76]or None),
                                                                                    status[96],int(status[99] or None),status[103],int(status[106] or None),status[167],
                                                                                    status[170],status[173],int(status[179] or None),status[195],status[198],
                                                                                    status[210].strip("'"))

        except IndexError as msg:
            LOGGER.debug(msg)
            raise IndexError(msg)
        
        self.s.close()

        LOGGER.debug(json_data)
        
        return json.loads(json_data)

    def set_temperature(self, temp: int):
        self.connect()

        try:
            self.s.sendall(bytes('set set_domestic_temperature ' + str(temp) + '\n', 'UTF-8'))
            time.sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()

        if request == f"#? set 'set_domestic_temperature' to {temp} ({hex(temp)})\n":
            return json.loads('{"success": true}')
        else:
            return json.loads('{"success": false}')

    def start_recirculation(self, duration: int):
        self.connect()

        try:
            self.s.sendall(bytes('set recirculation_duration ' + str(duration) + '\n', 'UTF-8'))
            self.s.recv(BUFF_SIZE).decode('UTF-8')
            time.sleep(1)
            self.s.sendall(bytes('set set_recirculation_enabled true' + '\n', 'UTF-8'))
            time.sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')
        LOGGER.debug(request)

        self.s.close()

        if request == "#? set 'set_recirculation_enabled' to true\n":
            return json.loads('{"success": true}')
        else:
            return json.loads('{"success": false}')

    def stop_recirculation(self):
        self.connect()

        try:
            self.s.sendall(bytes('set set_recirculation_enabled false' + '\n', 'UTF-8'))
            time.sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()

        if request == "#? set 'set_recirculation_enabled' to false\n":
            return json.loads('{"success": true}')
        else:
            return json.loads('{"success": false}')

    def vacation_mode_on(self):
        self.connect()

        try:
            self.s.sendall(bytes('set schedule_holiday true' + '\n', 'UTF-8'))
            time.sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()

        if request == "#? set 'schedule_holiday' to true\n":
            return json.loads('{"success": true}')
        else:
            return json.loads('{"success": false}')

    def vacation_mode_off(self):
        self.connect()

        try:
            self.s.sendall(bytes('set schedule_holiday false' + '\n', 'UTF-8'))
            time.sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()

        if request == "#? set 'schedule_holiday' to false\n":
            return json.loads('{"success": true}')
        else:
            return json.loads('{"success": false}')

    def turn_off(self):
        self.connect()

        try:
            self.s.sendall(bytes('set set_operation_enabled false' + '\n', 'UTF-8'))
            time.sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()

        if request == "#? set 'set_operation_enabled' to false\n":
            return json.loads('{"success": true}')
        else:
            return json.loads('{"success": false}')

    def turn_on(self):
        self.connect()

        try:
            self.s.sendall(bytes('set set_operation_enabled true' + '\n', 'UTF-8'))
            time.sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()

        if request == "#? set 'set_operation_enabled' to true\n":
            return json.loads('{"success": true}')
        else:
            return json.loads('{"success": false}')

    def do_maintenance_retrieval(self):
        self.connect()

        try:
            self.s.sendall(bytes('set do_maintenance_retrieval true' + '\n', 'UTF-8'))
            time.sleep(1) #sleep here to make sure our send has time to get there
        except socket.error as msg:
            print("Socket Error: %s" % msg)

        request = self.s.recv(BUFF_SIZE).decode('UTF-8')

        self.s.close()

        if request == "#? set \'do_maintenance_retrieval\' to true\n":
            return json.loads('{"success": true}')
        else:
            return json.loads('{"success": false}')