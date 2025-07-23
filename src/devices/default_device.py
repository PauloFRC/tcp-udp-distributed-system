import socket
import struct
import threading
import time

from jwt import DecodeError
from proto.sensor_data_pb2 import Response, DeviceCommand, GatewayAnnouncement
from proto.sensor_data_pb2 import SensorReading
from devices.device import Device

import grpc
from concurrent import futures
from proto import sensor_data_pb2
from proto import sensor_data_pb2_grpc

class DeviceControlServicer(sensor_data_pb2_grpc.DeviceControlServicer):
    def __init__(self, device_client):
        self.device_client = device_client

    def SendCommand(self, request, context):
        self.device_client.handle_command(request)
        return sensor_data_pb2.CommandResponse(success=True, message="Command received")

class DeviceClient(Device):
    def __init__(self, sensor_id: str, location: str, interval=30, discovery_group='228.0.0.8', discovery_port=6791, grpc_port=0):
        super().__init__(sensor_id, location)
        self.interval = interval
        self.discovery_group = discovery_group
        self.discovery_port = discovery_port
        self.grpc_port = grpc_port

        self.tcp_gateway_address = None
        self.udp_gateway_address = None

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.running = False
        self.grpc_server_started = threading.Event()

    def start_grpc_server(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        sensor_data_pb2_grpc.add_DeviceControlServicer_to_server(DeviceControlServicer(self), server)
        port = server.add_insecure_port(f'[::]:{self.grpc_port}')
        self.grpc_port = port
        server.start()
        print(f"🔑 [{self.sensor_id}] Servidor gRPC iniciado na porta {self.grpc_port}")
        self.grpc_server_started.set() # Sinaliza que o servidor iniciou
        server.wait_for_termination()

    def discover_gateway(self):
        self.grpc_server_started.wait()
        
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

    def _monitor_loop(self):
        grpc_thread = threading.Thread(target=self.start_grpc_server)
        grpc_thread.daemon = True
        grpc_thread.start()

        self.discover_gateway()

    def _generate_reading(self) -> SensorReading:
        pass

    def handle_command(self, command: DeviceCommand):
        command_str = command.command
        print(f"📥 [{self.sensor_id}] Recebeu o comando: '{command_str}'")

        # por padrão todo dispositivo tem o comportamento de enviar leitura se receber comando de envio
        if command_str == "send":
            self.send_tcp_data()

    def send_tcp_data(self):
        self.grpc_server_started.wait() 

        reading = self._generate_reading()
        reading.metadata["grpc_port"] = str(self.grpc_port)
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
        self.grpc_server_started.wait() 

        reading = self._generate_reading()
        reading.metadata["grpc_port"] = str(self.grpc_port)
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

