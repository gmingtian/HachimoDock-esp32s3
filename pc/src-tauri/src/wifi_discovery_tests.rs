use super::*;

fn name(text:&str)->Vec<u8> { let mut out=Vec::new(); for label in text.split('.') { out.push(label.len() as u8); out.extend_from_slice(label.as_bytes()); } out.push(0);out }
fn record(owner:&str,kind:u16,data:Vec<u8>)->Vec<u8> {
    let mut out=name(owner); out.extend(kind.to_be_bytes());out.extend(1u16.to_be_bytes());out.extend(120u32.to_be_bytes());out.extend((data.len() as u16).to_be_bytes());out.extend(data);out
}

#[test]
fn wifi_discovery_joins_srv_target_and_private_address() {
    let mut packet=vec![0,0,0x84,0,0,0,0,2,0,0,0,0];
    let mut srv=vec![0,0,0,0,0xbf,0x4d]; // 48973
    srv.extend(name("s3-fixture.local"));
    packet.extend(record("s3-fixture._hachimodock._tcp.local",33,srv));
    packet.extend(record("s3-fixture.local",1,vec![192,168,1,30]));
    let mut records=Records::default(); records.parse(&packet).unwrap();
    assert_eq!(records.devices().get("s3-fixture.local").unwrap().to_string(),"192.168.1.30:48973");
}

#[test]
fn wifi_discovery_rejects_pointer_cycles_and_truncated_record_lengths() {
    assert!(dns_name(&[0xc0,0],&mut 0).is_err());
    let mut packet=vec![0,0,0x84,0,0,0,0,1,0,0,0,0];
    packet.extend([0xc0,0xff]);
    assert!(Records::default().parse(&packet).is_err());
}
