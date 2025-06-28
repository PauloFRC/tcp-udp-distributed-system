protoc --python_out=. src/proto/sensor_data.proto

python3 src/run.py multi
