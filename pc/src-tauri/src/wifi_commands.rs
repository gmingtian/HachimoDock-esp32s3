//! Device Wi-Fi operations. Legacy host-computer Wi-Fi commands stay separate.
use crate::{usb_serial::UsbSerialManager, wifi_devices::{self, Settings}};
use serde_json::{json, Value};
use std::{path::PathBuf, sync::atomic::{AtomicBool,Ordering}, time::Duration};
use tauri::Manager;

static CONNECTING:AtomicBool=AtomicBool::new(false);
pub(crate) struct SwitchGuard;
impl Drop for SwitchGuard { fn drop(&mut self){ CONNECTING.store(false,Ordering::Release); } }
pub(crate) fn begin_switch()->Result<SwitchGuard,String> {
    CONNECTING.compare_exchange(false,true,Ordering::AcqRel,Ordering::Acquire).map_err(|_|"正在切换连接，请稍候")?;
    Ok(SwitchGuard)
}
pub(crate) fn connection_attempt_active()->bool { CONNECTING.load(Ordering::Acquire) }
fn root(app:&tauri::AppHandle)->Result<PathBuf,String> { app.path().app_data_dir().map_err(|_|"无线配置目录不可用".into()) }
fn settings(app:&tauri::AppHandle)->Result<Settings,String> { wifi_devices::load(&root(app)?) }
fn update(app:&tauri::AppHandle, change:impl FnOnce(&mut Settings)->Result<(),String>)->Result<Settings,String> {
    let _guard=wifi_devices::STORE_LOCK.lock().map_err(|_|"无线配置繁忙")?;
    let dir=root(app)?; let mut saved=wifi_devices::load(&dir)?; change(&mut saved)?; wifi_devices::save(&dir,&saved)?; Ok(saved)
}

fn require_usb(manager:&UsbSerialManager,board:&str)->Result<(),String> {
    let status=manager.status();
    if !status.connected||status.transport!="usb"||status.board_device_id!=board||status.runtime!="esp-s3" {
        return Err("请先通过 USB 连接目标 ESP32-S3".into());
    }
    if status.capabilities.pointer("/transport/wifi").and_then(Value::as_bool)!=Some(true) {
        return Err("当前固件未启用 Wi-Fi，请先升级 S3 r3 或更新版本".into());
    }
    manager.ensure_transport_switch_idle()
}

pub(crate) fn release_current(manager:&UsbSerialManager)->Result<(),String> {
    manager.ensure_transport_switch_idle()?;
    let status=manager.status();
    if status.connected && status.capabilities.pointer("/transport/wifi").and_then(Value::as_bool)==Some(true) {
        manager.maintenance_request(&status.board_device_id,"transport/release","transport/status",json!({}))?;
    }
    manager.disconnect();
    Ok(())
}

pub(crate) fn connect_board(app:&tauri::AppHandle,manager:&UsbSerialManager,board:&str,ip:Option<String>,explicit:bool)->Result<(),String> {
    let saved=settings(app)?;
    let device=saved.devices.iter().find(|d|d.identity.board_device_id==board).ok_or("此电脑尚未配对该设备，请先通过 USB 绑定")?.clone();
    let current=manager.status();
    if current.connected && current.board_device_id==board && current.transport=="wifi" { return Ok(()); }
    if !explicit && current.connected { return Err("已有活动连接".into()); }
    // Resolve the destination before releasing a working USB session.
    let address=if let Some(ip)=ip.filter(|s|!s.trim().is_empty()) {
        wifi_devices::endpoint(&ip,device.port)?
    } else {
        let discovered=crate::wifi_discovery::discover(Duration::from_millis(if explicit {1200}else{350})).unwrap_or_default();
        discovered.get(&device.identity.hostname).copied().or_else(||wifi_devices::endpoint(&device.ip,device.port).ok()).ok_or("未发现已绑定设备，请确认同一局域网或填写设备 IP")?
    };
    if explicit { release_current(manager)?; }
    let emitter=app.clone();
    manager.connect_wifi(&device.identity,address,explicit,move|topic,payload|crate::handle_incoming_usb_message(&emitter,topic,payload))?;
    update(app,|saved|{
        if explicit { saved.preferred_transport="wifi".into(); saved.selected_board_device_id=board.into(); }
        if let Some(d)=saved.devices.iter_mut().find(|d|d.identity.board_device_id==board){d.ip=address.ip().to_string();}
        Ok(())
    })?;
    crate::forward_current_state_after_usb_connect(manager)?;
    Ok(())
}

