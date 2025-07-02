use prost::Message;
use socket2::{Domain, Protocol, Socket, Type};
use std::net::{IpAddr, Ipv4Addr, SocketAddr, SocketAddrV4};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpStream, UdpSocket};
use tokio::sync::RwLock;
use tokio::time::{interval, sleep};
use std::future::Future;

use crate::sensor_data::{DeviceCommand, DeviceType, GatewayAnnouncement, Response, SensorReading};

pub struct DeviceClient {
    pub sensor_id: String,
    pub location: String,
    pub interval: Duration,
    discovery_group: Ipv4Addr,
    discovery_port: u16,
    pub gateway_addresses: Arc<RwLock<Option<GatewayAddresses>>>,
    running: Arc<RwLock<bool>>,
}

#[derive(Clone, Debug)]
pub struct GatewayAddresses {
    pub tcp: SocketAddr,
    pub udp: SocketAddr,
    pub command: SocketAddr,
}

impl DeviceClient {
    pub fn new(
        sensor_id: String,
        location: String,
        interval_secs: u64,
        discovery_group: Option<&str>,
        discovery_port: Option<u16>,
    ) -> Self {
        let discovery_group = discovery_group
            .and_then(|s| s.parse().ok())
            .unwrap_or_else(|| "228.0.0.8".parse().unwrap());
        
        Self {
            sensor_id,
            location,
            interval: Duration::from_secs(interval_secs),
            discovery_group,
            discovery_port: discovery_port.unwrap_or(6791),
            gateway_addresses: Arc::new(RwLock::new(None)),
            running: Arc::new(RwLock::new(false)),
        }
    }

    pub async fn run_background_tasks<F, Fut>(&self, mut handler: F) -> Result<(), Box<dyn std::error::Error + Send + Sync>> 
    where
        F: FnMut(DeviceCommand) -> Fut + Send + Sync,
        Fut: Future<Output = Result<(), Box<dyn std::error::Error + Send + Sync>>> + Send,
    {
        *self.running.write().await = true;
        log::info!("[{}] Iniciando tasks de fundo", self.sensor_id);

        let discovery_task = self.discover_gateway();
        let command_task = self.poll_for_commands(&mut handler);

        tokio::try_join!(discovery_task, command_task)?;

        Ok(())
    }

    pub async fn stop(&self) {
        *self.running.write().await = false;
        log::info!("[{}] Stopping device client", self.sensor_id);
    }

    async fn discover_gateway(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        log::info!(
            "[{}] Looking for gateway at {}:{}...",
            self.sensor_id, self.discovery_group, self.discovery_port
        );

        let addr = std::net::SocketAddr::new(std::net::IpAddr::V4(std::net::Ipv4Addr::UNSPECIFIED), self.discovery_port);
        let socket = Socket::new(Domain::IPV4, Type::DGRAM, Some(Protocol::UDP))?;
        socket.set_reuse_address(true)?;
        #[cfg(target_family = "unix")]
        socket.set_reuse_port(true)?;
        socket.bind(&addr.into())?;
        socket.set_nonblocking(true)?;
        let std_udp_socket = std::net::UdpSocket::from(socket);
        let socket = tokio::net::UdpSocket::from_std(std_udp_socket)?;

        //let socket = tokio::net::UdpSocket::bind(format!("0.0.0.0:{}", self.discovery_port)).await?;
        socket.join_multicast_v4(self.discovery_group, std::net::Ipv4Addr::UNSPECIFIED)?;

        while *self.running.read().await {
            let mut buf = [0u8; 1024];

            if let Ok(Ok((len, _addr))) = tokio::time::timeout(std::time::Duration::from_secs(1), socket.recv_from(&mut buf)).await {
                if let Ok(announcement) = crate::sensor_data::GatewayAnnouncement::decode(&buf[..len]) {
                    if self.gateway_addresses.read().await.is_none() {
                        let gateway_ip: std::net::IpAddr = announcement.gateway_ip.parse()?;
                        let addresses = GatewayAddresses {
                            tcp: std::net::SocketAddr::new(gateway_ip, announcement.tcp_port as u16),
                            udp: std::net::SocketAddr::new(gateway_ip, announcement.udp_port as u16),
                            command: std::net::SocketAddr::new(gateway_ip, announcement.command_port as u16),
                        };
                        *self.gateway_addresses.write().await = Some(addresses.clone());
                        log::info!("[{}] Gateway encontrado em {}", self.sensor_id, addresses.tcp);
                    }
                }
            }
        }
        Ok(())
    }

