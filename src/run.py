import time
from gateway import Gateway
from sensor_manager import SensorManager
from sensors.humidity_sensor import HumiditySensorClient
from sensors.temperature_sensor import TemperatureSensorClient
from sensors.movement_sensor import MovementSensor
from sensors.udp_sensor_client import UdpSensorClient


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "gateway":
        # Roda gateway
        gateway = Gateway()
        gateway.start()
    
    elif len(sys.argv) > 1 and sys.argv[1] == "multi":
        # Roda múltiplos sensores
        manager = SensorManager()
        
        manager.add_sensor(TemperatureSensorClient("TEMP-001", "Cocó", interval=25))
        manager.add_sensor(HumiditySensorClient("HUM-001", "Cocó", interval=20))
        manager.add_sensor(TemperatureSensorClient("TEMP-002", "Iracema", interval=35))
        manager.add_sensor(HumiditySensorClient("HUM-002", "Iracema", interval=45))

        manager.add_sensor(MovementSensor("UDP-MOV-01", "Corredor Principal"))
        manager.add_sensor(MovementSensor("UDP-MOV-02", "Porta dos Fundos"))
        
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
            sensor.start_monitoring()
        except KeyboardInterrupt:
            sensor.stop_monitoring()
            print("\n🏁 Sensor de temperatura parou.")
