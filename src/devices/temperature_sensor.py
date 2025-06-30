import random
import time
from proto.sensor_data_pb2 import SensorReading, DeviceType
from devices.tcp_sensor_client import TcpDeviceClient

# Sensor de temperatura TCP
class TemperatureSensorClient(TcpDeviceClient):
    def __init__(self, sensor_id: str, location: str, interval: int = 10, 
                 host: str = 'localhost', port: int = 6789, command_poll_port: int=8081):
        super().__init__(sensor_id, location, host, port, command_poll_port, interval)

    def _generate_reading(self) -> SensorReading:
        reading = SensorReading()
        reading.sensor_id = self.sensor_id
        reading.location = self.location
        reading.sensor_type = DeviceType.TEMPERATURE
        reading.value = round(random.uniform(18.0, 25.0), 2)
        reading.unit = "°C"
        reading.timestamp = int(time.time())
        return reading

    def _monitor_loop(self):
        super()._monitor_loop()
        while self.running:
            self.send_data_gateway()
            time.sleep(self.interval)
