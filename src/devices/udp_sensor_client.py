import socket
import time
import struct

from jwt import DecodeError
from proto.sensor_data_pb2 import SensorReading, GatewayAnnouncement
from devices.sensor_client import Device

class UdpSensorClient(Device):
    def __init__(self, sensor_id: str, location: str, discovery_group='228.0.0.9', discovery_port=6792):
        super().__init__(sensor_id, location)
        self.discovery_group = discovery_group
        self.discovery_port = discovery_port
        self.gateway_address = None # Will be (ip, port)
        
        # Socket for sending data to the gateway (will be unicast)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def discover_gateway(self):
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_sock.bind(('', self.discovery_port))
        
        mreq = struct.pack("4sl", socket.inet_aton(self.discovery_group), socket.INADDR_ANY)
        listen_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        listen_sock.settimeout(1.0) # Set timeout to unblock loop

        print(f"🔎 [{self.sensor_id}] Procurando gateway em {self.discovery_group}:{self.discovery_port}...")

        while self.running and self.gateway_address is None:
            try:
                data, _ = listen_sock.recvfrom(1024)
                announcement = GatewayAnnouncement()
                announcement.ParseFromString(data)
                
                self.gateway_address = (announcement.gateway_ip, announcement.udp_port)
                print(f"✅ [{self.sensor_id}] Gateway encontrado em {self.gateway_address}")
            except socket.timeout:
                continue # No message received, just continue waiting
            except DecodeError:
                print(f"⚠️  [{self.sensor_id}] Recebido pacote de descoberta malformado. Ignorando.")
                continue
            except Exception as e:
                if self.running:
                    print(f"⚠️  [{self.sensor_id}] Erro durante a descoberta: {e}")
                    time.sleep(5)
        
        listen_sock.close()

    def send_sensor_reading(self, reading: SensorReading):
        """Sends a single sensor reading directly to the discovered gateway."""
        if not self.gateway_address:
            print(f"⚠️  [{self.sensor_id}] Gateway não encontrado. Não é possível enviar dados.")
            return

        try:
            data = reading.SerializeToString()
            self.sock.sendto(data, self.gateway_address)
            print(f"📤 [{self.sensor_id}] enviou via UDP para {self.gateway_address}: {reading.value} {reading.unit}")
        except Exception as e:
            print(f"⚠️  [{self.sensor_id}] Erro no envio UDP: {e}")
            self.gateway_address = None 

    def stop(self):
        super().stop()
        self.sock.close()

    def _monitor_loop(self):
        """The main loop for the sensor's operation."""
        # First, discover the gateway. This will block until the gateway is found.
        self.discover_gateway()
        
        # The subclass will implement the rest of the loop
        if not self.running: # If discovery was interrupted
            return