    async fn poll_for_commands<F, Fut>(&self, handler: &mut F) -> Result<(), Box<dyn std::error::Error + Send + Sync>>
    where
        F: FnMut(DeviceCommand) -> Fut,
        Fut: Future<Output = Result<(), Box<dyn std::error::Error + Send + Sync>>>,
    {
        while *self.running.read().await && self.gateway_addresses.read().await.is_none() {
            sleep(Duration::from_millis(100)).await;
        }

        let mut interval = interval(Duration::from_secs(5));
        
        while *self.running.read().await {
            interval.tick().await;
            
            if let Some(addresses) = self.gateway_addresses.read().await.clone() {
                if let Err(e) = self.request_command(&addresses.command, handler).await {
                    log::warn!("[{}] Falha ao fazer o poll por comandos: {}", self.sensor_id, e);
                }
            }
        }

        Ok(())
    }

    async fn request_command<F, Fut>(&self, command_addr: &SocketAddr, handler: &mut F) -> Result<(), Box<dyn std::error::Error + Send + Sync>>
    where
        F: FnMut(DeviceCommand) -> Fut,
        Fut: Future<Output = Result<(), Box<dyn std::error::Error + Send + Sync>>>,
    {  
        match TcpStream::connect(command_addr).await {
            Ok(mut stream) => {
                let sensor_id_bytes = self.sensor_id.as_bytes();
                let length = (sensor_id_bytes.len() as u32).to_be_bytes();
                stream.write_all(&length).await?;
                stream.write_all(sensor_id_bytes).await?;

                let mut len_buf = [0u8; 4];
                stream.read_exact(&mut len_buf).await?;
                let msg_len = u32::from_be_bytes(len_buf);

                if msg_len == 0 {
                    return Ok(());
                }

                let mut command_buf = vec![0u8; msg_len as usize];
                stream.read_exact(&mut command_buf).await?;
                
                let command = DeviceCommand::decode(&command_buf[..])?;
                // self.handle_command(command).await?;
                handler(command).await?;
            }
            Err(e) => {
                log::warn!("[{}] Falha ao se conectar ao gateway de comando {}: {}", 
                          self.sensor_id, command_addr, e);
            }
        }

        Ok(())
    }

    pub async fn handle_command(&self, command: DeviceCommand) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        log::info!("[{}] Recebeu o comando: '{}'", self.sensor_id, command.command);

        if command.command == "send" {
            self.send_tcp_data().await?;
        }

        Ok(())
    }

    pub async fn send_tcp_data(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let addresses = self.gateway_addresses.read().await.clone();
        let Some(addresses) = addresses else {
            log::warn!("[{}] Endereço TCP do gateway não encontrado. Não é possível enviar dados.", self.sensor_id);
            return Ok(());
        };

        let reading = self.generate_reading().await;
        
        match TcpStream::connect(&addresses.tcp).await {
            Ok(mut stream) => {
                let data = reading.encode_to_vec();
                let msg_length = (data.len() as u32).to_be_bytes();
                
                stream.write_all(&msg_length).await?;
                stream.write_all(&data).await?;

                let mut response_len_buf = [0u8; 4];
                if stream.read_exact(&mut response_len_buf).await.is_err() {
                    log::warn!("[{}] Sem resposta do gateway.", self.sensor_id);
                    return Ok(());
                }

                let response_length = u32::from_be_bytes(response_len_buf);
                let mut response_buf = vec![0u8; response_length as usize];
                stream.read_exact(&mut response_buf).await?;

                let response = Response::decode(&response_buf[..])?;

                if response.success {
                    log::info!("[{}] enviado: {} {}. Gateway respondeu: '{}'", 
                              self.sensor_id, reading.value, reading.unit, response.message);
                } else {
                    log::warn!("[{}] Gateway deu erro: '{}'", self.sensor_id, response.message);
                }
            }
            Err(e) => {
                log::warn!("[{}] Falha na conexão TCP. O gateway está offline? {}", self.sensor_id, e);
            }
        }

        Ok(())
    }

    pub async fn get_gateway_addresses(&self) -> Option<GatewayAddresses> {
        self.gateway_addresses.read().await.clone()
    }

    pub async fn is_gateway_available(&self) -> bool {
        self.gateway_addresses.read().await.is_some()
    }

    pub async fn generate_reading(&self) -> SensorReading {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64;

        SensorReading {
            sensor_id: self.sensor_id.clone(),
            location: self.location.clone(),
            sensor_type: DeviceType::Unknown.into(),
            value: 0.0,
            unit: "".to_string(),
            timestamp,
            metadata: std::collections::HashMap::new(),
        }
    }
}