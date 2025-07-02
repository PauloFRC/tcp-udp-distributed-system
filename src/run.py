import time
from gateway import Gateway
from sensor_manager import DeviceManager
from devices.humidity_sensor import HumiditySensorClient
from devices.temperature_sensor import TemperatureSensorClient
from devices.alarm_sensor import AlarmSensor
from devices.semaphore import Semaphore

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "gateway":
        # Roda gateway
        gateway = Gateway()
        gateway.start()
    
    elif len(sys.argv) > 1 and sys.argv[1] == "multi":
        # Roda múltiplos sensores
        manager = DeviceManager()
        
        # manager.add_sensor(TemperatureSensorClient("TEMP-01", "Cocó", interval=25))
        # manager.add_sensor(HumiditySensorClient("HUM-01", "Cocó", interval=25))
        # manager.add_sensor(TemperatureSensorClient("TEMP-02", "Iracema", interval=30))
        # manager.add_sensor(HumiditySensorClient("HUM-002", "Iracema", interval=30))
        # manager.add_sensor(TemperatureSensorClient("TEMP-03", "Aldeota", interval=35))
        # manager.add_sensor(HumiditySensorClient("HUM-003", "Aldeota", interval=35))

        manager.add_sensor(AlarmSensor("ALARM-01", "Banco de Brasil", interval=10))
        manager.add_sensor(AlarmSensor("ALARM-02", "Múseu de Arte", interval=10))

        #manager.add_sensor(Semaphore("SEM-01", "Rua Maria com rua João", interval=40))
        #manager.add_sensor(Semaphore("SEM-02", "Rua Leonardo com rua Pedro", interval=5))
        
        try:
            manager.start_all_sensors()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            manager.stop_all_sensors()
            print("\n🏁 Todos os sensores parados.")
    
    else:
        # Roda um único sensor
        sensor = TemperatureSensorClient("TEMP-SENSOR-01", "Aldeota", interval=30)
        
        try:
            sensor.start()
        except KeyboardInterrupt:
            sensor.stop()
            print("\n🏁 Sensor de temperatura parou.")
