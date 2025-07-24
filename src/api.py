import asyncio
import time
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.protobuf.json_format import MessageToDict
from fastapi.middleware.cors import CORSMiddleware

from gateway import Gateway

app = FastAPI(
    title="Gateway API",
    description="REST API que integra gateway e cliente",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],  
)

gateway = Gateway()

def proto_to_dict(proto_message):
    return MessageToDict(proto_message, preserving_proto_field_name=True)

class CommandPayload(BaseModel):
    command: str
    params: Dict[str, Any] = None

@app.on_event("startup")
def startup_event():
    gateway.start()
    print("✅ Serviços de do Gateway iniciara,.")

@app.get("/devices", summary="Listar todos os dispositivos")
def list_devices():
    all_sensors = gateway.get_sensor_status()
    return [proto_to_dict(reading) for reading in all_sensors.values()]

@app.get("/locations/{location_name}/devices", summary="Listar dispositivos por localização")
def stream_location_data(location_name: str):
    all_sensors = gateway.get_sensor_status()
    location_sensors = [
        proto_to_dict(r) for r in all_sensors.values() if r.location == location_name
    ]
    if not location_sensors:
        raise HTTPException(status_code=404, detail=f"Sem dispositivos na localização '{location_name}'")
    return location_sensors

@app.get("/devices/{device_id}/data", summary="Pegar dados sob demanda")
async def get_on_demand_data(device_id: str):
    sensor_data = gateway.get_sensor_status()
    last_reading = sensor_data.get(device_id)
    last_timestamp = last_reading.timestamp if last_reading else 0

    command_response = gateway.send_command_to_device(device_id, "send_tcp_data")

    if not command_response or not command_response.success:
        raise HTTPException(status_code=502, detail="Falha ao enviar comando para dispositivo. Pode ser que esteja offline")

    timeout = time.time() + 15
    while time.time() < timeout:
        current_reading = gateway.get_sensor_status().get(device_id)
        if current_reading and current_reading.timestamp > last_timestamp:
            return proto_to_dict(current_reading)
        await asyncio.sleep(0.1) 

    raise HTTPException(status_code=408, detail="Timeout")

@app.post("/devices/{device_id}/command", summary="Envia comando a um dispositivo")
def queue_command(device_id: str, payload: CommandPayload):
    response = gateway.send_command_to_device(device_id, payload.command, payload.params)

    if response and response.success:
        return {"status": "success", "message": response.message}
    
    error_message = response.message if response else "Dispositivo não encontrado ou falhou ao responder"
    raise HTTPException(status_code=500, detail=error_message)