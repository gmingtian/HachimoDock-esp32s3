//! Explicit parent-run hardware checks. Ordinary tests only validate local artifacts.
use super::*;

const R15: &str = "0.7.103-s3-r15-80m-l320";
const R16: &str = "0.7.103-s3-r16-80m-l320";
const R15_IMAGE_SHA: &str = "0d6948c427e648ed723c9627618d523057da9d3940b517f99de028fbb3915482";

fn source() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../local-clawpkgs/xiangqi-a4")
}
fn explicit(name: &str) -> String {
    let value = std::env::var(name).unwrap_or_else(|_| panic!("{name} must be explicit"));
    assert!(!value.trim().is_empty(), "{name} must be nonempty");
    value
}
fn explicit_path(name: &str) -> PathBuf {
    let path = PathBuf::from(explicit(name));
    assert!(path.is_absolute(), "{name} must be an absolute path");
    path
}
fn receipt_path(name: &str) -> PathBuf {
    let path = explicit_path(name);
    assert!(!path.exists(), "refuse to overwrite an existing receipt");
    assert!(path.parent().unwrap().is_dir(), "receipt directory must already exist");
    path
}
fn write_new(path: &Path, value: &serde_json::Value) {
    use std::io::Write;
    let mut file = std::fs::OpenOptions::new().write(true).create_new(true).open(path).unwrap();
    file.write_all(&serde_json::to_vec_pretty(value).unwrap()).unwrap();
    file.sync_all().unwrap();
}
fn connect(manager: &UsbSerialManager, port: &str, board: &str, firmware: &str) {
    manager.connect(port, |_, _| {}).unwrap();
    let deadline = Instant::now() + Duration::from_secs(15);
    while Instant::now() < deadline {
        let status = manager.status();
        if status.connected && status.board_device_id == board && status.runtime == "esp-s3" { break; }
        thread::sleep(Duration::from_millis(100));
    }
    let status = manager.status();
    assert!(status.connected);
    assert_eq!(status.board_device_id, board);
    assert_eq!(status.runtime, "esp-s3");
    assert_eq!(status.firmware, firmware);
}
fn inventory_items(value: &serde_json::Value) -> &Vec<serde_json::Value> {
    assert_eq!(value["complete"], true, "incomplete catalog forbids mutation");
    assert_ne!(value["recoveryBlocked"], true);
    value["items"].as_array().expect("real widget inventory")
}
fn assert_preserved(before: &serde_json::Value, after: &serde_json::Value, extra: usize) {
    let old = inventory_items(before);
    let new = inventory_items(after);
    assert_eq!(new.len(), old.len() + extra);
    for original in old {
        let current = new.iter().find(|v| v["id"] == original["id"]).expect("original component retained");
        for key in ["name", "version", "manifestState", "resourceState", "imageCount"] {
            assert_eq!(current[key], original[key], "{}: {key}", original["id"]);
        }
    }
}
fn assert_counter(value: &serde_json::Value, key: &str) -> u64 {
    value[key].as_u64().unwrap_or_else(|| panic!("missing real diagnostic {key}"))
}

#[test]
fn xiangqi_a4_package_validates_and_compiles_without_board() {
    let dir = source();
    let validated = crate::clawpkg::validate_clawpkg_at_path(&dir).unwrap();
    assert!(validated.ok, "{:?}", validated.errors);
    let runtime = std::fs::read(dir.join("runtime/widget.json")).unwrap();
    let json: serde_json::Value = serde_json::from_slice(&runtime).unwrap();
    assert_eq!(json["game"]["type"], "xiangqi");
    for (field, name) in [("score_var", "ui"), ("difficulty_var", "level"), ("status_var", "phase")] {
        assert_eq!(json["game"][field], name);
        assert_eq!(json["vars"][name]["type"], "int");
    }
    let actions = json["game"]["actions"].as_object().unwrap();
    assert_eq!(actions.len(), 6);
    for action in ["place", "undo", "left", "right", "up", "down"] { assert!(actions.contains_key(action)); }
    let sprites = prepare_p4_widget_sprite_files(&dir, &runtime).unwrap();
    assert_eq!(sprites.len(), 1);
    assert!(sprites[0].0.ends_with("board.p4i"));
    let data = &sprites[0].1;
    assert!(data.len() >= 1036);
    assert_eq!(&data[..4], b"P4I1");
    assert_eq!((data[4], data[5]), (198, 220));
    assert_eq!(data.len(), u32::from_le_bytes(data[8..12].try_into().unwrap()) as usize);
    // Verify decoded coverage. RLE bytes need not exceed the pixel count.
    let mut decoded = 0usize;
    let mut at = 1036usize;
    while at < data.len() {
        let tag = data[at]; at += 1;
        let count = usize::from(tag & 127) + 1;
        decoded += count;
        assert!(decoded <= 198 * 220);
        let payload = if tag & 128 != 0 { 1 } else { count };
        assert!(at + payload <= data.len(), "complete RLE payload");
        at += payload;
    }
    assert_eq!(decoded, 198 * 220);
}

