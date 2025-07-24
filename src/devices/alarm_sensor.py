import time
import random
from proto.sensor_data_pb2 import SensorReading, DeviceType
from devices.default_device import DeviceClient

class AlarmSensor(DeviceClient):
    def __init__(self, sensor_id: str, location: str, interval=30, discovery_group='228.0.0.8', discovery_port=6791):
        super().__init__(sensor_id, location, interval, discovery_group, discovery_port)
        self.state = 0.0
        self.turn_off_alarm_interval = 10

    def _generate_reading(self) -> SensorReading:
        reading = SensorReading()
        reading.sensor_id = self.sensor_id
        reading.location = self.location
        reading.sensor_type = DeviceType.ALARM
        reading.value = self.state
        reading.unit = ""
        reading.timestamp = int(time.time())
        reading.metadata["device_ip"] = self._get_local_ip()
        return reading
    
    # Envia alarme e logo após desativa
    def ring_alarm(self):
        self.state = 1.0 # Movimento detectado
        reading = self._generate_reading()
        reading.metadata["grpc_port"] = str(self.grpc_port)
        self.publish_rabbitmq(reading.SerializeToString())

    def turn_off(self):
        self.state = 0.0 # Sem movimento
        reading = self._generate_reading()
        reading.metadata["grpc_port"] = str(self.grpc_port)
        self.publish_rabbitmq(reading.SerializeToString())

    def _monitor_loop(self):
        super()._monitor_loop()

        self.connect_rabbitmq()
        self.grpc_server_started.wait()
        while self.running:
            time.sleep(self.interval)
            print(f"🚨 [{self.sensor_id}] Alarme detectado!")
            self.ring_alarm()
            time.sleep(self.turn_off_alarm_interval)
            self.turn_off()
