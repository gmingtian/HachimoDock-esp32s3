/** Active transport and USB-only provisioning rules shared by device screens. */
export function connectionLabel(status) {
  return !status?.connected ? "未连接" : status.transport === "wifi" ? "Wi-Fi" : "USB";
}
export function wifiSetupState(status, settings) {
  const supported = status?.runtime === "esp-s3" && status?.capabilities?.transport?.wifi === true;
  return {
    activeTransport: status?.connected ? status.transport || "usb" : "",
    preferredTransport: settings?.preferredTransport === "wifi" ? "wifi" : "usb",
    canProvision: Boolean(status?.connected && supported && status?.transport !== "wifi"),
    supported,
  };
}
export function configureInput(board, ssid, password) {
  if (!board || !ssid || new TextEncoder().encode(ssid).length > 32 || new TextEncoder().encode(password).length > 64) {
    throw new Error("请输入有效的设备、Wi-Fi 名称和密码（名称最多 32 字节，密码最多 64 字节）");
  }
  return { expectedBoardDeviceId: board, ssid, password };
}
export function networkStateLabel(network) {
  if (!network?.configured) return "未配网";
  if (network.state === "wrong_password") return "密码错误，请通过 USB 修改配网";
  if (network.state === "disabled" || network.enabled === false) return "Wi-Fi 已关闭";
  if (network.connected) return `已连接 · ${network.ip || ""} · ${network.rssi ?? "—"} dBm`;
  return "未连接路由器，请检查网络与信号";
}
