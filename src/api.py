# api.py

import asyncio
import time
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.protobuf.json_format import MessageToDict
from fastapi.middleware.cors import CORSMiddleware

# Import your modified Gateway class
from gateway import Gateway

# 1. Initialize FastAPI and the Gateway
app = FastAPI(
    title="Gateway API",
    description="REST API for interacting with IoT devices via the gateway.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Create a single instance of the Gateway
gateway = Gateway()

# Create a helper function to convert Protobuf messages to JSON-serializable dicts
def proto_to_dict(proto_message):
    return MessageToDict(proto_message, preserving_proto_field_name=True)

# 2. Define Pydantic models for request bodies
class CommandPayload(BaseModel):
    command: str
    params: Dict[str, Any] = None

# 3. Create API endpoints

@app.on_event("startup")
def startup_event():
    """
    On startup, start the gateway's background tasks for listening to devices.
    """
    gateway.start()
    print("✅ Gateway background services started.")

@app.get("/devices", summary="List All Devices")
def list_devices():
    """
    Replaces `LIST_DEVICES`.
    Retrieves the latest status and data from all connected devices.
    """
    all_sensors = gateway.get_sensor_status()
    # Convert each SensorReading protobuf object into a dictionary
    return [proto_to_dict(reading) for reading in all_sensors.values()]

@app.get("/locations/{location_name}/devices", summary="List Devices by Location")
def stream_location_data(location_name: str):
    """
    Replaces `STREAM_LOCATION_DATA`.
    Gets all current device data for a specific location.
    """
    all_sensors = gateway.get_sensor_status()
    location_sensors = [
        proto_to_dict(r) for r in all_sensors.values() if r.location == location_name
    ]
    if not location_sensors:
        raise HTTPException(status_code=404, detail=f"No devices found at location '{location_name}'")
    return location_sensors

@app.get("/devices/{device_id}/data", summary="Get On-Demand Data")
async def get_on_demand_data(device_id: str):
    """
    Replaces `GET_ON_DEMAND_DATA`.
    Triggers a device to send its latest data and returns it.
    """
    sensor_data = gateway.get_sensor_status()
    last_reading = sensor_data.get(device_id)
    last_timestamp = last_reading.timestamp if last_reading else 0

    command_response = gateway.send_command_to_device(device_id, "send_tcp_data")

    if not command_response or not command_response.success:
        raise HTTPException(status_code=502, detail="Failed to command device. It may be offline.")

    # Poll for new data with a 15-second timeout (asynchronous)
    timeout = time.time() + 15
    while time.time() < timeout:
        current_reading = gateway.get_sensor_status().get(device_id)
        if current_reading and current_reading.timestamp > last_timestamp:
            return proto_to_dict(current_reading)
        await asyncio.sleep(0.1) # Use asyncio.sleep in async functions

    raise HTTPException(status_code=408, detail="Device did not return new data in time.")

@app.post("/devices/{device_id}/command", summary="Send a Command to a Device")
def queue_command(device_id: str, payload: CommandPayload):
    """
    Replaces `QUEUE_COMMAND`.
    Sends a command to a specific device.
    """
    response = gateway.send_command_to_device(device_id, payload.command, payload.params)

    if response and response.success:
        return {"status": "success", "message": response.message}
    
    error_message = response.message if response else "Device not found or failed to respond."
    raise HTTPException(status_code=500, detail=error_message)