pub(crate) fn reconnect_after_update(app:&tauri::AppHandle,manager:&UsbSerialManager,board:&str)->Result<(),String> {
    let saved=settings(app)?;
    let device=saved.devices.iter().find(|d|d.identity.board_device_id==board).ok_or("升级设备无线绑定已丢失")?;
    let found=crate::wifi_discovery::discover(Duration::from_millis(700)).unwrap_or_default();
    let address=found.get(&device.identity.hostname).copied().or_else(||wifi_devices::endpoint(&device.ip,device.port).ok()).ok_or("等待升级设备重新上线")?;
    let emitter=app.clone();
    manager.reconnect_wifi_after_update(&device.identity,address,move|topic,payload|crate::handle_incoming_usb_message(&emitter,topic,payload))
}

pub(crate) fn prefers_wifi(app:&tauri::AppHandle,board:&str)->bool {
    settings(app).is_ok_and(|s|s.preferred_transport=="wifi"&&s.selected_board_device_id==board)
}
pub(crate) fn preferred_board(app:&tauri::AppHandle)->Option<String> {
    settings(app).ok().map(|s|s.selected_board_device_id).filter(|s|!s.is_empty())
}
pub(crate) fn remember_usb(app:&tauri::AppHandle,board:&str)->Result<(),String> {
    update(app,|s|{s.preferred_transport="usb".into();s.selected_board_device_id=board.into();Ok(())})?;
    Ok(())
}
pub(crate) fn try_preferred_wifi(app:&tauri::AppHandle,manager:&UsbSerialManager)->bool {
    if connection_attempt_active()||manager.status().connected{return false;}
    let Ok(saved)=settings(app) else{return false;};
    if saved.preferred_transport!="wifi"||saved.selected_board_device_id.is_empty(){return false;}
    let Ok(_guard)=begin_switch() else{return false;};
    connect_board(app,manager,&saved.selected_board_device_id,None,false).is_ok()
}

#[tauri::command]
pub async fn device_wifi_get_status(app:tauri::AppHandle,manager:tauri::State<'_,UsbSerialManager>)->Result<Value,String> {
    let manager=manager.inner().clone();
    tauri::async_runtime::spawn_blocking(move||{
        let saved=settings(&app)?;let active=manager.status();
        let supported=active.capabilities.pointer("/transport/wifi").and_then(Value::as_bool)==Some(true);
        let network=if active.connected&&supported&&manager.ensure_transport_switch_idle().is_ok(){
            manager.maintenance_request(&active.board_device_id,"wifi/status","wifi/status",json!({})).ok()
        } else{None};
        Ok(json!({"preferredTransport":saved.preferred_transport,"selectedBoardDeviceId":saved.selected_board_device_id,
            "devices":saved.public_devices(),"activeTransport":if active.connected{active.transport}else{String::new()},
            "connected":active.connected,"boardDeviceId":active.board_device_id,"supportsWifi":supported,"network":network}))
    }).await.map_err(|_|"读取无线状态失败")?
}

#[tauri::command]
pub async fn device_wifi_scan_networks(manager:tauri::State<'_,UsbSerialManager>,expected_board_device_id:String)->Result<Value,String> {
    let manager=manager.inner().clone();tauri::async_runtime::spawn_blocking(move||{
        require_usb(&manager,&expected_board_device_id)?;
        manager.maintenance_request(&expected_board_device_id,"wifi/scan","wifi/scan",json!({}))
    }).await.map_err(|_|"扫描设备网络失败")?
}

#[tauri::command]
pub async fn device_wifi_configure(manager:tauri::State<'_,UsbSerialManager>,expected_board_device_id:String,ssid:String,password:String)->Result<Value,String> {
    let manager=manager.inner().clone();tauri::async_runtime::spawn_blocking(move||{
        require_usb(&manager,&expected_board_device_id)?;
        if ssid.is_empty()||ssid.len()>32||password.len()>64{return Err("SSID 或密码长度无效".into());}
        manager.maintenance_request(&expected_board_device_id,"wifi/configure","wifi/status",json!({"ssid":ssid,"password":password,"enabled":true}))
    }).await.map_err(|_|"设备配网失败")?
}

#[tauri::command]
pub async fn device_wifi_pair(app:tauri::AppHandle,manager:tauri::State<'_,UsbSerialManager>,expected_board_device_id:String)->Result<Value,String> {
    let manager=manager.inner().clone();tauri::async_runtime::spawn_blocking(move||{
        require_usb(&manager,&expected_board_device_id)?;
        let pair=manager.maintenance_request(&expected_board_device_id,"wifi/pair","wifi/pair",json!({}))?;
        let port=manager.status().port_name;
        let saved=update(&app,|s|s.accept_pairing(&expected_board_device_id,&port,&pair))?;
        Ok(json!({"ok":true,"devices":saved.public_devices()}))
    }).await.map_err(|_|"无线绑定失败")?
}

