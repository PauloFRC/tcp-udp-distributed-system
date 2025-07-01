import time
import random
from proto.sensor_data_pb2 import SensorReading, DeviceType
from devices.default_device import DeviceClient

class AlarmSensor(DeviceClient):
    def __init__(self, sensor_id: str, location: str, interval=30, discovery_group='228.0.0.8', discovery_port=6791):
        super().__init__(sensor_id, location, interval, discovery_group, discovery_port)

    def _generate_reading(self) -> SensorReading:
        reading = SensorReading()
        reading.sensor_id = self.sensor_id
        reading.location = self.location
        reading.sensor_type = DeviceType.ALARM
        reading.value = 1.0 # movimento detectado
        reading.unit = "%"
        reading.timestamp = int(time.time())
        return reading

    def _monitor_loop(self):
        super()._monitor_loop()
        while self.running:
            time_to_sleep = random.uniform(self.interval/2, self.interval*2)
            time.sleep(time_to_sleep)

            print(f"🚨 [{self.sensor_id}] Alarme detectado!")
            self.send_tcp_data()
