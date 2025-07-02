use crate::device_client::DeviceClient;
use crate::sensor_data::{DeviceType, SensorReading, DeviceCommand};
use rand::Rng;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::time::{interval, Duration};
use std::sync::atomic::AtomicBool;
use std::sync::atomic::Ordering;

pub struct LampPostClient {
    device_client: DeviceClient,
    state: AtomicBool,
}

impl LampPostClient {
    pub fn new(
        sensor_id: String,
        location: String,
        interval_secs: u64,
        discovery_group: Option<&str>,
        discovery_port: Option<u16>,
    ) -> Self {
        Self {
            device_client: DeviceClient::new(
                sensor_id,
                location,
                interval_secs,
                discovery_group,
                discovery_port,
            ),
            state: AtomicBool::new(false),
        }
    }

    fn generate_reading(&self) -> SensorReading {
        let mut rng = rand::thread_rng();

        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64;

        SensorReading {
            sensor_id: self.device_client.sensor_id.clone(),
            location: self.device_client.location.clone(),
            sensor_type: DeviceType::LampPost.into(),
            value: if self.state.load(Ordering::SeqCst) { 1.0 } else { 0.0 },
            unit: "".to_string(),
            timestamp,
            metadata: std::collections::HashMap::new(),
        }
    }

    pub async fn start(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        log::info!("[{}] Iniciando posto de luz", self.device_client.sensor_id);

        let handler = move |command: DeviceCommand| async move {
            self.handle_command(command).await
        };

        let device_client_tasks = self.device_client.run_background_tasks(handler);
        let monitoring_task = self.monitor_loop();

        tokio::try_join!(device_client_tasks, monitoring_task)?;

        Ok(())
    }

    async fn monitor_loop(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        while !self.device_client.is_gateway_available().await {
            tokio::time::sleep(Duration::from_millis(100)).await;
        }

        let mut interval = interval(self.device_client.interval);

        loop {
            interval.tick().await;
            
            let reading = self.generate_reading();
            
            if let Err(e) = self.send_udp_reading(reading).await {
                log::error!("[{}] Falha ao enviar dado UDP: {}", self.device_client.sensor_id, e);
            }
        }
    }

    async fn send_udp_reading(&self, reading: SensorReading) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        use prost::Message;
        use tokio::net::UdpSocket;

        let addresses = self.device_client.get_gateway_addresses().await;
        let Some(addresses) = addresses else {
            log::warn!("[{}] Endereço UDP do gateway não encontrado. Não é possível enviar dados.", self.device_client.sensor_id);
            return Ok(());
        };

        let data = reading.encode_to_vec();

        match UdpSocket::bind("0.0.0.0:0").await {
            Ok(socket) => {
                socket.send_to(&data, &addresses.udp).await?;
                log::info!("[{}] enviado via UDP para {}: {} {}", 
                          self.device_client.sensor_id, addresses.udp, reading.value, reading.unit);
            }
            Err(e) => {
                log::error!("[{}] Erro ao enviar dados via UDP: {}", self.device_client.sensor_id, e);
            }
        }

        Ok(())
    }

    async fn handle_command(&self, command: DeviceCommand) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        self.device_client.handle_command(command.clone()).await?;

        match command.command.as_str() {
            "send" => {
                log::info!("[{}] Enviando leitura do poste", self.device_client.sensor_id);
                let reading = self.generate_reading();
                self.device_client.send_tcp_data(reading).await?
            }
            "on" => {
                log::info!("[{}] Ligando poste", self.device_client.sensor_id);
                self.state.store(true, Ordering::SeqCst);
            }
            "off" => {
                log::info!("[{}] Desligando poste", self.device_client.sensor_id);
                self.state.store(false, Ordering::SeqCst);
            }
            _ => {
                log::info!("[{}] Comando não reconhecido", self.device_client.sensor_id);
            }
        }

        Ok(())
    }


    pub async fn stop(&self) {
        self.device_client.stop().await;
    }
}