#[test]
#[ignore = "parent-only authorized new install; explicit XQ_HOME/PORT/BOARD/NATIVE_UI_ROOT/RECEIPT required"]
fn xiangqi_a4_publish_and_install_on_authorized_r16_board() {
    let port = explicit("XQ_PORT");
    let board_owned = explicit("XQ_BOARD"); let board = board_owned.trim();
    let home = explicit_path("XQ_HOME"); assert!(home.is_dir());
    let ui = explicit_path("XQ_NATIVE_UI_ROOT"); assert!(ui.join("inventory.json").is_file());
    let receipt = receipt_path("XQ_RECEIPT");
    let before_receipt = receipt.with_extension("before.json"); assert!(!before_receipt.exists());
    xiangqi_a4_package_validates_and_compiles_without_board();
    let manager = UsbSerialManager::new(); manager.set_native_ui_root(ui);
    connect(&manager, &port, board, R16);
    let (_, connection) = manager.connected_board_snapshot(board).unwrap();
    let settled = manager.query_firmware_status(board, connection).unwrap();
    assert_eq!(settled["version"], R16);
    assert_eq!(settled["runtimeReady"], true);
    assert_eq!(settled["imageState"], "valid");
    assert_eq!(settled["pendingVerify"], false);
    assert_eq!(settled["active"], false);
    let before = manager.query_widget_inventory(board).unwrap();
    let items = inventory_items(&before);
    assert_eq!(items.len(), 30, "expected original thirty components");
    assert!(!items.iter().any(|v| v["id"] == "xiangqi-a4"), "new install only; refuse overwrite");
    assert!(before["maxInstalled"].as_u64().expect("actual slot capacity") > items.len() as u64);
    let diagnostics_before = manager.query_diagnostics(board).unwrap();
    let boot = assert_counter(&diagnostics_before, "bootCount");
    let faults = assert_counter(&diagnostics_before, "faultResetCount");
    let buttons_before = manager.query_button_config(board).unwrap();
    assert!(!buttons_before["config"].is_null(), "real button configuration required");
    write_new(&before_receipt, &serde_json::json!({"board":board,"firmware":R16,"before":before,"diagnostics":diagnostics_before,"buttons":buttons_before}));
    let entry = crate::component_library::publish_source(&home, &source()).unwrap();
    assert_eq!(entry.id, "xiangqi-a4"); assert!(entry.valid, "{:?}", entry.validation_errors);
    let transfer = manager.install_widget_clawpkg_on_board(board, "xiangqi-a4", Path::new(&entry.path), &HashMap::new(), |done, total, bytes| {
        eprintln!("XQ install {done}/{total} files {bytes} bytes");
    }).unwrap();
    let after = manager.query_widget_inventory(board).unwrap();
    assert_preserved(&before, &after, 1);
    let installed = inventory_items(&after).iter().find(|v| v["id"] == "xiangqi-a4").unwrap();
    assert_eq!(installed["resourceState"], "ready"); assert_eq!(installed["manifestState"], "valid");
    let diagnostics_after = manager.query_diagnostics(board).unwrap();
    assert_eq!(assert_counter(&diagnostics_after, "bootCount"), boot);
    assert_eq!(assert_counter(&diagnostics_after, "faultResetCount"), faults);
    assert_eq!(manager.status().firmware, R16);
    let buttons_after = manager.query_button_config(board).unwrap();
    assert_eq!(buttons_before["config"], buttons_after["config"]);
    write_new(&receipt, &serde_json::json!({"board":board,"firmware":R16,"libraryEntry":entry,"transferredFiles":transfer.0,"transferredBytes":transfer.1,"before":before,"after":after,"diagnosticsBefore":diagnostics_before,"diagnosticsAfter":diagnostics_after,"buttonsBefore":buttons_before,"buttonsAfter":buttons_after}));
    manager.disconnect();
}

