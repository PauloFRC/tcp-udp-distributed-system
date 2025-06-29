import time
import random
from devices.udp_sensor_client import UdpSensorClient
from proto.sensor_data_pb2 import SensorReading, DeviceType

# Sensor de movimento UDP
class AlarmSensor(UdpSensorClient):
    def __init__(self, sensor_id: str, location: str, multicast_group='228.0.0.8', multicast_port=6791):
        super().__init__(sensor_id, location, multicast_group, multicast_port)

    def _generate_reading(self) -> SensorReading:
        reading = SensorReading()
        reading.sensor_id = self.sensor_id
        reading.location = self.location
        reading.sensor_type = DeviceType.ALARM
        reading.value = 1.0 # movimento detectado
        reading.unit = "detected"
        reading.timestamp = int(time.time())
        reading.metadata["trigger"] = "passive_infrared"
        return reading

    def _monitor_loop(self):
        super()._monitor_loop()
        while self.running:
            # Simula espera para detectar movimento
            time_to_wait = random.uniform(10, 30)
            time.sleep(time_to_wait)

            if self.running:
                print(f"🏃 [{self.sensor_id}] Alarme detectado!")
                reading = self._generate_reading()
                self.send_sensor_reading(reading)

