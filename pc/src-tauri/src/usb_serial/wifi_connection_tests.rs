use super::*;
use std::net::{TcpListener, TcpStream};

fn install(manager: &UsbSerialManager, on_message: impl Fn(String, serde_json::Value) + Send + 'static) -> TcpStream {
    let listener=TcpListener::bind("127.0.0.1:0").unwrap();
    let peer=TcpStream::connect(listener.local_addr().unwrap()).unwrap();
    let (stream,_)=listener.accept().unwrap();
    stream.set_read_timeout(Some(Duration::from_millis(30))).unwrap();
    let hello=SerialMessage { topic:"hello".into(), payload:serde_json::json!({"boardDeviceId":"s3-shared","runtime":"esp-s3"}) };
    manager.install_verified_stream("127.0.0.1:48973".into(),0,"wifi",Box::new(stream.try_clone().unwrap()),Box::new(stream),hello,Arc::new(AtomicBool::new(false)),on_message).unwrap();
    peer
}

#[test]
fn wifi_shared_connection_reports_real_transport_and_never_replays_closed_reader() {
    let manager=UsbSerialManager::new();
    let (tx,rx)=mpsc::channel();
    let mut old=install(&manager,move |topic,_| { let _=tx.send(topic); });
    assert_eq!(rx.recv_timeout(Duration::from_secs(1)).unwrap(),"hello");
    assert_eq!(manager.status().transport,"wifi");
    manager.disconnect();
    let _=old.write_all(b"{\"topic\":\"input/event\",\"payload\":{}}\n");
    assert!(rx.recv_timeout(Duration::from_millis(200)).is_err());
}

#[test]
fn wifi_shared_request_resolves_existing_waiter_and_keeps_pair_secret_out_of_events() {
    let manager=UsbSerialManager::new();
    let (tx,rx)=mpsc::channel();
    let mut peer=install(&manager,move |topic,_| { let _=tx.send(topic); });
    assert_eq!(rx.recv_timeout(Duration::from_secs(1)).unwrap(),"hello");
    let server=thread::spawn(move || {
        let mut reader=BufReader::new(peer.try_clone().unwrap());
        let mut line=String::new(); reader.read_line(&mut line).unwrap();
        let request:serde_json::Value=serde_json::from_str(&line).unwrap();
        assert_eq!(request["topic"],"wifi/pair");
        let response=serde_json::json!({"topic":"wifi/pair","payload":{"ok":true,"boardDeviceId":"s3-shared","requestId":request["payload"]["requestId"],"token":"private-fixture"}});
        peer.write_all(format!("{response}\n").as_bytes()).unwrap();
    });
    let response=manager.maintenance_request("s3-shared","wifi/pair","wifi/pair",serde_json::json!({})).unwrap();
    assert_eq!(response["token"],"private-fixture");
    assert!(rx.recv_timeout(Duration::from_millis(100)).is_err());
    server.join().unwrap();
}

#[test]
fn wifi_switch_is_blocked_during_capture_and_resource_transactions() {
    let manager=UsbSerialManager::new(); let _peer=install(&manager,|_,_|{});
    manager.ensure_transport_switch_idle().unwrap();
    manager.connection.lock().unwrap().as_mut().unwrap().capture_active.store(true,Ordering::Release);
    assert!(manager.ensure_transport_switch_idle().is_err());
    manager.connection.lock().unwrap().as_mut().unwrap().capture_active.store(false,Ordering::Release);
    let _guard=manager.asset_transfer_guard.lock().unwrap();
    assert!(manager.ensure_transport_switch_idle().is_err());
}

