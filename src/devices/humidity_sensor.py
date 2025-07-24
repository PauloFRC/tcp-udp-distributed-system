import random
import time
from typing import Dict
from proto.sensor_data_pb2 import SensorReading, DeviceType
from devices.default_device import DeviceClient

# Sensor de umidade TCP
class HumiditySensorClient(DeviceClient):
    def __init__(self, sensor_id: str, location: str, interval=30, discovery_group='228.0.0.8', discovery_port=6791):
        super().__init__(sensor_id, location, interval, discovery_group, discovery_port)

    def _generate_reading(self) -> SensorReading:
        reading = SensorReading()
        reading.sensor_id = self.sensor_id
        reading.location = self.location
        reading.sensor_type = DeviceType.HUMIDITY
        reading.value = round(random.uniform(40.0, 60.0), 2)
        reading.unit = "%"
        reading.timestamp = int(time.time())
        reading.metadata["device_ip"] = self._get_local_ip()
        return reading

    def _monitor_loop(self):
        super()._monitor_loop()
        self.connect_rabbitmq()
        self.grpc_server_started.wait()
        while self.running:
            reading = self._generate_reading()
            reading.metadata["grpc_port"] = str(self.grpc_port)
            self.publish_rabbitmq(reading.SerializeToString())
            time.sleep(self.interval)
            