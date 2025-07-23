import threading
import time
from proto.sensor_data_pb2 import DeviceType, DeviceCommand, CommandResponse
from proto.sensor_data_pb2 import SensorReading
from devices.default_device import DeviceClient

class Semaphore(DeviceClient):
    def __init__(self, sensor_id: str, location: str, interval=30, discovery_group='228.0.0.8', discovery_port=6791):
        super().__init__(sensor_id, location, interval, discovery_group, discovery_port)

        self.state = "verde"
        self.state_lock = threading.Lock()
        self.semaphore_color_map = {"vermelho":0, "amarelo":1, "verde":2}
        self.intervals = {"vermelho": self.interval, "verde":self.interval, "amarelo":30}

        self._thread_semaphore = threading.Thread(target=self._semaphore_loop, daemon=True)
    
    def _generate_reading(self) -> SensorReading:
        reading = SensorReading()
        reading.sensor_id = self.sensor_id
        reading.location = self.location
        reading.sensor_type = DeviceType.SEMAPHORE
        reading.value = self.semaphore_color_map[self.state]
        reading.timestamp = int(time.time())
        return reading
    
    def _next_state(self):
        match self.state:
            case "vermelho":
                self.state = "amarelo"
            case "amarelo":
                self.state = "verde"
            case "verde": 
                self.state = "vermelho"
    
    def handle_command(self, command: DeviceCommand):
        super().handle_command(command)

    def SetSemaphoreLight(self, request, context):
        with self.state_lock:
            self.state = request.state
        print(f"🚦 [{self.sensor_id}] Semáforo atualizado:", self.state)
        return CommandResponse(success=True, message=f"Luz do semáforo alterada para {request.state}")
    
    def _semaphore_loop(self):
        while self.running:
            with self.state_lock:
                self._next_state()
                sleep_time = self.intervals[self.state]
            time.sleep(sleep_time)

    def _monitor_loop(self):
        super()._monitor_loop()
        # inicializa thread de atualizar o semáforo
        self._thread_semaphore.start()
        while self.running:
            self.send_udp_data()
            time.sleep(self.interval)    