#[test]
#[ignore = "parent-only authorized r15-to-r16 OTA; explicit verified 16MiB r15 backup and target SHA required"]
fn xiangqi_r15_to_r16_ota_preserves_original_slot_and_userdata() {
    let port = explicit("XQ_PORT"); let board_owned = explicit("XQ_BOARD"); let board = board_owned.trim();
    let firmware_path = explicit_path("XQ_FIRMWARE_BIN");
    let expected_sha = explicit("XQ_FIRMWARE_SHA256");
    assert_eq!(expected_sha.len(), 64); assert!(expected_sha.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()));
    let receipt = receipt_path("XQ_OTA_RECEIPT");
    let before_receipt = receipt.with_extension("before.json"); assert!(!before_receipt.exists());
    let backup_receipt = explicit_path("XQ_BACKUP_RECEIPT");
    let proof: serde_json::Value = serde_json::from_slice(&std::fs::read(&backup_receipt).unwrap()).unwrap();
    assert_eq!(proof["board"], board); assert_eq!(proof["bytes"], 0x1000000u64);
    assert_eq!(proof["preservedFirmware"], R15); assert_eq!(proof["preservedSlot"], "ota_0");
    assert_eq!(proof["preservedImageSha256"], R15_IMAGE_SHA);
    let backup_path = PathBuf::from(proof["backup"].as_str().expect("absolute full-flash backup path"));
    assert!(backup_path.is_absolute());
    let backup = std::fs::read(&backup_path).unwrap(); assert_eq!(backup.len(), 0x1000000);
    assert_eq!(format!("{:x}", Sha256::digest(&backup)), proof["sha256"].as_str().unwrap());
    let image_bytes = usize::try_from(proof["preservedImageBytes"].as_u64().unwrap()).unwrap();
    assert!(image_bytes > 256 && image_bytes <= 0x300000);
    let r15 = &backup[0x10000..0x10000 + image_bytes];
    assert_eq!(format!("{:x}", Sha256::digest(r15)), R15_IMAGE_SHA);
    let old_desc = parse_esp_idf_app_descriptor(r15).unwrap();
    assert_eq!(old_desc.version, R15); assert_eq!(old_desc.project_name, "pet_manager_s3_runtime");
    let firmware = std::fs::read(&firmware_path).unwrap();
    assert_eq!(format!("{:x}", Sha256::digest(&firmware)), expected_sha);
    let descriptor = parse_esp_idf_app_descriptor(&firmware).unwrap();
    assert_eq!(descriptor.version, R16); assert_eq!(descriptor.project_name, "pet_manager_s3_runtime");
    validate_firmware_for_target(&firmware, P4ChipTarget::S3).unwrap();
    let manager = UsbSerialManager::new(); connect(&manager, &port, board, R15);
    let (_, connection) = manager.connected_board_snapshot(board).unwrap();
    let ota_before = manager.query_firmware_status(board, connection).unwrap();
    assert_eq!(ota_before["version"], R15); assert_eq!(ota_before["runtimeReady"], true);
    assert_eq!(ota_before["pendingVerify"], false); assert_eq!(ota_before["active"], false);
    assert_eq!(ota_before["imageState"], "valid");
    assert_eq!(ota_before["runningPartition"]["label"], "ota_0");
    assert_eq!(ota_before["runningPartition"]["address"], 0x10000u64);
    assert_eq!(ota_before["runningPartition"]["size"], 0x300000u64);
    assert_eq!(ota_before["bootPartition"]["label"], "ota_0");
    assert_eq!(ota_before["nextPartition"]["label"], "ota_1");
    assert_eq!(ota_before["nextPartition"]["address"], 0x310000u64);
    assert_eq!(ota_before["nextPartition"]["size"], 0x300000u64);
    firmware_transaction::ensure_device_firmware_headroom(&ota_before, firmware.len()).unwrap();
    let before = manager.query_widget_inventory(board).unwrap(); assert_eq!(inventory_items(&before).len(), 30);
    let diagnostics_before = manager.query_diagnostics(board).unwrap();
    let boot = assert_counter(&diagnostics_before, "bootCount");
    let faults = assert_counter(&diagnostics_before, "faultResetCount");
    let buttons_before = manager.query_button_config(board).unwrap();
    assert!(!buttons_before["config"].is_null(), "real button configuration required");
    write_new(&before_receipt, &serde_json::json!({"board":board,"source":R15,"target":R16,"targetSha256":expected_sha,"backupReceipt":proof,"otaBefore":ota_before,"before":before,"diagnostics":diagnostics_before,"buttons":buttons_before}));
    let reconnect_manager = manager.clone(); let reconnect_port = port.clone(); let reconnect_board = board.to_owned();
    let result = manager.update_firmware(&firmware_path, board, |sent, total, stage| {
        if stage != "upload" || sent == total || sent % 65536 == 0 { eprintln!("XQ OTA {stage} {sent}/{total}"); }
    }, move |_| {
        reconnect_manager.disconnect();
        let deadline = Instant::now() + Duration::from_secs(30);
        while Instant::now() < deadline {
            if reconnect_manager.connect(&reconnect_port, |_, _| {}).is_ok() {
                let hello = Instant::now() + Duration::from_secs(5);
                while Instant::now() < hello {
                    let s = reconnect_manager.status();
                    if s.connected && s.board_device_id == reconnect_board && s.runtime == "esp-s3" && s.firmware == R16 { return Ok(()); }
                    thread::sleep(Duration::from_millis(100));
                }
                reconnect_manager.disconnect();
            }
            thread::sleep(Duration::from_millis(500));
        }
        Err("no actual r16 HELLO from authorized board after OTA".into())
    }).unwrap();
    assert_eq!(result.version, R16); assert_eq!(result.sha256, expected_sha);
    assert_eq!(result.target_partition, "ota_1"); assert_eq!(result.image_state, "valid"); assert!(!result.pending_reboot);
    let (_, connection) = manager.connected_board_snapshot(board).unwrap();
    let ota_after = manager.query_firmware_status(board, connection).unwrap();
    assert_eq!(ota_after["version"], R16); assert_eq!(ota_after["runtimeReady"], true);
    assert_eq!(ota_after["imageState"], "valid"); assert_eq!(ota_after["pendingVerify"], false); assert_eq!(ota_after["active"], false);
    assert_eq!(ota_after["runningPartition"]["label"], "ota_1"); assert_eq!(ota_after["bootPartition"]["label"], "ota_1");
    assert_eq!(ota_after["nextPartition"]["label"], "ota_0");
    let after = manager.query_widget_inventory(board).unwrap(); assert_preserved(&before, &after, 0);
    let diagnostics_after = manager.query_diagnostics(board).unwrap();
    assert_eq!(assert_counter(&diagnostics_after, "bootCount"), boot + 1);
    assert_eq!(assert_counter(&diagnostics_after, "faultResetCount"), faults);
    let buttons_after = manager.query_button_config(board).unwrap(); assert_eq!(buttons_before["config"], buttons_after["config"]);
    assert_eq!(diagnostics_before["storage"]["activeAppearanceSlot"], diagnostics_after["storage"]["activeAppearanceSlot"]);
    write_new(&receipt, &serde_json::json!({"board":board,"source":R15,"target":R16,"result":result,"backupReceipt":proof,"otaBefore":ota_before,"otaAfter":ota_after,"before":before,"after":after,"diagnosticsBefore":diagnostics_before,"diagnosticsAfter":diagnostics_after,"buttonsBefore":buttons_before,"buttonsAfter":buttons_after}));
    manager.disconnect();
}