#[tauri::command]
pub async fn device_wifi_list_devices(app:tauri::AppHandle)->Result<Value,String> {
    tauri::async_runtime::spawn_blocking(move||{
        let discovered=crate::wifi_discovery::discover(Duration::from_millis(1200))?;
        let saved=update(&app,|s|{for d in &mut s.devices{if let Some(address)=discovered.get(&d.identity.hostname){d.ip=address.ip().to_string();}}Ok(())})?;
        let devices:Vec<_>=saved.public_devices().into_iter().map(|d|{let online=discovered.contains_key(&d.hostname);json!({"boardDeviceId":d.board_device_id,"ip":d.ip,"port":d.port,"paired":true,"discovered":online})}).collect();
        Ok(json!({"devices":devices}))
    }).await.map_err(|_|"查找无线设备失败")?
}

#[tauri::command]
pub async fn device_wifi_connect(app:tauri::AppHandle,manager:tauri::State<'_,UsbSerialManager>,expected_board_device_id:String,ip:Option<String>)->Result<crate::usb_serial::UsbConnectionStatus,String> {
    let manager=manager.inner().clone();tauri::async_runtime::spawn_blocking(move||{
        let _guard=begin_switch()?;
        connect_board(&app,&manager,&expected_board_device_id,ip,true)?;
        Ok(manager.status())
    }).await.map_err(|_|"无线连接失败")?
}

#[tauri::command]
pub async fn device_wifi_set_enabled(manager:tauri::State<'_,UsbSerialManager>,expected_board_device_id:String,enabled:bool)->Result<Value,String> {
    let manager=manager.inner().clone();tauri::async_runtime::spawn_blocking(move||{
        require_usb(&manager,&expected_board_device_id)?;
        manager.maintenance_request(&expected_board_device_id,"wifi/set_enabled","wifi/status",json!({"enabled":enabled}))
    }).await.map_err(|_|"设置设备无线开关失败")?
}

#[tauri::command]
pub async fn device_wifi_clear(app:tauri::AppHandle,manager:tauri::State<'_,UsbSerialManager>,expected_board_device_id:String)->Result<Value,String> {
    let manager=manager.inner().clone();tauri::async_runtime::spawn_blocking(move||{
        require_usb(&manager,&expected_board_device_id)?;
        manager.maintenance_request(&expected_board_device_id,"wifi/clear","wifi/status",json!({}))?;
        update(&app,|s|{s.devices.retain(|d|d.identity.board_device_id!=expected_board_device_id);s.preferred_transport="usb".into();Ok(())})?;
        Ok(json!({"ok":true}))
    }).await.map_err(|_|"清除设备配网失败")?
}

#[tauri::command]
pub async fn device_set_transport_preference(app:tauri::AppHandle,manager:tauri::State<'_,UsbSerialManager>,expected_board_device_id:String,transport:String)->Result<crate::usb_serial::UsbConnectionStatus,String> {
    let manager=manager.inner().clone();tauri::async_runtime::spawn_blocking(move||{
        let _guard=begin_switch()?;
        match transport.as_str(){
            "wifi"=>connect_board(&app,&manager,&expected_board_device_id,None,true)?,
            "usb"=>{
                manager.ensure_transport_switch_idle()?;
                let current=manager.status();
                if !current.connected||current.transport!="usb"||current.board_device_id!=expected_board_device_id {
                    release_current(&manager)?;
                    let mut last="未找到目标 USB 设备".to_string();let mut connected=false;
                    for device in manager.scan_devices(){
                        let emitter=app.clone();
                        match manager.connect_expected(&device.port_name,&expected_board_device_id,false,move|t,p|crate::handle_incoming_usb_message(&emitter,t,p)){
                            Ok(())=>{connected=true;break;},Err(e)=>last=e,
                        }
                    }
                    if !connected{return Err(last);}
                }
                update(&app,|s|{s.preferred_transport="usb".into();s.selected_board_device_id=expected_board_device_id.clone();Ok(())})?;
                crate::forward_current_state_after_usb_connect(&manager)?;
            }
            _=>return Err("连接方式必须为 USB 或 Wi-Fi".into()),
        }
        Ok(manager.status())
    }).await.map_err(|_|"切换设备连接失败")?
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn wifi_connection_attempt_serializes_background_probe_with_manual_switch() {
        let active=begin_switch().unwrap();
        let concurrent=std::thread::spawn(||begin_switch().is_err()).join().unwrap();
        assert!(concurrent,"background attempt must not enter a manual switch");
        drop(active);
        assert!(begin_switch().is_ok(),"completed attempt must release priority lock");
    }
}
