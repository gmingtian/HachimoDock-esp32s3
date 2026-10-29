use super::*;
use rustls::{ServerConfig, ServerConnection, StreamOwned};
use std::net::TcpListener;

fn fixture() -> (WifiIdentity, Arc<ServerConfig>) {
    let cert = rcgen::generate_simple_self_signed(vec!["s3-fixture.local".into()]).unwrap();
    let config = ServerConfig::builder_with_provider(Arc::new(rustls::crypto::ring::default_provider()))
        .with_safe_default_protocol_versions().unwrap()
        .with_no_client_auth()
        .with_single_cert(vec![cert.cert.der().clone()], rustls::pki_types::PrivatePkcs8KeyDer::from(cert.key_pair.serialize_der()).into()).unwrap();
    (WifiIdentity { board_device_id: "s3-fixture".into(), hostname:"s3-fixture.local".into(), certificate_pem:cert.cert.pem(), token:"ab".repeat(32) }, Arc::new(config))
}

fn peer(config: Arc<ServerConfig>, accept: bool) -> (SocketAddr, thread::JoinHandle<()>) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let worker = thread::spawn(move || {
        let (socket, _) = listener.accept().unwrap();
        socket.set_read_timeout(Some(Duration::from_secs(3))).unwrap();
        socket.set_write_timeout(Some(Duration::from_secs(3))).unwrap();
        let mut tls = StreamOwned::new(ServerConnection::new(config).unwrap(), socket);
        let auth = match read_json_line(&mut tls, 32768, Instant::now()+Duration::from_secs(3)) { Ok(auth)=>auth, Err(_)=>return };
        assert_eq!(auth["topic"], "wifi/auth");
        assert_eq!(auth["payload"]["expectedBoardDeviceId"], "s3-fixture");
        assert_eq!(auth["payload"]["token"], "ab".repeat(32));
        let response=serde_json::json!({"topic":"wifi/auth","payload":{"ok":accept,"boardDeviceId":"s3-fixture","requestId":auth["payload"]["requestId"],"error":"rejected"}});
        tls.write_all(format!("{response}\n").as_bytes()).unwrap();
        tls.flush().unwrap();
        if !accept { return; }
        let mut data=[0;6];
        tls.read_exact(&mut data).unwrap();
        assert_eq!(&data,b"\0\n\xffabc");
        for part in [b"{\"topic\":".as_slice(),b"\"audio/chunk\",\"payload\":{}}\n".as_slice()] {
            tls.write_all(part).unwrap(); tls.flush().unwrap();
        }
    });
    (address, worker)
}

#[test]
fn wifi_tls_preserves_binary_and_fragmented_json() {
    let (identity, config)=fixture();
    let (address, worker)=peer(config,true);
    let mut io=connect(&identity,address,"desktop-fixture",false).unwrap();
    io.writer.write_all(b"\0\n\xffabc").unwrap();
    let value=read_json_line(&mut io.reader,32768,Instant::now()+Duration::from_secs(3)).unwrap();
    assert_eq!(value["topic"],"audio/chunk");
    worker.join().unwrap();
}

#[test]
fn wifi_tls_rejects_other_certificate_before_sending_auth() {
    let (identity, _)=fixture(); let (_,config)=fixture();
    let (address,worker)=peer(config,true);
    assert!(connect(&identity,address,"desktop-fixture",false).is_err());
    worker.join().unwrap();
}

#[test]
fn wifi_tls_rejects_server_hostname_mismatch() {
    let (mut identity, config)=fixture();
    identity.hostname="other-board.local".into();
    let (address,worker)=peer(config,true);
    assert!(connect(&identity,address,"desktop-fixture",false).is_err());
    worker.join().unwrap();
}

#[test]
fn wifi_auth_failure_never_installs_runtime_stream() {
    let (identity,config)=fixture(); let (address,worker)=peer(config,false);
    assert!(connect(&identity,address,"desktop-fixture",false).is_err());
    worker.join().unwrap();
}

#[test]
fn wifi_json_limit_and_utf8_are_enforced_without_tail_reinterpretation() {
    assert!(read_json_line(&mut &b"123456789\n{}\n"[..],8,Instant::now()+Duration::from_secs(1)).is_err());
    assert!(read_json_line(&mut &b"\xff\n"[..],8,Instant::now()+Duration::from_secs(1)).is_err());
}

#[test]
fn wifi_cancellation_unblocks_reader_and_writer() {
    let (identity,config)=fixture();
    let (address,worker)=peer(config,true);
    let mut io=connect(&identity,address,"desktop-fixture",false).unwrap();
    io.writer.write_all(b"\0\n\xffabc").unwrap();
    worker.join().unwrap();
    io.cancel.store(true,Ordering::Release);
    assert!(io.writer.write_all(b"stale").is_err());
    assert!(io.reader.read(&mut [0;1]).is_err());
}
