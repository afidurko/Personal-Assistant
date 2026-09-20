#!/usr/bin/env node
/**
 * Fast property checks for url-contract.js (used by trillion fuzzer via subprocess too).
 */
const assert = require("node:assert/strict");
const {
  targetUrl,
  offlineHtml,
  escapeHtml,
  assertPackageContract,
  DEFAULT_SELF_HOST,
  CLOUD_URL,
  PIN,
  APP_ID,
} = require("../src/url-contract.js");
const pkg = require("../package.json");

assert.equal(targetUrl({}), DEFAULT_SELF_HOST);
assert.equal(targetUrl({ ILLA_DESKTOP_MODE: "cloud" }), CLOUD_URL);
assert.equal(targetUrl({ ILLA_DESKTOP_URL: "https://example.com/app" }), "https://example.com/app");
assert.equal(targetUrl({ ILLA_DESKTOP_URL: "ftp://bad" }), DEFAULT_SELF_HOST);
assert.equal(targetUrl({ ILLA_DESKTOP_URL: "not a url" }), DEFAULT_SELF_HOST);
assert.equal(targetUrl({ ILLA_DESKTOP_URL: "  https://x.test/y  " }), "https://x.test/y");

const html = offlineHtml('<script>alert(1)</script>', 'a&b<"\'');
assert.ok(!html.includes("<script>"));
assert.ok(html.includes("&lt;script&gt;"));
assert.ok(html.includes("&amp;"));
assert.ok(html.includes("&quot;") || html.includes("&#39;"));
assert.equal(escapeHtml("&"), "&amp;");

const errs = assertPackageContract(pkg);
assert.deepEqual(errs, []);
assert.equal(pkg.devDependencies["electron-builder"], PIN);
assert.equal(pkg.build.appId, APP_ID);

console.log(JSON.stringify({ ok: true, checks: 10 }, null, 2));
