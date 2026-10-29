import test from "node:test";
import assert from "node:assert/strict";
import { connectionLabel, wifiSetupState, configureInput, networkStateLabel } from "./wifi-settings.js";

test("active Wi-Fi remains distinct from remembered USB preference", () => {
  assert.equal(connectionLabel({ connected: true, transport: "wifi" }), "Wi-Fi");
  const state = wifiSetupState({ connected: true, transport: "wifi", runtime: "esp-s3", capabilities: { transport: { wifi: true } } }, { preferredTransport: "usb", devices: [{ boardDeviceId: "s3-a" }] });
  assert.equal(state.canProvision, false);
  assert.equal(state.preferredTransport, "usb");
  assert.equal(state.activeTransport, "wifi");
});

test("old USB firmware cannot accidentally expose network configuration", () => {
  assert.equal(wifiSetupState({ connected: true, transport: "usb", runtime: "esp-s3" }, {}).canProvision, false);
  assert.equal(wifiSetupState({ connected: true, transport: "usb", runtime: "esp-s3", capabilities: { transport: { wifi: true } } }, {}).canProvision, true);
});

test("hidden SSIDs preserve literal whitespace and invalid UTF-8 byte budgets fail", () => {
  assert.deepEqual(configureInput("s3-a", "  hidden  ", "password"), { expectedBoardDeviceId: "s3-a", ssid: "  hidden  ", password: "password" });
  assert.throws(() => configureInput("s3-a", "中".repeat(11), "password"));
  assert.throws(() => configureInput("", "wifi", "password"));
});

test("wrong password and disabled Wi-Fi cannot masquerade as waiting to connect", () => {
  assert.equal(networkStateLabel({ state: "wrong_password", configured: true }), "密码错误，请通过 USB 修改配网");
  assert.equal(networkStateLabel({ state: "disabled", configured: true }), "Wi-Fi 已关闭");
  assert.equal(networkStateLabel({ state: "disconnected", configured: true }), "未连接路由器，请检查网络与信号");
});
