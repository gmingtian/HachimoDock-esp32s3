//! Explicit local-component installation, never run by ordinary cargo test.
use super::*;

fn source() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../local-clawpkgs/gomoku-a4")
}

#[test]
fn gomoku_a4_package_validates_and_compiles_without_board() {
    let dir=source();
    let validated=crate::clawpkg::validate_clawpkg_at_path(&dir).unwrap();
    assert!(validated.ok,"{:?}",validated.errors);
    let runtime=std::fs::read(dir.join("runtime/widget.json")).unwrap();
    let sprites=prepare_p4_widget_sprite_files(&dir,&runtime).unwrap();
    assert_eq!(sprites.len(),1);
    assert!(sprites[0].0.ends_with("board.p4i"),"{}",sprites[0].0);
    let data=&sprites[0].1;
    assert_eq!(&data[..4],b"P4I1");assert_eq!((data[4],data[5]),(220,220));
    assert_eq!(data.len(),u32::from_le_bytes(data[8..12].try_into().unwrap()) as usize);
    let mut pixels=Vec::new();let mut at=1036;
    while at<data.len(){
        let tag=data[at];at+=1;let n=usize::from(tag&127)+1;
        assert!(pixels.len()+n<=48400,"bounded decoded image");
        if tag&128!=0 {let index=data[at];at+=1;pixels.extend(std::iter::repeat_n(index,n));}
        else {pixels.extend_from_slice(&data[at..at+n]);at+=n;}
    }
    assert_eq!(pixels.len(),48400);
    let rgba=|x:usize,y:usize|{let i=usize::from(pixels[y*220+x]);&data[12+i*4..16+i*4]};
    assert_eq!(rgba(12,12)[3],255);assert!(rgba(12,12)[0]<rgba(13,13)[0],"first grid intersection");
    assert_eq!(rgba(208,208),rgba(12,12),"last grid intersection");
}

#[test]
#[ignore = "requires explicit user authorization and GOMOKU_PORT/BOARD/HOME/NATIVE_UI_ROOT/RECEIPT"]
fn gomoku_a4_publish_and_install_on_authorized_board() {
    let port=std::env::var("GOMOKU_PORT").expect("explicit port");
    let board=std::env::var("GOMOKU_BOARD").expect("explicit board");
    let home=PathBuf::from(std::env::var("GOMOKU_HOME").expect("explicit component library home"));
    let receipt=PathBuf::from(std::env::var("GOMOKU_RECEIPT").expect("explicit installation receipt"));
    let manager=UsbSerialManager::new();
    manager.set_native_ui_root(PathBuf::from(std::env::var("GOMOKU_NATIVE_UI_ROOT").expect("explicit S3 UI root")));
    manager.connect(&port,|_,_|{}).unwrap();
    let end=Instant::now()+Duration::from_secs(10);
    while manager.status().board_device_id!=board && Instant::now()<end { thread::sleep(Duration::from_millis(100)); }
    let status=manager.status();assert_eq!(status.board_device_id,board);assert_eq!(status.runtime,"esp-s3");
    assert_eq!(status.firmware,"0.7.103-s3-r15-80m-l320","keep verified r15 firmware");
    let before=manager.query_widget_inventory(&board).unwrap();
    let diagnostics_before=manager.query_diagnostics(&board).unwrap();
    let items=before["items"].as_array().expect("widget inventory");
    assert!(!items.iter().any(|v|v["id"]=="gomoku-a4"),"refuse to overwrite an existing game");
    let entry=crate::component_library::publish_source(&home,&source()).unwrap();
    assert!(entry.valid,"{:?}",entry.validation_errors);
    let result=manager.install_widget_clawpkg_on_board(&board,"gomoku-a4",Path::new(&entry.path),&std::collections::HashMap::new(),|done,total,bytes|{
        eprintln!("GOMOKU transfer {done}/{total} files, {bytes} bytes");
    }).unwrap();
    let after=manager.query_widget_inventory(&board).unwrap();
    let after_items=after["items"].as_array().unwrap();
    let installed=after_items.iter().find(|v|v["id"]=="gomoku-a4").expect("installed game");
    assert_eq!(installed["resourceState"],"ready");assert_eq!(installed["manifestState"],"valid");
    for original in items {
        let current=after_items.iter().find(|v|v["id"]==original["id"]).expect("existing component preserved");
        for key in ["resourceState","manifestState","version","name"] {assert_eq!(current[key],original[key],"existing {} {key}",original["id"]);}
    }
    let diagnostics_after=manager.query_diagnostics(&board).unwrap();
    assert_eq!(diagnostics_before["bootCount"],diagnostics_after["bootCount"]);
    assert_eq!(diagnostics_before["faultResetCount"],diagnostics_after["faultResetCount"]);
    let record=serde_json::json!({"board":board,"firmware":status.firmware,"libraryEntry":entry,
        "transferredFiles":result.0,"transferredBytes":result.1,"before":before,"after":after,
        "diagnosticsBefore":diagnostics_before,"diagnosticsAfter":diagnostics_after});
    std::fs::write(receipt,serde_json::to_vec_pretty(&record).unwrap()).unwrap();
    manager.disconnect();
    eprintln!("PASS Gomoku published locally and installed; existing components and r15 firmware preserved");
}
