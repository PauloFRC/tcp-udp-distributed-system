import socket
import struct
import threading
import time

from jwt import DecodeError
from proto.sensor_data_pb2 import Response, DeviceCommand, GatewayAnnouncement
from proto.sensor_data_pb2 import SensorReading
from devices.device import Device

class DeviceClient(Device):
    def __init__(self, sensor_id: str, location: str, interval=30, discovery_group='228.0.0.8', discovery_port=6791):
        self.sensor_id = sensor_id
        self.location = location
        self.interval = interval
        self.discovery_group = discovery_group
        self.discovery_port = discovery_port

        self.tcp_gateway_address = None
        self.udp_gateway_address = None
        self.command_gateway_address = None

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self._thread_poll_commands = threading.Thread(target=self.run_poll_for_commands)
        self._thread_poll_commands.daemon = True

        self.running = False

    def discover_gateway(self):
        # Procura um gateway para se conectar
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_sock.bind(('', self.discovery_port))
        
        mreq = struct.pack("4sl", socket.inet_aton(self.discovery_group), socket.INADDR_ANY)
        listen_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        listen_sock.settimeout(1.0)

        print(f"🔎 [{self.sensor_id}] Procurando gateway em {self.discovery_group}:{self.discovery_port}...")

        while self.running and self.tcp_gateway_address is None:
            try:
                data, _ = listen_sock.recvfrom(1024)
                announcement = GatewayAnnouncement()
                announcement.ParseFromString(data)
                
                self.tcp_gateway_address = (announcement.gateway_ip, announcement.tcp_port)
                self.udp_gateway_address = (announcement.gateway_ip, announcement.udp_port)
                self.command_gateway_address = (announcement.gateway_ip, announcement.command_port)

                print(f"✅ [{self.sensor_id}] Gateway encontrado em {self.tcp_gateway_address}")
            except socket.timeout:
                continue
            except DecodeError:
                print(f"⚠️  [{self.sensor_id}] Recebido pacote de descoberta malformado. Ignorando.")
                continue
            except Exception as e:
                if self.running:
                    print(f"⚠️  [{self.sensor_id}] Erro durante a descoberta: {e}")
                    time.sleep(5)
        
        listen_sock.close()

    def run_poll_for_commands(self):
        while True:
            try:
                # A cada 5 seg espera procura por um comando
                time.sleep(5)

                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect(self.command_gateway_address)

                    sensor_id_bytes = self.sensor_id.encode('utf-8')
                    msg = struct.pack('!I', len(sensor_id_bytes)) + sensor_id_bytes
                    s.sendall(msg)

                    len_data = s.recv(4)
                    if not len_data:
                        continue
                    
                    msg_len = struct.unpack('!I', len_data)[0]

                    if msg_len == 0:
                        continue

                    command_data = s.recv(msg_len)
                    command = DeviceCommand()
                    command.ParseFromString(command_data)
                    
                    self.handle_command(command)

            except ConnectionRefusedError:
                print(f"⚠️ Falha ao se conectar ao servidor {self.command_gateway_address[0]}:{self.command_gateway_address[1]}. O gateway está offline?")
            except Exception as e:
                print(f"Erro encontrado ao procurar por comandos: {e}")

    def _generate_reading(self) -> SensorReading:
        pass

    def handle_command(self, command: DeviceCommand):
        command_str = command.command
        print(f"📥 [{self.sensor_id}] Recebeu o comando: '{command_str}'")

        # por padrão todo dispositivo tem o comportamento de enviar leitura se receber comando de envio
        if command_str == "send":
            self.send_tcp_data()

    def send_tcp_data(self):
        reading = self._generate_reading()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(self.tcp_gateway_address)
                
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

    def send_udp_data(self):
        reading = self._generate_reading()
        if not self.udp_gateway_address:
            print(f"⚠️  [{self.sensor_id}] Endereço UDP do gateway não encontrado. Não é possível enviar dados.")
            return
        try:
            data = reading.SerializeToString()
            self.sock.sendto(data, self.udp_gateway_address)
            print(f"📤 [{self.sensor_id}] enviou via UDP para {self.udp_gateway_address}: {reading.value} {reading.unit}")
        except Exception as e:
            print(f"⚠️  [{self.sensor_id}] Erro no envio UDP: {e}")
            self.udp_gateway_address = None 
    
    def _monitor_loop(self):
        self.discover_gateway()

        # inicializa thread de receber comandos
        self._thread_poll_commands.start()

