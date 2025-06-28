from abc import ABC, abstractmethod
import threading

# Define interfaco dos sensores
class SensorClient(ABC):
    def __init__(self, sensor_id: str, location: str):
        self.sensor_id = sensor_id
        self.location = location
        self.running = False
        self.thread = None

    def start_monitoring(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop)
            self.thread.daemon = True
            self.thread.start()
            print(f"🚀 [{self.sensor_id}] Iniciando monitoramento...")

    def stop_monitoring(self):
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join()
            print(f"🛑 [{self.sensor_id}] Parando monitoramento...")

    @abstractmethod
    def _monitor_loop(self):
        pass
    