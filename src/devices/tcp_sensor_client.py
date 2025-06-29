from abc import abstractmethod
import socket
import struct
import threading
import time
from proto.sensor_data_pb2 import Response, DeviceCommand
from proto.sensor_data_pb2 import SensorReading
from devices.sensor_client import Device

class TcpDeviceClient(Device):
    def __init__(self, sensor_id: str, location: str, host='0.0.0.0', port=6789, command_poll_port=8081, interval=30):
        self.sensor_id = sensor_id
        self.location = location
        self.host = host
        self.port = port
        self.command_poll_port = command_poll_port
        self.interval = interval

        #self._thread_send_data = threading.Thread(target=self.run_send_data)
        #self._thread_send_data.daemon = True

        # ADD a new thread for polling for commands
        self._thread_poll_commands = threading.Thread(target=self.run_poll_for_commands)
        self._thread_poll_commands.daemon = True

        self.running = False

    def run_poll_for_commands(self):
        """Periodically connects to the gateway to ask for commands."""
        while True:
            try:
                # Wait for 5 seconds before asking for a command
                time.sleep(5)

                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((self.host, self.command_poll_port))

                    # 1. Send our ID to the gateway so it knows who is asking
                    sensor_id_bytes = self.sensor_id.encode('utf-8')
                    msg = struct.pack('!I', len(sensor_id_bytes)) + sensor_id_bytes
                    s.sendall(msg)

                    # 2. Wait for a response
                    len_data = s.recv(4)
                    if not len_data:
                        continue
                    
                    msg_len = struct.unpack('!I', len_data)[0]

                    # If length is 0, gateway has no command for us
                    if msg_len == 0:
                        continue

                    # 3. If we get data, it's a command
                    command_data = s.recv(msg_len)
                    command = DeviceCommand()
                    command.ParseFromString(command_data)
                    
                    # Call the same handle_command method as before
                    self.handle_command(command)

            except ConnectionRefusedError:
                print(f"⚠️ Could not connect to command server at {self.host}:{self.command_poll_port}. Is the gateway running?")
            except Exception as e:
                print(f"An error occurred while polling for commands: {e}")

    def _generate_reading(self) -> SensorReading:
        pass

    def handle_command(self, command):
        print(f"📥 [{self.sensor_id}] Recebeu o comando: '{command}'")

    def send_data_gateway(self):
        reading = self._generate_reading()
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

