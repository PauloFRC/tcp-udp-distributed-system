import threading
import time
from proto.sensor_data_pb2 import DeviceType
from proto.sensor_data_pb2 import SensorReading
from devices.tcp_sensor_client import TcpDeviceClient

class Semaphore(TcpDeviceClient):
    def __init__(self, sensor_id: str, location: str, 
                 host: str = 'localhost', port: int = 6789, command_poll_port: int = 8081, interval: int = 10):
        super().__init__(sensor_id, location, host, port, command_poll_port, interval)
        self.state = "vermelho" # (vermelho, amarelo, verde)
        self.intervals = {"vermelho": self.interval, "verde":self.interval, "amarelo":4}
    
    def _generate_reading(self) -> SensorReading:
        reading = SensorReading()
        reading.sensor_id = self.sensor_id
        reading.location = self.location
        reading.sensor_type = DeviceType.SEMAPHORE
        reading.value = 0 # mudar
        reading.timestamp = int(time.time())
        reading.metadata['command_poll_port'] = str(self.command_poll_port)
        return reading
    
    def _update_state(self):
        match self.state:
            case "vermelho":
                self.state = "amarelo"
            case "amarelo":
                self.state = "verde"
            case "verde": 
                self.state = "vermelho"
    
    def handle_command(self, command):
        print("SEMAFORO REALIZANDO COMANDO")
        super().handle_command(command)
        command_str = command.command
        # atualiza a cor do semáforo se for passada um comando para mudar de cor
        if command_str in ("vermelho", "amarelo", "verde"):
            self.state = command_str
        print("ESTADO SEMAFORO APOS REALIZAR COMANDO:", self.state)

    def _monitor_loop(self):
        self._thread_poll_commands.start()
        while self.running:
            time.sleep(self.intervals[self.state])
            self._update_state()
            self.send_data_gateway()
            print("O semáforo mudou para estado:", self.state)
    