#[test]
#[ignore = "parent-only isolated r16b-to-r16c production OTA; explicit verified 16MiB r16b backup, target SHA and new receipt paths required"]
fn xiangqi_r16b_to_r16c_cadence_ota_retains_accepted_r16b() {
    const R16B: &str = "0.7.103-s3-r16b-80m-l320";
    const R16C: &str = "0.7.103-s3-r16c-80m-l320";
    const IMAGE_BYTES: usize = 2_594_464;
    const TARGET_SHA: &str = "07ffa6be00feb6cb90ddd747099d20d3fa79ffbcf7bac4cbacdd8057e4496efb";
    const PRESERVED_SHA: &str = "b74735a501cc04fa8602c3cfa1f6b4e2ce2c11730ac004b0e979d7a88e80cb8a";

    let port = explicit("XQ_PORT");
    let board_owned = explicit("XQ_BOARD"); let board = board_owned.trim();
    let firmware_path = explicit_path("XQ_FIRMWARE_BIN");
    let expected_sha = explicit("XQ_FIRMWARE_SHA256");
    assert_eq!(expected_sha, TARGET_SHA, "only the frozen r16c candidate is authorized");
    let receipt = receipt_path("XQ_OTA_RECEIPT");
    let before_receipt = receipt.with_extension("before.json");
    assert!(!before_receipt.exists(), "refuse to overwrite pre-mutation evidence");

    let backup_receipt = explicit_path("XQ_BACKUP_RECEIPT");
    let proof: serde_json::Value = serde_json::from_slice(&std::fs::read(&backup_receipt).unwrap()).unwrap();
    assert_eq!(proof["board"], board);
    assert_eq!(proof["bytes"], 0x1000000u64);
    assert_eq!(proof["preservedFirmware"], R16B);
    assert_eq!(proof["preservedSlot"], "ota_1");
    assert_eq!(proof["preservedImageBytes"], IMAGE_BYTES as u64);
    assert_eq!(proof["preservedImageSha256"], PRESERVED_SHA);
    let backup_path = PathBuf::from(proof["backup"].as_str().expect("absolute complete-flash backup path"));
    assert!(backup_path.is_absolute());
    let backup = std::fs::read(&backup_path).unwrap();
    assert_eq!(backup.len(), 0x1000000);
    assert_eq!(format!("{:x}", Sha256::digest(&backup)), proof["sha256"].as_str().unwrap());
    let preserved = &backup[0x310000..0x310000 + IMAGE_BYTES];
    assert_eq!(format!("{:x}", Sha256::digest(preserved)), PRESERVED_SHA);
    let old_descriptor = parse_esp_idf_app_descriptor(preserved).unwrap();
    assert_eq!(old_descriptor.version, R16B);
    assert_eq!(old_descriptor.project_name, "pet_manager_s3_runtime");
    validate_firmware_for_target(preserved, P4ChipTarget::S3).unwrap();

    let firmware = std::fs::read(&firmware_path).unwrap();
    assert_eq!(firmware.len(), IMAGE_BYTES);
    assert_eq!(format!("{:x}", Sha256::digest(&firmware)), TARGET_SHA);
    let descriptor = parse_esp_idf_app_descriptor(&firmware).unwrap();
    assert_eq!(descriptor.version, R16C);
    assert_eq!(descriptor.project_name, "pet_manager_s3_runtime");
    validate_firmware_for_target(&firmware, P4ChipTarget::S3).unwrap();

    // No desktop auto-probe/heartbeat thread: only this isolated production manager.
    let manager = UsbSerialManager::new();
    connect(&manager, &port, board, R16B);
    let (_, connection) = manager.connected_board_snapshot(board).unwrap();
    let ota_before = manager.query_firmware_status(board, connection).unwrap();
    assert_eq!(ota_before["supported"], true);
    assert_eq!(ota_before["version"], R16B);
    assert_eq!(ota_before["runtimeReady"], true);
    assert_eq!(ota_before["pendingVerify"], false);
    assert_eq!(ota_before["active"], false, "unknown/interrupted OTA forbids begin");
    assert_eq!(ota_before["imageState"], "valid");
    assert_eq!(ota_before["runningPartition"]["label"], "ota_1");
    assert_eq!(ota_before["runningPartition"]["address"], 0x310000u64);
    assert_eq!(ota_before["runningPartition"]["size"], 0x300000u64);
    assert_eq!(ota_before["bootPartition"]["label"], "ota_1");
    assert_eq!(ota_before["nextPartition"]["label"], "ota_0");
    assert_eq!(ota_before["nextPartition"]["address"], 0x10000u64);
    assert_eq!(ota_before["nextPartition"]["size"], 0x300000u64);
    firmware_transaction::ensure_device_firmware_headroom(&ota_before, firmware.len()).unwrap();
    let before = manager.query_widget_inventory(board).unwrap();
    let items = inventory_items(&before);
    assert_eq!(items.len(), 31);
    assert_eq!(items.iter().map(|v| v["id"].as_str().expect("real component id"))
        .collect::<std::collections::HashSet<_>>().len(), 31);
    assert!(items.iter().any(|v| v["id"] == "xiangqi-a4"));
    for item in items {
        assert_eq!(item["manifestState"], "valid");
        assert_eq!(item["resourceState"], "ready");
    }
    let diagnostics_before = manager.query_diagnostics(board).unwrap();
    let boot = assert_counter(&diagnostics_before, "bootCount");
    let faults = assert_counter(&diagnostics_before, "faultResetCount");
    let dropped = assert_counter(&diagnostics_before["runtime"], "inputDroppedEvents");
    let appearance = assert_counter(&diagnostics_before["storage"], "activeAppearanceSlot");
    assert!(appearance <= 1);
    let buttons_before = manager.query_button_config(board).unwrap();
    assert_eq!(buttons_before["bindingCount"], 16);
    assert_eq!(buttons_before["config"]["bindings"].as_array().expect("real bindings").len(), 16);
    write_new(&before_receipt, &serde_json::json!({
        "board":board,"source":R16B,"target":R16C,"targetBytes":IMAGE_BYTES,
        "targetSha256":TARGET_SHA,"backupReceiptPath":backup_receipt,"backupReceipt":proof,
        "otaBefore":ota_before,"before":before,"diagnostics":diagnostics_before,"buttons":buttons_before
    }));
    // A read-only idle check immediately precedes the sole production update.
    // Unknown results panic/stop; there is no replay, recovery begin or abort.
    manager.ensure_firmware_transfer_idle(board, connection).unwrap();
    let reconnect_manager = manager.clone();
    let reconnect_port = port.clone(); let reconnect_board = board.to_owned();
    let result = manager.update_firmware(&firmware_path, board, |sent, total, stage| {
        if stage != "upload" || sent == total || sent % 65536 == 0 {
            eprintln!("XQ r16c OTA {stage} {sent}/{total}");
        }
    }, move |_| {
        reconnect_manager.disconnect();
        let deadline = Instant::now() + Duration::from_secs(30);
        while Instant::now() < deadline {
            if reconnect_manager.connect(&reconnect_port, |_, _| {}).is_ok() {
                let hello = Instant::now() + Duration::from_secs(5);
                while Instant::now() < hello {
                    let status = reconnect_manager.status();
                    if status.connected && status.board_device_id == reconnect_board
                        && status.runtime == "esp-s3" && status.firmware == R16C { return Ok(()); }
                    thread::sleep(Duration::from_millis(100));
                }
                reconnect_manager.disconnect();
            }
            thread::sleep(Duration::from_millis(500));
        }
        Err("no actual r16c HELLO from authorized board after OTA; no replay".into())
    }).unwrap();
    assert_eq!(result.version, R16C);
    assert_eq!(result.sha256, TARGET_SHA);
    assert_eq!(result.bytes, IMAGE_BYTES as u64);
    assert_eq!(result.target_partition, "ota_0");
    assert_eq!(result.image_state, "valid");
    assert!(!result.pending_reboot);
    let (_, connection) = manager.connected_board_snapshot(board).unwrap();
    let ota_after = manager.query_firmware_status(board, connection).unwrap();
    assert_eq!(ota_after["version"], R16C);
    assert_eq!(ota_after["runtimeReady"], true);
    assert_eq!(ota_after["imageState"], "valid");
    assert_eq!(ota_after["pendingVerify"], false);
    assert_eq!(ota_after["active"], false);
    assert_eq!(ota_after["runningPartition"]["label"], "ota_0");
    assert_eq!(ota_after["runningPartition"]["address"], 0x10000u64);
    assert_eq!(ota_after["bootPartition"]["label"], "ota_0");
    assert_eq!(ota_after["nextPartition"]["label"], "ota_1");
    assert_eq!(ota_after["nextPartition"]["address"], 0x310000u64);
    let after = manager.query_widget_inventory(board).unwrap();
    assert_preserved(&before, &after, 0);
    let diagnostics_after = manager.query_diagnostics(board).unwrap();
    assert_eq!(assert_counter(&diagnostics_after, "bootCount"), boot + 1);
    assert_eq!(assert_counter(&diagnostics_after, "faultResetCount"), faults);
    assert_eq!(assert_counter(&diagnostics_after["runtime"], "inputDroppedEvents"), dropped);
    assert_eq!(assert_counter(&diagnostics_after["storage"], "activeAppearanceSlot"), appearance);
    let buttons_after = manager.query_button_config(board).unwrap();
    assert_eq!(buttons_after["bindingCount"], 16);
    assert_eq!(buttons_before["config"], buttons_after["config"]);
    write_new(&receipt, &serde_json::json!({
        "board":board,"source":R16B,"target":R16C,"result":result,
        "backupReceiptPath":backup_receipt,"backupReceipt":proof,
        "otaBefore":ota_before,"otaAfter":ota_after,"before":before,"after":after,
        "diagnosticsBefore":diagnostics_before,"diagnosticsAfter":diagnostics_after,
        "buttonsBefore":buttons_before,"buttonsAfter":buttons_after
    }));
    manager.disconnect();
}
