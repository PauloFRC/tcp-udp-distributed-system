import threading
from devices.sensor_client import Device

class DeviceManager:
    def __init__(self):
        self.sensors = []
        self.threads = []
    
    def add_sensor(self, sensor: Device):
        self.sensors.append(sensor)
    
    def start_all_sensors(self):
        print("🎯 Iniciando todos os sensores...")
        
        for sensor in self.sensors:
            thread = threading.Thread(target=sensor.start)
            thread.daemon = True
            thread.start()
            self.threads.append(thread)
        
        print(f"✅ Iniciou {len(self.sensors)} sensores")
    
    def stop_all_sensors(self):
        print("🛑 Parando todos os sensores...")
        for sensor in self.sensors:
            sensor.stop()