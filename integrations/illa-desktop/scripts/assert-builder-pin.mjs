#!/usr/bin/env node
/**
 * Fail if package.json drifts off ILLA desktop packaging contracts.
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const { assertPackageContract, PIN } = require("../src/url-contract.js");

const pkgPath = path.join(here, "..", "package.json");
const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
const errors = assertPackageContract(pkg);

if (errors.length) {
  console.error(JSON.stringify({ ok: false, expected_pin: PIN, errors }, null, 2));
  process.exit(1);
}

console.log(
  JSON.stringify(
    {
      ok: true,
      electron_builder: pkg.devDependencies["electron-builder"],
      appId: pkg.build.appId,
      author_email: pkg.author.email,
      release:
        "https://github.com/electron-userland/electron-builder/releases/tag/electron-builder%4026.16.1",
    },
    null,
    2
  )
);
