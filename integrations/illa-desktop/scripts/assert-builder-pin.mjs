#!/usr/bin/env node
/**
 * Fail if package.json drifts off electron-builder@26.16.1.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PIN = "26.16.1";
const here = path.dirname(fileURLToPath(import.meta.url));
const pkgPath = path.join(here, "..", "package.json");
const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
const version = (pkg.devDependencies && pkg.devDependencies["electron-builder"]) || "";

if (version !== PIN) {
  console.error(
    JSON.stringify(
      {
        ok: false,
        expected: PIN,
        actual: version,
        message: "ILLA desktop must pin electron-builder exactly to 26.16.1",
      },
      null,
      2
    )
  );
  process.exit(1);
}

console.log(
  JSON.stringify(
    {
      ok: true,
      electron_builder: version,
      release:
        "https://github.com/electron-userland/electron-builder/releases/tag/electron-builder%4026.16.1",
    },
    null,
    2
  )
);
