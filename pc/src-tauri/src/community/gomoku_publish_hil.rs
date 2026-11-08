//! Explicit publication through the existing native credential/safety boundary.
use super::*;

fn input(value: Value) -> CommunityInput {
    serde_json::from_value(value).expect("explicit community input")
}

#[test]
#[ignore = "requires explicit user publication authorization and GOMOKU_COMMUNITY_MODE/HOME/ROOT"]
fn gomoku_authorized_community_publication() {
    let mode=std::env::var("GOMOKU_COMMUNITY_MODE").expect("explicit prepare or submit mode");
    assert!(matches!(mode.as_str(),"prepare"|"submit"));
    let home=PathBuf::from(std::env::var("GOMOKU_COMMUNITY_HOME").expect("explicit identity home"));
    let directory=PathBuf::from(std::env::var("GOMOKU_COMMUNITY_ROOT").expect("explicit community staging directory"));
    let package=directory.join("package");
    let metadata:Value=serde_json::from_slice(&fs::read(directory.join("metadata.json")).unwrap()).unwrap();
    assert_eq!(metadata["author"],"gaomt");
    assert_eq!(metadata["category"],"game");
    let runtime:Value=serde_json::from_slice(&fs::read(package.join("runtime/widget.json")).unwrap()).unwrap();
    assert_eq!(runtime["game"]["type"],"gomoku","retain the genuine game type");
    let manifest:Value=serde_json::from_slice(&fs::read(package.join("component.json")).unwrap()).unwrap();
    assert_eq!(manifest["id"],"gomoku-a4");assert_eq!(manifest["author"],"gaomt");
    let validation=crate::clawpkg::validate_clawpkg_at_path(&package).unwrap();
    assert!(validation.ok,"{:?}",validation.errors);
    let entry=crate::component_library::publish_source(&home,&package).unwrap();
    let prepared=execute(&home,input(json!({"action":"prepare","path":entry.path}))).unwrap();
    assert_eq!(prepared["canPublish"],true);
    fs::write(directory.join("prepared.json"),serde_json::to_vec_pretty(&prepared).unwrap()).unwrap();
    if mode=="prepare" {eprintln!("PASS public package prepared, author gaomt, all native checks passed");return;}
    let mine=execute(&home,input(json!({"action":"mine"}))).unwrap();
    fs::write(directory.join("mine-before.json"),serde_json::to_vec_pretty(&mine).unwrap()).unwrap();
    if let Some(existing)=mine["items"].as_array().and_then(|items|items.iter().find(|v|v["id"]=="gomoku-a4")){
        fs::write(directory.join("existing-publication.json"),serde_json::to_vec_pretty(existing).unwrap()).unwrap();
        eprintln!("Existing Gomoku submission found; skipped duplicate write. Review existing-publication.json");
        return;
    }
    let request_path=directory.join("submission-request.json");
    let request_record=if request_path.exists(){
        let record:Value=serde_json::from_slice(&fs::read(&request_path).unwrap()).unwrap();
        assert_eq!(record["contentHash"],prepared["contentHash"],"changed package needs a new explicit request record");
        assert_eq!(record["metadata"],metadata,"changed metadata needs a new explicit request record");record
    }else{
        let record=json!({"requestId":uuid::Uuid::new_v4().to_string(),"contentHash":prepared["contentHash"],"metadata":metadata});
        fs::write(&request_path,serde_json::to_vec_pretty(&record).unwrap()).unwrap();record
    };
    let cover=fs::read(directory.parent().unwrap().join("gomoku-a4-gameplay.png")).unwrap();
    let reply=execute(&home,input(json!({"action":"publish","path":entry.path,"metadata":metadata,
        "covers":[base64::engine::general_purpose::STANDARD.encode(cover)],
        "expectedContentHash":prepared["contentHash"],"requestId":request_record["requestId"]})));
    let record=match &reply {Ok(value)=>json!({"submitted":true,"result":value}),Err(error)=>json!({"submitted":false,"error":error})};
    fs::write(directory.join("submission-result.json"),serde_json::to_vec_pretty(&record).unwrap()).unwrap();
    match reply {
        Ok(value)=>eprintln!("SUBMITTED id={} status={}",value["id"],value["status"]),
        Err(error)=>eprintln!("NOT SUBMITTED: {error}"),
    }
    let mine_after=execute(&home,input(json!({"action":"mine"}))).unwrap();
    fs::write(directory.join("mine-after.json"),serde_json::to_vec_pretty(&mine_after).unwrap()).unwrap();
}
