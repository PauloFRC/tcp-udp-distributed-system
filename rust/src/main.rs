pub mod sensor_data {
    include!(concat!(env!("OUT_DIR"), "/sensor_data.rs"));
}

mod device_client;
mod temperature_sensor;
mod lamp_post;

use temperature_sensor::TemperatureSensorClient;
use lamp_post::LampPostClient;

#[tokio::main]
async fn main() {
    env_logger::init();

    let sensor = TemperatureSensorClient::new(
        "RUST-TEMP-01".to_string(),
        "Cocó".to_string(),
        30,
        Some("228.0.0.8"),
        Some(6791),
    );

    let sensor2 = LampPostClient::new(
        "RUST-LAMP-01".to_string(),
        "Avenida João".to_string(),
        30,
        Some("228.0.0.8"),
        Some(6791),
    );

    // tokio::select! {
    //     result = sensor.start() => {
    //         if let Err(e) = result {
    //             log::error!("Sensor falhou: {}", e);
    //         }
    //     }
    //     _ = tokio::signal::ctrl_c() => {
    //         log::info!("Desligando...");
    //         sensor.stop().await;
    //     }
    // }

    tokio::select! {
        result = sensor2.start() => {
            if let Err(e) = result {
                log::error!("Sensor falhou: {}", e);
            }
        }
        _ = tokio::signal::ctrl_c() => {
            log::info!("Desligando...");
            sensor2.stop().await;
        }
    }
}