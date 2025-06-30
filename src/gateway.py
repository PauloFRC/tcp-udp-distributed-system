from collections import defaultdict
import socket
import threading
import time
import datetime
import struct
from proto.sensor_data_pb2 import SensorReading, Response, DeviceType, GatewayAnnouncement, DeviceCommand

class Gateway:
    def __init__(self, host='0.0.0.0', tcp_port=6789, udp_port=6790, discovery_group='228.0.0.8', 
                 discovery_port=6791, command_poll_port=8081):
        self.host = host
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.discovery_group = discovery_group
        self.discovery_port = discovery_port
        self.command_poll_port = command_poll_port

        self.command_devices = set()
        self.command_devices_lock = threading.Lock()

        self.command_queue = defaultdict(list)
        self.queue_lock = threading.Lock()
        self._thread_command_poll = threading.Thread(target=self.run_command_poll_server)
        self._thread_command_poll.daemon = True

        self.running = False
        self.sensor_data = {}

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
    
    def run_command_poll_server(self):
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind((self.host, self.command_poll_port))
        listen_socket.listen(5)
        print(f"👂 Fila de comandos ouvindo na porta {self.command_poll_port}")

        while True:
            conn, addr = listen_socket.accept()
            handler_thread = threading.Thread(
                target=self.handle_command_poll_connection, 
                args=(conn, addr)
            )
            handler_thread.start()
    
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
                    
                    reading.metadata["address"] = addr[0]
                    self.sensor_data[reading.sensor_id] = reading

                    with self.command_devices_lock:
                        self.command_devices.add(reading.sensor_id)
                    
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

    def handle_udp_data(self, data, addr, protocol="UDP"):
        try:
            reading = SensorReading()
            reading.ParseFromString(data)

            self.sensor_data[reading.sensor_id] = reading

            with self.command_devices_lock:
                self.command_devices.add(reading.sensor_id)

            self.display_sensor_reading(reading, addr, protocol)

        except Exception as e:
            print("⚠️ Parsing falhou")
            print(f"📊 Bytes recebidos: ({len(data)} bytes). Exception: {e}")
            print(f"  📋 Dados: {data.hex()}")
            print("-" * 60)

    def handle_command_poll_connection(self, conn, addr):
        try:
            msg_length_data = conn.recv(4)
            if not msg_length_data:
                return
            msg_length = struct.unpack('!I', msg_length_data)[0]
            device_id = conn.recv(msg_length).decode('utf-8')
            print(f"🔎 Dispositivo '{device_id}' está esperando por comando no endereço {addr}")

            command_to_send = None
            with self.queue_lock:
                if self.command_queue[device_id]:
                    command_to_send = self.command_queue[device_id].pop(0)
            
            if command_to_send:
                print(f"✅ Enviando comando '{command_to_send.command}' para dispositivo '{device_id}'")
                data = command_to_send.SerializeToString()
                msg = struct.pack('!I', len(data)) + data
                conn.sendall(msg)
            else:
                # Envia mensagem vazia
                conn.sendall(struct.pack('!I', 0))

        except Exception as e:
            print(f"Error handling command poll from {addr}: {e}")
        finally:
            conn.close()
    
    def queue_command_for_device(self, device_id, command_str):
        print(f"📬 Adicionando na fila comando '{command_str}' para o dispositivo '{device_id}'")
        
        command = DeviceCommand(
            target_id=device_id,
            command=command_str,
            timestamp=int(time.time())
        )
        with self.queue_lock:
            self.command_queue[device_id].append(command)

    def monitor_and_send_commands(self):
        while self.running:
            # a cada 10 segundos, verifica se algum comando deveria ser enviado a algum dispositivo
            time.sleep(10)
            
            with self.command_devices_lock:
                devices_to_check = list(self.command_devices)

            for sensor_id in devices_to_check:
                if sensor_id in self.sensor_data:
                    if self.sensor_data[sensor_id].sensor_type == DeviceType.SEMAPHORE:
                        self.queue_command_for_device(sensor_id, "verde") # muda semaforo pra verde
                    elif self.sensor_data[sensor_id].location == "Cocó":
                        self.queue_command_for_device(sensor_id, "send") # pede pros sensores no cocó enviarem dados
    
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

    def listen_udp(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.udp_port))

        print(f"🌐 Gateway (UDP) ouvindo em {self.host}:{self.udp_port} para dados de sensores")

        while self.running:
            data, addr = sock.recvfrom(1024)
            self.handle_udp_data(data, addr)

    def broadcast_discovery(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)

        announcement = GatewayAnnouncement(
            gateway_ip=self.gateway_ip,
            udp_port=self.udp_port
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

        udp_thread = threading.Thread(target=self.listen_udp)
        udp_thread.daemon = True
        udp_thread.start()

        discovery_thread = threading.Thread(target=self.broadcast_discovery)
        discovery_thread.daemon = True
        discovery_thread.start()

        self._thread_command_poll.start()
        
        thread_monitor_commands = threading.Thread(target=self.monitor_and_send_commands)
        thread_monitor_commands.daemon = True
        thread_monitor_commands.start()

        print("=" * 60)

        try:
            while self.running:
                pass
        except KeyboardInterrupt:
            print("\n🛑 Desligando gateway")
            self.running = False
    
    def get_sensor_status(self):
        return dict(self.sensor_data)
    