#[test]
fn wifi_s3_unsupported_builtin_install_fails_before_any_device_write() {
    let manager=UsbSerialManager::new();let mut peer=install(&manager,|_,_|{});
    peer.set_read_timeout(Some(Duration::from_millis(100))).unwrap();
    let empty=tempfile::tempdir().unwrap();
    let result=manager.install_widget_clawpkg_on_board("s3-shared","fresh-fruit-slice",empty.path(),&HashMap::new(),|_,_,_|{});
    assert!(result.unwrap_err().contains("不支持 S3 三键"));
    assert!(peer.read(&mut [0u8;16]).is_err(),"unsupported package must not enter begin/erase");
}

type TlsPeer=rustls::StreamOwned<rustls::ServerConnection,TcpStream>;
fn read_frame(peer:&mut TlsPeer)->serde_json::Value {
    crate::wifi_transport::read_json_line(peer,32768,Instant::now()+Duration::from_secs(4)).unwrap()
}
fn send_frame(peer:&mut TlsPeer,topic:&str,payload:serde_json::Value) {
    peer.write_all(format!("{}\n",serde_json::json!({"topic":topic,"payload":payload})).as_bytes()).unwrap();
    peer.flush().unwrap();
}
fn tls_peer(work:impl FnOnce(&mut TlsPeer)+Send+'static)->(crate::wifi_transport::WifiIdentity,std::net::SocketAddr,thread::JoinHandle<()>) {
    let cert=rcgen::generate_simple_self_signed(vec!["s3-shared.local".into()]).unwrap();
    let config=rustls::ServerConfig::builder_with_provider(Arc::new(rustls::crypto::ring::default_provider()))
        .with_safe_default_protocol_versions().unwrap().with_no_client_auth()
        .with_single_cert(vec![cert.cert.der().clone()],rustls::pki_types::PrivatePkcs8KeyDer::from(cert.key_pair.serialize_der()).into()).unwrap();
    let identity=crate::wifi_transport::WifiIdentity {board_device_id:"s3-shared".into(),hostname:"s3-shared.local".into(),certificate_pem:cert.cert.pem(),token:"ab".repeat(32)};
    let listener=TcpListener::bind("127.0.0.1:0").unwrap();let address=listener.local_addr().unwrap();
    let worker=thread::spawn(move||{
        let (socket,_)=listener.accept().unwrap();socket.set_read_timeout(Some(Duration::from_secs(4))).unwrap();socket.set_write_timeout(Some(Duration::from_secs(4))).unwrap();
        let mut peer=rustls::StreamOwned::new(rustls::ServerConnection::new(Arc::new(config)).unwrap(),socket);
        let auth=read_frame(&mut peer);assert_eq!(auth["topic"],"wifi/auth");
        send_frame(&mut peer,"wifi/auth",serde_json::json!({"ok":true,"boardDeviceId":"s3-shared","requestId":auth["payload"]["requestId"]}));
        send_frame(&mut peer,"hello",serde_json::json!({"boardDeviceId":"s3-shared","runtime":"esp-s3","capabilities":{"transport":{"wifi":true,"rawAssetReadyAck":true,"rawAssetChunks":true,"rawAssetChunkBytes":8192}}}));
        assert_eq!(read_frame(&mut peer)["topic"],"ack");
        work(&mut peer);
    });
    (identity,address,worker)
}

