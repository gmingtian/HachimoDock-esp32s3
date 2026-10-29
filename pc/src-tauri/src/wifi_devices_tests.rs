use super::*;

#[test]
fn wifi_store_encrypts_tokens_and_preserves_explicit_preference() {
    let root=tempfile::tempdir().unwrap();
    let mut settings=Settings::default();
    settings.preferred_transport="wifi".into();
    settings.selected_board_device_id="s3-fixture".into();
    settings.devices.push(SavedDevice { identity:crate::wifi_transport::WifiIdentity {
        board_device_id:"s3-fixture".into(),hostname:"s3-fixture.local".into(),certificate_pem:"public-cert".into(),token:"secret-fixture".into()
    }, ip:"192.168.1.20".into(),port:48973,usb_port:"/dev/ttyACM0".into() });
    save(root.path(), &settings).unwrap();
    let disk=std::fs::read_to_string(root.path().join(FILE_NAME)).unwrap();
    assert!(!disk.contains("secret-fixture"));
    let loaded=load(root.path()).unwrap();
    assert_eq!(loaded.preferred_transport,"wifi");
    assert_eq!(loaded.devices[0].identity.token,"secret-fixture");
    let status=serde_json::to_string(&loaded.public_devices()).unwrap();
    assert!(!status.contains("secret-fixture"));
    assert!(!status.contains("certificatePem"));
}

#[test]
fn wifi_pairing_rejects_wrong_board_or_invalid_credentials_without_replacing_original() {
    let mut settings=Settings::default();
    let invalid=serde_json::json!({"ok":true,"boardDeviceId":"other","hostname":"other.local","token":"ab".repeat(32),"certificatePem":"invalid"});
    assert!(settings.accept_pairing("s3-bound","/dev/ttyACM0",&invalid).is_err());
    assert!(settings.devices.is_empty());
}

#[test]
fn wifi_endpoints_reject_urls_and_multicast_and_accept_local_ip() {
    assert!(endpoint("https://192.168.1.2",48973).is_err());
    assert!(endpoint("224.0.0.251",48973).is_err());
    assert!(endpoint("8.8.8.8",48973).is_err());
    assert_eq!(endpoint("192.168.1.2",48973).unwrap().to_string(),"192.168.1.2:48973");
}
