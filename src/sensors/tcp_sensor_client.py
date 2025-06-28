from abc import abstractmethod
import socket
import struct
import time
from typing import Dict
from proto.sensor_data_pb2 import Response
from proto.sensor_data_pb2 import SensorType
from proto.sensor_data_pb2 import SensorReading
from sensors.sensor_client import SensorClient


class TcpSensorClient(SensorClient):
    def __init__(self, sensor_id: str, location: str, host='localhost', port=6789, interval=30):
        self.sensor_id = sensor_id
        self.location = location
        self.host = host
        self.port = port
        self.interval = interval
        self.running = False
    
    def send_sensor_reading(self, reading: SensorReading):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
                
                # Serializa mensagem
                data = reading.SerializeToString()
                msg_length = struct.pack('!I', len(data))
                s.sendall(msg_length + data)
                
                response_len_data = s.recv(4)
                if not response_len_data:
                    print(f"⚠️  [{self.sensor_id}] Nenhuma resposta recebida do gateway.")
                    return

                response_length = struct.unpack('!I', response_len_data)[0]

                response_data = s.recv(response_length)
                response = Response()
                response.ParseFromString(response_data)

                if response.success:
                    print(f"📤 [{self.sensor_id}] enviou: {reading.value} {reading.unit}. Gateway respondeu: '{response.message}'")
                else:
                    print(f"⚠️  [{self.sensor_id}] Gateway retornou um erro: '{response.message}'")

        except ConnectionRefusedError:
            print(f"⚠️  [{self.sensor_id}] Conexão TCP recusada. O gateway está offline?")
        except Exception as e:
            print(f"⚠️  [{self.sensor_id}] Erro no envio TCP: {e}")
    
    def _monitor_loop(self):
        pass

