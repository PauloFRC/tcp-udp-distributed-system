protoc --python_out=. src/proto/sensor_data.proto
python -m grpc_tools.protoc -Isrc --python_out=src --grpc_python_out=src src/proto/sensor_data.proto

python3 src/run.py multi
