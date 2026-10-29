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
