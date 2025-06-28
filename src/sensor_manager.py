import threading
from sensors.sensor_client import SensorClient

class SensorManager:
    def __init__(self):
        self.sensors = []
        self.threads = []
    
    def add_sensor(self, sensor: SensorClient):
        self.sensors.append(sensor)
    
    def start_all_sensors(self):
        print("🎯 Iniciando todos os sensores...")
        
        for sensor in self.sensors:
            thread = threading.Thread(target=sensor.start_monitoring)
            thread.daemon = True
            thread.start()
            self.threads.append(thread)
        
        print(f"✅ Iniciou {len(self.sensors)} sensoress")
    
    def stop_all_sensors(self):
        print("🛑 Parando todos os sensores...")
        for sensor in self.sensors:
            sensor.stop_monitoring()