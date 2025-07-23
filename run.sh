source .venv/bin/activate

#/usr/local/bin/protoc --version
#/usr/local/bin/protoc --python_out=. src/proto/sensor_data.proto
python -m grpc_tools.protoc -Isrc --python_out=src --grpc_python_out=src src/proto/sensor_data.proto

# gnome-terminal -- bash -c "python3 src/run.py gateway; exec bash"

gnome-terminal -- bash -c "python3 src/run.py multi; exec bash"

gnome-terminal -- bash -c "cd src && uvicorn api:app --reload"

# gnome-terminal -- bash -c "cd rust && cargo build && clear && RUST_LOG=info cargo run; exec bash"
