fn main() {
    println!("cargo:rerun-if-changed=proto/sensor_data.proto");
    if let Err(e) = prost_build::compile_protos(&["proto/sensor_data.proto"], &["proto/"]) {
        panic!("prost-build failed: {}", e);
    }
}