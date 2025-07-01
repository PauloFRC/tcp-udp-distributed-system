import random
import time
from proto.sensor_data_pb2 import SensorReading, DeviceType
from devices.default_device import DeviceClient

# Sensor de temperatura TCP
class TemperatureSensorClient(DeviceClient):
    def __init__(self, sensor_id: str, location: str, interval=30, discovery_group='228.0.0.8', discovery_port=6791):
        super().__init__(sensor_id, location, interval, discovery_group, discovery_port)

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
            self.send_udp_data()
            time.sleep(self.interval)
