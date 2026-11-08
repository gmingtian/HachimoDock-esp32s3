//! Explicit, ignored hardware recovery check using the production installer.
use super::*;

#[test]
#[ignore = "requires explicit S3 resource-repair authorization, port, board, root and verified full backup"]
fn s3_restore_three_bootstrap_resources_preserving_saves() {
    let port=std::env::var("S3_REPAIR_PORT").expect("explicit port");
    let board=std::env::var("S3_REPAIR_BOARD").expect("explicit board");
    let root=PathBuf::from(std::env::var("S3_REPAIR_ROOT").expect("explicit source root"));
    let receipt=PathBuf::from(std::env::var("S3_REPAIR_BACKUP_RECEIPT").expect("verified full backup receipt"));
    let backup:serde_json::Value=serde_json::from_slice(&std::fs::read(receipt).unwrap()).unwrap();
    assert_eq!(backup["bytes"],0x1000000);
    assert_eq!(backup["preservedFirmware"],"0.7.103-s3-r14c-80m-l320");
    let manager=UsbSerialManager::new();
    manager.set_native_ui_root(PathBuf::from(std::env::var("S3_REPAIR_NATIVE_UI_ROOT").expect("explicit native UI resources")));
    manager.connect(&port,|_,_|{}).unwrap();
    let end=Instant::now()+Duration::from_secs(10);
    while manager.status().board_device_id!=board && Instant::now()<end { thread::sleep(Duration::from_millis(100)); }
    let status=manager.status();assert_eq!(status.board_device_id,board);assert_eq!(status.runtime,"esp-s3");
    assert_eq!(status.firmware,"0.7.103-s3-r14c-80m-l320");
    let before=manager.query_diagnostics(&board).unwrap();
    let inventory=manager.query_widget_inventory(&board).unwrap();
    let ids=["cloud-hop","block-combo","bloomfrog_companion"];
    for id in ids {
        let item=inventory["items"].as_array().unwrap().iter().find(|v|v["id"]==id).expect("existing package only");
        assert_eq!(item["resourceState"],"bootstrap", "refuse to replace a complete/custom package");
    }
    for id in ids {
        eprintln!("REPAIR {id} using production repairResources path");
        let outcome=manager.repair_widget_resources(&board,id,&root.join(id));
        eprintln!("RESULT {id}: {outcome:?}");
        outcome.unwrap();
    }
    let after_inventory=manager.query_widget_inventory(&board).unwrap();
    for id in ids {
        let item=after_inventory["items"].as_array().unwrap().iter().find(|v|v["id"]==id).unwrap();
        assert_eq!(item["resourceState"],"ready");assert_eq!(item["manifestState"],"valid");
    }
    let after=manager.query_diagnostics(&board).unwrap();
    assert_eq!(before["bootCount"],after["bootCount"]);assert_eq!(before["faultResetCount"],after["faultResetCount"]);
    manager.disconnect();
    eprintln!("PASS all three resources ready; existing save preservation enforced by repairResources commit");
}
