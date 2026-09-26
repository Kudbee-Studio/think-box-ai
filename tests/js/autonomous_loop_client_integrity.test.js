/**
 * Runtime assertions for the autonomous-loop action-integrity renderer.
 *
 * Loads the real client file from public/control-plane with a minimal DOM stub
 * and drives TBAutonomousLoopClient.renderActionIntegrity() with the same shapes
 * returned by GET /api/v1/autonomous-loop/actions/integrity.
 *
 * Exit code 0 = all assertions passed.
 */

"use strict";

const path = require("path");

const CLIENT_PATH = path.join(
  __dirname,
  "..",
  "..",
  "public",
  "control-plane",
  "autonomous_loop_client.js"
);

const elements = {};
function el(id) {
  if (!elements[id]) {
    elements[id] = { id, textContent: "", className: "", style: {} };
  }
  return elements[id];
}

global.document = {
  getElementById: el,
  createElement: () => ({
    style: {},
    dataset: {},
    appendChild() {},
    addEventListener() {},
  }),
  querySelectorAll: () => [],
  querySelector: () => null,
  addEventListener() {},
};
global.window = { addEventListener() {} };
global.fetch = async () => ({ ok: false });
global.setInterval = () => 0;
global.clearInterval = () => {};

// The client is an IIFE that publishes its API onto window.
new Function(
  "window",
  "document",
  "fetch",
  "setInterval",
  "clearInterval",
  require("fs").readFileSync(CLIENT_PATH, "utf8")
)(global.window, global.document, global.fetch, global.setInterval, global.clearInterval);

const api = global.window.TBAutonomousLoopClient;
if (!api || typeof api.renderActionIntegrity !== "function") {
  console.error("FAIL: renderActionIntegrity not exported on TBAutonomousLoopClient");
  process.exit(1);
}

let failures = 0;
function check(label, actual, expected) {
  if (actual !== expected) {
    console.error(`FAIL ${label}\n  expected: ${expected}\n  actual:   ${actual}`);
    failures += 1;
  } else {
    console.log(`ok   ${label}`);
  }
}

const badge = () => el("integrityBadge");
const detail = () => el("integrityDetail");

// 1. Endpoint unavailable.
api.renderActionIntegrity(null);
check("offline badge", badge().textContent, "OFFLINE");
check("offline detail", detail().textContent, "Integrity endpoint unavailable");

// 2. Durability disabled -> must NOT claim a chain exists.
api.renderActionIntegrity({ attached: false });
check("not-attached badge", badge().textContent, "NOT ATTACHED");
check("not-attached detail", detail().textContent, "Durability disabled; actions are in-memory only");

// 3. Attached and valid.
api.renderActionIntegrity({ attached: true, count: 0, valid: true });
check("valid-empty badge", badge().textContent, "VALID");
check("valid-empty detail", detail().textContent, "0 persisted receipt(s), hash chain intact");

api.renderActionIntegrity({ attached: true, count: 3, valid: true });
check("valid-3 badge", badge().textContent, "VALID");
check("valid-3 detail", detail().textContent, "3 persisted receipt(s), hash chain intact");
check("valid-3 warning cleared", badge().style.background, "");

// 4. Tampered -> must be visually distinct.
api.renderActionIntegrity({ attached: true, count: 3, valid: false });
check("tampered badge", badge().textContent, "TAMPERED");
check("tampered detail", detail().textContent, "3 persisted receipt(s), hash chain BROKEN");
if (!badge().style.background) {
  console.error("FAIL tampered chain should carry a warning background");
  failures += 1;
} else {
  console.log("ok   tampered styling applied");
}

// 5. Recovery clears the warning styling again.
api.renderActionIntegrity({ attached: true, count: 4, valid: true });
check("recovered badge", badge().textContent, "VALID");
check("recovered background cleared", badge().style.background, "");
check("recovered color cleared", badge().style.color, "");
check("recovered detail", detail().textContent, "4 persisted receipt(s), hash chain intact");

if (failures > 0) {
  console.error(`\n${failures} assertion(s) failed`);
  process.exit(1);
}
console.log("\nAll integrity renderer assertions passed");
