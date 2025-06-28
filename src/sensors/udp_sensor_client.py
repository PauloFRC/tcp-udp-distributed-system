import socket
from proto.sensor_data_pb2 import SensorReading, SensorType
from sensors.sensor_client import SensorClient

class UdpSensorClient(SensorClient):
    def __init__(self, sensor_id: str, location: str, multicast_group='228.0.0.8', multicast_port=6791):
        super().__init__(sensor_id, location)
        self.multicast_group = multicast_group
        self.multicast_port = multicast_port
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)

    def send_sensor_reading(self, reading: SensorReading):
        try:
            data = reading.SerializeToString()
            self.sock.sendto(data, (self.multicast_group, self.multicast_port))
            print(f"📤 [{self.sensor_id}] enviou via UDP: {reading.value} {reading.unit}")
        except Exception as e:
            print(f"⚠️  [{self.sensor_id}] Erro no envio UDP: {e}")

    def stop_monitoring(self):
        super().stop_monitoring()
        self.sock.close()

    def _monitor_loop(self):
        pass
