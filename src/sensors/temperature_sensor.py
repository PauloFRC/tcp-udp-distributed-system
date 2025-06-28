import random
import time
from typing import Dict
from proto.sensor_data_pb2 import SensorReading, SensorType
from sensors.tcp_sensor_client import TcpSensorClient

# Sensor de temperatura TCP
class TemperatureSensorClient(TcpSensorClient):
    def __init__(self, sensor_id: str, location: str, interval: int = 10, host: str = 'localhost', port: int = 6789):
        super().__init__(sensor_id, location, host, port, interval)

    def _generate_reading(self) -> SensorReading:
        reading = SensorReading()
        reading.sensor_id = self.sensor_id
        reading.location = self.location
        reading.sensor_type = SensorType.TEMPERATURE
        reading.value = round(random.uniform(18.0, 25.0), 2)
        reading.unit = "°C"
        reading.timestamp = int(time.time())
        return reading

    def _monitor_loop(self):
        while self.running:
            reading = self._generate_reading()
            self.send_sensor_reading(reading)
            time.sleep(self.interval)
