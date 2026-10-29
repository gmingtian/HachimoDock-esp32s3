import test from "node:test";
import assert from "node:assert/strict";
import { componentSupportedOnTarget, filterTargetComponents } from "./s3-components.js";

test("S3 keeps directly playable games and removes controls needing more than three keys", () => {
  const items = ["snake-turn", "block-combo", "two-key-pong", "fresh-fruit-slice", "cloud-hop", "flappy-bird", "bloomfrog_companion", "city-radio", "my-custom-widget"].map((id) => ({ id }));
  assert.deepEqual(filterTargetComponents(items, "esp-s3").map((x) => x.id), ["snake-turn", "two-key-pong", "flappy-bird", "city-radio", "my-custom-widget"]);
  assert.equal(componentSupportedOnTarget("fresh-fruit-slice", "esp-p4"), true);
  assert.equal(filterTargetComponents(items, "esp-p4").length, 9);
});
