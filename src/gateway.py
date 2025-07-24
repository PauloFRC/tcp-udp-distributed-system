from collections import defaultdict
import socket
import threading
import time
import datetime
import struct
import pika
from proto.sensor_data_pb2 import SensorReading, Response, DeviceType, GatewayAnnouncement, AppRequest, GatewayResponse

import grpc
from proto import sensor_data_pb2
from proto import sensor_data_pb2_grpc

class Gateway:
    def __init__(self, host='0.0.0.0', tcp_port=6789, udp_port=6790, discovery_group='228.0.0.8', 
                 discovery_port=6791, status_query_port=8082, rabbitmq_host='localhost', rabbitmq_port=5672):
        self.host = host
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.discovery_group = discovery_group
        self.discovery_port = discovery_port
        self.status_query_port = status_query_port

        self.devices = {}
        self.devices_lock = threading.Lock()

        self.running = False
        self.sensor_data = {}
        self.sensor_data_lock = threading.Lock()

        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.connection = None
        self.channel = None
        self.exchange_name = 'sensor_data_exchange'

        self.gateway_ip = self._get_local_ip()

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
            result = self.channel.queue_declare(queue='', exclusive=True)
            self.queue_name = result.method.queue
            self.channel.queue_bind(exchange=self.exchange_name, queue=self.queue_name)
            print(f"✅ Conectado ao RabbitMQ em {self.rabbitmq_host}:{self.rabbitmq_port}")
        except pika.exceptions.AMQPConnectionError as e:
            print(f"❌ Erro ao conectar ao RabbitMQ: {e}")
            self.connection = None
            self.channel = None

    def listen_rabbitmq(self):
        if not self.channel:
            print("⚠️ Não conectado ao RabbitMQ. Tentando reconectar...")
            self.connect_rabbitmq()
            if not self.channel:
                return

        print(f"🌐 Gateway (RabbitMQ) ouvindo na fila '{self.queue_name}' para dados de sensores")
        try:
            self.channel.basic_consume(queue=self.queue_name, on_message_callback=self._rabbitmq_callback, auto_ack=True)
            self.channel.start_consuming()
        except Exception as e:
            print(f"❌ Erro ao consumir mensagens do RabbitMQ: {e}")
            if self.connection:
                self.connection.close()
            self.connection = None
            self.channel = None

    def _rabbitmq_callback(self, ch, method, properties, body):
        # The body contains the serialized SensorReading protobuf message
        self.handle_sensor_data(body, addr=("RabbitMQ", self.rabbitmq_port), protocol="RabbitMQ")
    
    def send_command_to_device(self, device_id, command_str, params=None):
        with self.devices_lock:
            device_info = self.devices.get(device_id)

        if not device_info:
            print(f"⚠️ Dispositivo '{device_id}' não encontrado.")
            return None

        try:
            channel = grpc.insecure_channel(f"{device_info['address']}:{device_info['grpc_port']}")
            stub = sensor_data_pb2_grpc.DeviceControlStub(channel)
            if command_str == "send_tcp_data":
                request = sensor_data_pb2.Empty()
                response = stub.SendTcpData(request)
            #elif command_str in ["vermelho", "amarelo", "verde"]:
            #    request = sensor_data_pb2.SemaphoreLightStateRequest(state=command_str)
            #    response = stub.SetSemaphoreLight(request)
            else:
                request = sensor_data_pb2.CommandRequest(command=command_str, params=params)
                response = stub.SendCommand(request)
            print(f"✅ Comando '{command_str}' enviado para '{device_id}'. Resposta: {response.message}")
            return response
        except grpc.RpcError as e:
            print(f"⚠️ Erro ao enviar comando para '{device_id}': {e}")
            return None

    def handle_tcp_client(self, conn, addr):
        response = None
        try:
            # Recebe comprimento da mensagem (4 bytes)
            length_data = conn.recv(4)
            if not length_data:
                return
            
            msg_length = struct.unpack('!I', length_data)[0]
            
            # Recebe mensagem
            data = b''
            while len(data) < msg_length:
                chunk = conn.recv(msg_length - len(data))
                if not chunk:
                    break
                data += chunk
            
            if data:
                try:
                    reading = SensorReading()
                    reading.ParseFromString(data)
                    
                    with self.devices_lock:
                        self.devices[reading.sensor_id] = {
                            "address": addr[0],
                            "grpc_port": int(reading.metadata.get("grpc_port", 50051)) 
                        }

                    reading.metadata["address"] = addr[0]
                    self.sensor_data[reading.sensor_id] = reading
                    
                    self.display_sensor_reading(reading, addr)
                    
                    response = Response()
                    response.success = True
                    response.message = f"Dados recebidos do sensor {reading.sensor_id}"
                    response.timestamp = int(time.time())
                    
                except Exception as e:
                    print(f"Erro ao fazer parsing dos dados do sensor: {e}")
                    response = Response()
                    response.success = False
                    response.message = f"Erro: {str(e)}"
                    response.timestamp = int(time.time())
                    
                    response_data = response.SerializeToString()
                    response_length = struct.pack('!I', len(response_data))
                    conn.sendall(response_length + response_data)

                if response:
                    try:
                        response_data = response.SerializeToString()
                        response_length = struct.pack('!I', len(response_data))
                        conn.sendall(response_length + response_data)
                    except Exception as e:
                        print(f"Erro ao enviar resposta ao endereço {addr}: {e}")
        
        except Exception as e:
            print(f"Erro ao lidar com cliente {addr}: {e}")
        finally:
            conn.close()

    def handle_sensor_data(self, data, addr, protocol="UDP"):
        try:
            reading = SensorReading()
            reading.ParseFromString(data)

            with self.devices_lock:
                device_address = addr[0] if protocol != "RabbitMQ" else reading.metadata.get("device_ip", "unknown")
                self.devices[reading.sensor_id] = {
                    "address": device_address,
                    "grpc_port": int(reading.metadata.get("grpc_port", 50051))
                }

            with self.sensor_data_lock:
                self.sensor_data[reading.sensor_id] = reading

            self.display_sensor_reading(reading, addr, protocol)

        except Exception as e:
            print("⚠️ Parsing falhou")
            print(f"📊 Bytes recebidos: ({len(data)} bytes). Exception: {e}")
            print(f"  📋 Dados: {data.hex()}")
            print("-" * 60)
    
    def display_sensor_reading(self, reading, addr, protocol="TCP"):
        sensor_type_name = DeviceType.Name(reading.sensor_type)
        
        print(f"📊 Recebeu dado de {sensor_type_name} do endereço {addr} via {protocol}")
        print(f"  🆔 Sensor ID: {reading.sensor_id}")
        print(f"  📍 Localização: {reading.location}")
        print(f"  📈 Valor: {reading.value} {reading.unit}")
        print(f"  🕐 Timestamp: {datetime.datetime.fromtimestamp(reading.timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
        
        if reading.metadata:
            print(f"  📋 Metadata:")
            for key, value in reading.metadata.items():
                print(f"     {key}: {value}")
        
        print("-" * 60)

    def listen_tcp(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.tcp_port))
        s.listen(10)

        print(f"🌐 Gateway (TCP) ouvindo em {self.host}:{self.tcp_port}")

        while self.running:
            conn, addr = s.accept()
            print(f"🔗 Nova conexão de endereço {addr}")

            client_thread = threading.Thread(target=self.handle_tcp_client, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()

 

    def broadcast_discovery(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)

        announcement = GatewayAnnouncement(
            gateway_ip=self.gateway_ip,
            tcp_port=self.tcp_port,
            udp_port=self.udp_port,
            rabbitmq_host=self.rabbitmq_host,
            rabbitmq_port=self.rabbitmq_port
        )
        message = announcement.SerializeToString()

        print(f"📢 Iniciando anúncios de descoberta para {self.discovery_group}:{self.discovery_port}")
        while self.running:
            sock.sendto(message, (self.discovery_group, self.discovery_port))
            time.sleep(10) # Anuncia a cada 10s
    
    def start(self):
        self.running = True
        print("🚀 Iniciando Gateway...")
        print(f"   IP do Gateway para anúncios: {self.gateway_ip}")

        tcp_thread = threading.Thread(target=self.listen_tcp)
        tcp_thread.daemon = True
        tcp_thread.start()



        rabbitmq_thread = threading.Thread(target=self.listen_rabbitmq)
        rabbitmq_thread.daemon = True
        rabbitmq_thread.start()

        discovery_thread = threading.Thread(target=self.broadcast_discovery)
        discovery_thread.daemon = True
        discovery_thread.start()

        print("=" * 60)

        '''
        try:
            while self.running:
                pass
        except KeyboardInterrupt:
            print("\n🛑 Desligando gateway")
            self.running = False
            '''
    
    def get_sensor_status(self):
        with self.sensor_data_lock:
            return dict(self.sensor_data)