#[test]
fn wifi_tls_shared_raw_assets_widget_firmware_and_bidirectional_audio() {
    let (identity,address,server)=tls_peer(|peer|{
        let mut received=Vec::new();
        loop {
            let frame=read_frame(peer);let topic=frame["topic"].as_str().unwrap();let p=&frame["payload"];
            received.push(topic.to_string());
            match topic {
                "asset/begin"=>send_frame(peer,"asset/ack",serde_json::json!({"transferId":p["transferId"],"phase":"begin","ok":true})),
                "asset/raw-chunk"=>{
                    send_frame(peer,"asset/ack",serde_json::json!({"transferId":p["transferId"],"phase":"raw-ready","path":p["path"],"index":p["index"],"ok":true}));
                    let mut raw=vec![0;p["size"].as_u64().unwrap() as usize];peer.read_exact(&mut raw).unwrap();
                    assert_eq!(raw,(0..8192).map(|n|(n%251)as u8).collect::<Vec<_>>());
                    assert_eq!(p["checksum"],asset_checksum_hex(&raw));
                    send_frame(peer,"asset/ack",serde_json::json!({"transferId":p["transferId"],"phase":"raw-chunk","path":p["path"],"index":p["index"],"ok":true}));
                }
                "asset/file"|"asset/commit"=>send_frame(peer,"asset/ack",serde_json::json!({"transferId":p["transferId"],"phase":if topic=="asset/file"{"file"}else{"commit"},"path":p["path"],"ok":true})),
                "widget/chunk"=>send_frame(peer,"widget-install-ack",serde_json::json!({"transferId":p["transferId"],"phase":"chunk","path":p["path"],"index":p["index"],"ok":true})),
                "firmware/chunk"=>send_frame(peer,"firmware/ack",serde_json::json!({"transferId":p["transferId"],"phase":"chunk","nextSequence":1,"receivedBytes":3,"ok":true})),
                "audio/control"=>{
                    assert_eq!(p["action"],"start");
                    send_frame(peer,"audio/chunk",serde_json::json!({"boardDeviceId":"s3-shared","sessionId":"capture-test","seq":0,"data":"AQID"}));
                }
                "audio/play_chunk"=>{assert_eq!(p["data"],"BAUG");break;}
                _=>panic!("unexpected topic {topic}"),
            }
        }
        assert_eq!(received,vec!["asset/begin","asset/raw-chunk","asset/file","asset/commit","widget/chunk","firmware/chunk","audio/control","audio/play_chunk"]);
    });
    let manager=UsbSerialManager::new();manager.set_desktop_device_id("desktop-fixture");
    let (tx,rx)=mpsc::channel();manager.connect_wifi(&identity,address,false,move|topic,payload|{let _=tx.send((topic,payload));}).unwrap();
    assert_eq!(manager.status().transport,"wifi");
    manager.send_asset_begin_checked("raw-fixture",8192).unwrap();
    let raw:Vec<u8>=(0..8192).map(|n|(n%251)as u8).collect();
    manager.send_asset_raw_chunk_once("raw-fixture","p4/families/idle.default.h264",&raw,0).unwrap();
    manager.send_asset_file_commit_checked("raw-fixture","p4/families/idle.default.h264",8192,&asset_checksum_hex(&raw),1).unwrap();
    manager.send_asset_commit_checked("raw-fixture",1,8192).unwrap();
    let widget=manager.register_widget_ack_waiter("widget-fixture","chunk",Some("runtime/widget.json"),Some(0)).unwrap();
    manager.send_to_board("s3-shared","widget/chunk",&serde_json::json!({"transferId":"widget-fixture","path":"runtime/widget.json","index":0,"data":"e30="})).unwrap();
    assert_eq!(widget.recv_timeout(Duration::from_secs(2)).unwrap()["ok"],true);
    let generation=manager.connection.lock().unwrap().as_ref().unwrap().connection_id;
    manager.send_firmware_command_and_wait("s3-shared",generation,"firmware/chunk",&serde_json::json!({"transferId":"firmware-fixture","seq":0,"data":"AQID"}),"firmware-fixture","chunk",1,3,Duration::from_secs(2)).unwrap();
    manager.send_to_board("s3-shared","audio/control",&serde_json::json!({"action":"start"})).unwrap();
    let deadline=Instant::now()+Duration::from_secs(2);let mut capture=false;
    while Instant::now()<deadline {let (topic,payload)=rx.recv_timeout(Duration::from_secs(2)).unwrap();if topic=="audio/chunk"{assert_eq!(payload["data"],"AQID");capture=true;break;}}
    assert!(capture);
    manager.send_to_board("s3-shared","audio/play_chunk",&serde_json::json!({"sessionId":"play-test","data":"BAUG"})).unwrap();
    server.join().unwrap();
}
