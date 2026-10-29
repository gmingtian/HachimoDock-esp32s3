/** S3 USB provisioning and paired TLS network connection. Secrets never persist in UI storage. */
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { connectionLabel, configureInput, wifiSetupState, networkStateLabel } from "./lib/wifi-settings.js";

export default function WifiSettings({ status, boardDeviceId }) {
  const [settings, setSettings] = useState({ devices: [] });
  const [ssid, setSsid] = useState("");
  const [password, setPassword] = useState("");
  const [ip, setIp] = useState("");
  const [networks, setNetworks] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const board = status?.boardDeviceId || boardDeviceId || settings.selectedBoardDeviceId || "";
  const rules = wifiSetupState(status, settings);
  const paired = settings.devices?.some((device) => device.boardDeviceId === board);
  const refresh = useCallback(async () => {
    const next = await invoke("device_wifi_get_status");
    setSettings(next);
    return next;
  }, []);
  useEffect(() => {
    let mounted = true; let inFlight = false;
    const check = async () => {
      if (inFlight || busy) return;
      inFlight = true;
      try { const next = await invoke("device_wifi_get_status"); if (mounted) setSettings(next); }
      catch { /* Retain last status while a resource transaction owns the link. */ }
      finally { inFlight = false; }
    };
    check(); const timer = setInterval(check, 4000);
    return () => { mounted = false; clearInterval(timer); };
  }, [busy, status?.connected, status?.transport, status?.boardDeviceId]);
  const run = async (work, success) => {
    if (busy) return;
    setBusy(true); setMessage(""); setFailed(false);
    try { await work(); setMessage(success); await refresh(); }
    catch (error) { setFailed(true); setMessage(String(error?.message || error)); }
    finally { setBusy(false); }
  };
  const args = { expectedBoardDeviceId: board };
  const small = { display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" };
  const control = { padding: "9px 12px", border: "1px solid var(--border, #d9dde5)", borderRadius: 8, background: "var(--card-bg, #fff)", color: "inherit" };
  return <section aria-label="USB 与 Wi-Fi 连接" style={{ padding: 20, borderRadius: 14, border: "1px solid var(--border, #e0e3eb)", background: "var(--card-bg, #fff)" }}>
    <h3 style={{ margin: "0 0 10px" }}>设备连接</h3>
    <p>当前：<strong>{connectionLabel(status)}</strong>　偏好：{rules.preferredTransport === "wifi" ? "Wi-Fi" : "USB"}</p>
    <p style={{ fontSize: 13, opacity: 0.75 }}>记住所选连接，保持当前通道；Wi-Fi 断开后尝试 USB。录音、播放、同步和升级期间请先结束操作再切换。</p>
    {!rules.supported && status?.connected && <p role="status">当前设备需安装当前配套 S3 固件，才能启用无线连接。</p>}
    <div style={small}>
      <button style={control} disabled={busy || !board} onClick={() => run(() => invoke("device_set_transport_preference", { ...args, transport: "usb" }), "已使用 USB 连接")}>使用 USB</button>
      <button style={control} disabled={busy || !paired} onClick={() => run(() => invoke("device_wifi_connect", { ...args, ip: ip.trim() || null }), "已使用 Wi-Fi 连接")}>使用 Wi-Fi</button>
      <button style={control} disabled={busy} onClick={() => run(async () => { const found = await invoke("device_wifi_list_devices"); setSettings((s) => ({ ...s, devices: found.devices })); }, "已更新已绑定设备地址")}>查找无线设备</button>
      <input style={control} aria-label="设备局域网 IP" value={ip} onChange={(e) => setIp(e.target.value)} placeholder="设备 IP（发现失败时填写）" />
    </div>
    {settings.network && <p style={{ fontSize: 13 }}>网络：{settings.network.ssid || "未配网"}　{networkStateLabel(settings.network)}</p>}
    <details style={{ marginTop: 16 }}>
      <summary>Wi-Fi 配网与绑定（通过 USB）</summary>
      <p style={{ fontSize: 13 }}>连接设备 USB，填写 2.4GHz Wi-Fi。电脑和设备需处于可互访的局域网；其他电脑首次使用也需通过 USB 绑定。</p>
      <fieldset disabled={busy || !rules.canProvision} style={{ border: 0, padding: 0, margin: 0 }}>
        <div style={small}>
          <input aria-label="Wi-Fi 名称" style={control} value={ssid} onChange={(e) => setSsid(e.target.value)} list="device-wifi-networks" placeholder="Wi-Fi 名称（支持隐藏网络）" autoComplete="off" />
          <datalist id="device-wifi-networks">{networks.map((network, index) => <option key={`${network.ssid}-${index}`} value={network.ssid}>{network.rssi} dBm</option>)}</datalist>
          <input aria-label="Wi-Fi 密码" style={control} type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Wi-Fi 密码" autoComplete="new-password" />
          <button style={control} onClick={() => run(async () => { const found = await invoke("device_wifi_scan_networks", args); setNetworks(found.networks || []); }, "扫描完成")}>扫描网络</button>
          <button style={control} onClick={() => run(async () => { const input = configureInput(board, ssid, password); setPassword(""); await invoke("device_wifi_configure", input); }, "配网已提交，等待设备连接路由器")}>保存配网</button>
          <button style={control} onClick={() => run(() => invoke("device_wifi_pair", args), "此电脑已绑定无线设备")}>{paired ? "刷新此电脑绑定" : "绑定此电脑"}</button>
        </div>
        <div style={{ ...small, marginTop: 14 }}>
          <button style={control} onClick={() => run(() => invoke("device_wifi_set_enabled", { ...args, enabled: !settings.network?.enabled }), settings.network?.enabled ? "设备 Wi-Fi 已关闭" : "设备 Wi-Fi 已启用")}>{settings.network?.enabled ? "关闭设备 Wi-Fi" : "启用设备 Wi-Fi"}</button>
          {!confirmClear ? <button style={control} onClick={() => setConfirmClear(true)}>清除设备配网…</button> : <>
            <span>将删除网络并撤销所有电脑的无线绑定。</span>
            <button style={control} onClick={() => run(async () => { await invoke("device_wifi_clear", args); setConfirmClear(false); }, "配网和无线绑定已清除")}>确认清除</button>
            <button style={control} onClick={() => setConfirmClear(false)}>取消</button>
          </>}
        </div>
      </fieldset>
    </details>
    {busy && <p role="status">正在处理连接，请稍候…</p>}
    {message && <p role={failed ? "alert" : "status"} style={{ color: failed ? "#b42318" : "inherit" }}>{message}</p>}
  </section>;
}
