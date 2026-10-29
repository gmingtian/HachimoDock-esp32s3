import test from "node:test";
import assert from "node:assert/strict";
import { connectionLabel, wifiSetupState, configureInput } from "./wifi-settings.js";

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
