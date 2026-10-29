//! Per-board public identity, encrypted pairing credentials and user preference.
use crate::wifi_transport::WifiIdentity;
use serde::{Deserialize, Serialize};
use std::net::{IpAddr, SocketAddr};
use std::path::Path;
use std::sync::Mutex;

pub(crate) const FILE_NAME: &str = "wifi-devices.secure.json";
pub(crate) static STORE_LOCK: Mutex<()> = Mutex::new(());
const PURPOSE: &str = "wifi-devices";

#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct SavedDevice {
    pub identity: WifiIdentity,
    pub ip: String,
    pub port: u16,
    pub usb_port: String,
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", default)]
pub(crate) struct Settings {
    pub preferred_transport: String,
    pub selected_board_device_id: String,
    pub devices: Vec<SavedDevice>,
}
impl Default for Settings {
    fn default() -> Self { Self { preferred_transport: "usb".into(), selected_board_device_id: String::new(), devices: Vec::new() } }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct DeviceInfo {
    pub board_device_id: String,
    pub ip: String,
    pub port: u16,
    pub hostname: String,
    pub paired: bool,
}

impl Settings {
    pub fn public_devices(&self) -> Vec<DeviceInfo> {
        self.devices.iter().map(|d| DeviceInfo { board_device_id:d.identity.board_device_id.clone(), ip:d.ip.clone(),port:d.port,hostname:d.identity.hostname.clone(),paired:true }).collect()
    }
    pub fn accept_pairing(&mut self, board: &str, usb_port: &str, value: &serde_json::Value) -> Result<(),String> {
        use rustls::pki_types::{pem::PemObject, CertificateDer};
        let id=value["boardDeviceId"].as_str().unwrap_or_default();
        let hostname=value["hostname"].as_str().unwrap_or_default();
        let token=value["token"].as_str().unwrap_or_default();
        let certificate=value["certificatePem"].as_str().unwrap_or_default();
        if value["ok"] != true || board.is_empty() || board != id || hostname != format!("{id}.local")
            || token.len()!=64 || !token.bytes().all(|b| b.is_ascii_hexdigit()) || certificate.len()>8192 {
            return Err("设备配对资料无效，原绑定已保留".into());
        }
        CertificateDer::from_pem_slice(certificate.as_bytes()).map_err(|_| "设备配对证书无效")?;
        let ip=value["ip"].as_str().unwrap_or_default().to_string();
        let port=value["port"].as_u64().unwrap_or(48973);
        if port!=48973 { return Err("设备服务端口不受支持".into()); }
        if !ip.is_empty() && ip!="0.0.0.0" { endpoint(&ip,48973)?; }
        let device=SavedDevice { identity:WifiIdentity { board_device_id:id.into(),hostname:hostname.into(),certificate_pem:certificate.into(),token:token.to_ascii_lowercase() }, ip,port:48973,usb_port:usb_port.into() };
        if let Some(old)=self.devices.iter_mut().find(|d|d.identity.board_device_id==id) { *old=device; }
        else if self.devices.len()<16 { self.devices.push(device); }
        else { return Err("最多保存 16 台无线设备，请先清除旧绑定".into()); }
        self.selected_board_device_id=id.into();
        Ok(())
    }
}

pub(crate) fn load(root: &Path) -> Result<Settings,String> {
    let raw=crate::secure_config::read(&root.join(FILE_NAME),PURPOSE)?;
    let settings:Settings=raw.map(|s|serde_json::from_str(&s).map_err(|_|"无线配置损坏，原文件已保留".to_string())).transpose()?.unwrap_or_default();
    if !matches!(settings.preferred_transport.as_str(),"usb"|"wifi") || settings.devices.len()>16 {
        return Err("无线配置无效，原文件已保留".into());
    }
    Ok(settings)
}
pub(crate) fn save(root: &Path, settings: &Settings) -> Result<(),String> {
    let raw=serde_json::to_vec(settings).map_err(|_|"无线配置编码失败")?;
    crate::secure_config::write(&root.join(FILE_NAME),PURPOSE,&raw)
}

pub(crate) fn endpoint(ip: &str, port: u16) -> Result<SocketAddr,String> {
    let address:IpAddr=ip.trim().parse().map_err(|_|"请输入设备的局域网 IP 地址")?;
    let local=match address {
        IpAddr::V4(v)=>v.is_private()||v.is_loopback()||v.is_link_local(),
        IpAddr::V6(v)=>v.is_loopback()||v.is_unique_local()||v.is_unicast_link_local(),
    };
    if !local || address.is_unspecified() || address.is_multicast() || port==0 {
        return Err("仅支持局域网单播地址".into());
    }
    Ok(SocketAddr::new(address,port))
}

#[cfg(test)]
#[path="wifi_devices_tests.rs"]
mod tests;
