import socket
import struct
import threading
import time
import pika

#from jwt import DecodeError
from jwt.exceptions import JWSDecodeError
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
        return sensor_data_pb2.CommandResponse(success=True, message="Comando recebido")

    def SendTcpData(self, request, context):
        self.device_client.send_tcp_data()
        return sensor_data_pb2.CommandResponse(success=True, message="Dados TCP enviados")

class DeviceClient(Device):
    def __init__(self, sensor_id: str, location: str, interval=30, discovery_group='228.0.0.8', discovery_port=6791, grpc_port=0, rabbitmq_host='localhost', rabbitmq_port=5672):
        super().__init__(sensor_id, location)
        self.interval = interval
        self.discovery_group = discovery_group
        self.discovery_port = discovery_port
        self.grpc_port = grpc_port

        self.tcp_gateway_address = None
        self.udp_gateway_address = None

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.connection = None
        self.channel = None
        self.exchange_name = 'sensor_data_exchange'

        self.running = False
        self.grpc_server_started = threading.Event()

    def _get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def connect_rabbitmq(self):
        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.rabbitmq_host, port=self.rabbitmq_port))
            self.channel = self.connection.channel()
            self.channel.exchange_declare(exchange=self.exchange_name, exchange_type='fanout')
            print(f"✅ [{self.sensor_id}] Conectado ao RabbitMQ em {self.rabbitmq_host}:{self.rabbitmq_port}")
        except pika.exceptions.AMQPConnectionError as e:
            print(f"❌ [{self.sensor_id}] Erro ao conectar ao RabbitMQ: {e}")
            self.connection = None
            self.channel = None

    def publish_rabbitmq(self, data: bytes):
        if not self.channel:
            print(f"⚠️ [{self.sensor_id}] Não conectado ao RabbitMQ. Tentando reconectar...")
            self.connect_rabbitmq()
            if not self.channel:
                print(f"❌ [{self.sensor_id}] Falha ao reconectar ao RabbitMQ. Não foi possível publicar dados.")
                return
        try:
            self.channel.basic_publish(exchange=self.exchange_name, routing_key='', body=data)
            print(f"📤 [{self.sensor_id}] Publicou dados no RabbitMQ.")
        except Exception as e:
            print(f"❌ [{self.sensor_id}] Erro ao publicar dados no RabbitMQ: {e}")
            if self.connection:
                self.connection.close()
            self.connection = None
            self.channel = None

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
            except JWSDecodeError:
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

    def handle_command(self, command: str):
        print(f"📥 [{self.sensor_id}] Recebeu o comando: '{command}'")

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

