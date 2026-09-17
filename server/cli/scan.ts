#!/usr/bin/env tsx
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ScanOrchestrator } from '../core/scan-orchestrator.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

const orch = new ScanOrchestrator({
  rootDir: ROOT,
  dataDir: path.join(ROOT, 'data'),
  intervalMs: 15_000,
});

await orch.init();
const result = await orch.runOnce();
console.log(JSON.stringify(result, null, 2));
process.exit(0);
