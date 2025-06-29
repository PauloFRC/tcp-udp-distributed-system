fn main() {
    // Tell Cargo to re-run this build script if the .proto file changes.
    println!("cargo:rerun-if-changed=../proto/iot_system.proto");

    // Use prost_build to compile the protobuf file.
    // This will generate Rust code from iot_system.proto and place it in the `OUT_DIR`,
    // which allows our main.rs to `include!` it.
    prost_build::compile_protos(&["../proto/iot_system.proto"], &["../proto/"]).unwrap();
}
