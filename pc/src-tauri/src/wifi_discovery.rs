//! Bounded mDNS service discovery; results are addresses, never trust anchors.
use std::{collections::HashMap, net::{Ipv4Addr, SocketAddr, UdpSocket}, time::{Duration, Instant}};

#[derive(Default)]
struct Records {
    services: HashMap<String,u16>,
    addresses: HashMap<String,Ipv4Addr>,
}

fn u16_at(data:&[u8], at:usize)->Result<u16,()> { Ok(u16::from_be_bytes(data.get(at..at+2).ok_or(())?.try_into().map_err(|_|())?)) }

fn dns_name(data:&[u8], at:&mut usize)->Result<String,()> {
    let mut cursor=*at; let mut jumped=false; let mut out=Vec::new(); let mut total=0;
    for _ in 0..64 {
        let size=*data.get(cursor).ok_or(())?;
        if size&0xc0==0xc0 {
            let next=*data.get(cursor+1).ok_or(())?;
            if !jumped { *at=cursor+2; jumped=true; }
            cursor=(((size&0x3f) as usize)<<8)|next as usize;
            continue;
        }
        if size&0xc0!=0 { return Err(()); }
        cursor+=1;
        if size==0 { if !jumped { *at=cursor; } return Ok(out.join(".").to_ascii_lowercase()); }
        let label=data.get(cursor..cursor+size as usize).ok_or(())?;
        if !label.iter().all(|b|b.is_ascii_graphic() && *b!=b'.') { return Err(()); }
        total+=label.len()+1; if total>254 { return Err(()); }
        out.push(std::str::from_utf8(label).map_err(|_|())?.to_string());
        cursor+=size as usize;
    }
    Err(())
}

impl Records {
    fn parse(&mut self, packet:&[u8])->Result<(),()> {
        if packet.len()<12 || packet.len()>9000 || packet[2]&0x80==0 { return Err(()); }
        let questions=u16_at(packet,4)? as usize;
        let count=u16_at(packet,6)? as usize+u16_at(packet,8)? as usize+u16_at(packet,10)? as usize;
        if questions>32||count>128 { return Err(()); }
        let mut at=12;
        for _ in 0..questions { dns_name(packet,&mut at)?; at=at.checked_add(4).ok_or(())?; if at>packet.len(){return Err(());} }
        for _ in 0..count {
            let name=dns_name(packet,&mut at)?;
            let kind=u16_at(packet,at)?; let class=u16_at(packet,at+2)?&0x7fff;
            let ttl=u32::from_be_bytes(packet.get(at+4..at+8).ok_or(())?.try_into().map_err(|_|())?);
            let len=u16_at(packet,at+8)? as usize; at+=10;
            let end=at.checked_add(len).filter(|end|*end<=packet.len()).ok_or(())?;
            if class==1 && ttl>0 {
                if kind==1 && len==4 && self.addresses.len()<128 {
                    self.addresses.insert(name,Ipv4Addr::new(packet[at],packet[at+1],packet[at+2],packet[at+3]));
                } else if kind==33 && len>=7 && name.ends_with("._hachimodock._tcp.local") && self.services.len()<32 {
                    let port=u16_at(packet,at+4)?;
                    let mut target_at=at+6; let hostname=dns_name(packet,&mut target_at)?;
                    if target_at>end || port!=48973 || !hostname.ends_with(".local") { return Err(()); }
                    self.services.insert(hostname,port);
                }
            }
            at=end;
        }
        Ok(())
    }
    fn devices(&self)->HashMap<String,SocketAddr> {
        self.services.iter().filter_map(|(hostname,port)| {
            let ip=self.addresses.get(hostname)?;
            Some((hostname.clone(),crate::wifi_devices::endpoint(&ip.to_string(),*port).ok()?))
        }).collect()
    }
}

pub(crate) fn discover(timeout:Duration)->Result<HashMap<String,SocketAddr>,String> {
    let socket=UdpSocket::bind("0.0.0.0:0").map_err(|_|"无法打开局域网发现端口")?;
    socket.set_read_timeout(Some(Duration::from_millis(150))).map_err(|_|"无法设置发现超时")?;
    let mut query=vec![0,0,0,0,0,1,0,0,0,0,0,0];
    for label in ["_hachimodock","_tcp","local"] { query.push(label.len() as u8); query.extend_from_slice(label.as_bytes()); }
    query.extend_from_slice(&[0,0,12,0x80,1]); // PTR, QU: unicast response to this socket.
    socket.send_to(&query,"224.0.0.251:5353").map_err(|_|"局域网发现发送失败")?;
    let deadline=Instant::now()+timeout.min(Duration::from_secs(3));
    let mut records=Records::default(); let mut packet=[0u8;9000]; let mut packets=0;
    while Instant::now()<deadline && packets<64 {
        match socket.recv_from(&mut packet) {
            Ok((size,_))=>{ packets+=1;let _=records.parse(&packet[..size]); }
            Err(e) if matches!(e.kind(),std::io::ErrorKind::TimedOut|std::io::ErrorKind::WouldBlock)=>(),
            Err(_)=>return Err("局域网发现接收失败".into()),
        }
    }
    Ok(records.devices())
}

#[cfg(test)]
#[path="wifi_discovery_tests.rs"]
mod tests;
