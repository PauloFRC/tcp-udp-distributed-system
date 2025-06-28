/usr/local/bin/protoc --version
/usr/local/bin/protoc --python_out=. src/proto/sensor_data.proto

gnome-terminal -- bash -c "python3 src/run.py gateway; exec bash"

gnome-terminal -- bash -c "python3 src/run.py multi; exec bash"
