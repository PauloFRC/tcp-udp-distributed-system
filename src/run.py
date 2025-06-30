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
        
        manager.add_sensor(TemperatureSensorClient("TCP-TEMP-01", "Cocó", interval=25))
        manager.add_sensor(HumiditySensorClient("TCP-HUM-01", "Cocó", interval=20))
        #manager.add_sensor(TemperatureSensorClient("TEMP-002", "Iracema", interval=35))
        #manager.add_sensor(HumiditySensorClient("HUM-002", "Iracema", interval=45))

        manager.add_sensor(AlarmSensor("UDP-ALARM-01", "Banco de Brasil"))
        manager.add_sensor(AlarmSensor("UDP-ALARM-02", "Múseu de Arte"))

        manager.add_sensor(Semaphore("TCP-SEM-01", "Rua Maria com rua João", interval=40))
        manager.add_sensor(Semaphore("TCP-SEM-02", "Rua Leonardo com rua Pedro", interval=60))
        
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
