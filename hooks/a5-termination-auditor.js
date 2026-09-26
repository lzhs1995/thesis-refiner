#!/usr/bin/env node
'use strict';
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const chunks = [];
process.stdin.on('data', chunk => { chunks.push(chunk); });
process.stdin.on('end', () => {
  const bytes = Buffer.concat(chunks);
  const raw = bytes.toString('utf8');
  let input;
  try { input = raw.trim() ? JSON.parse(raw) : {}; } catch { process.exitCode = 2; return; }
  if (!input || Array.isArray(input) || typeof input !== 'object') {
    process.stderr.write('INVALID_HOOK_INPUT'); process.exitCode = 2; return;
  }
  function binding(key, envKey) {
    return Object.prototype.hasOwnProperty.call(input, key) ? input[key] : process.env[envKey];
  }
  const checkpoint = binding('workflow_checkpoint', 'THESIS_REFINER_CHECKPOINT');
  const delivery = binding('delivery_checkpoint', 'THESIS_REFINER_DELIVERY_CHECKPOINT');
  // 只审查显式绑定任务，不扫描其他章节状态或把旧回执继承为本次通过。
  if (checkpoint === undefined && delivery === undefined) { process.stdout.write(bytes); return; }
  const explicitRoot = process.env.THESIS_REFINER_ROOT;
  if (explicitRoot && !path.isAbsolute(explicitRoot)) {
    process.stderr.write('ABSOLUTE_SKILL_ROOT_REQUIRED'); process.exitCode = 2; return;
  }
  const root = explicitRoot || path.resolve(__dirname, '..');
  const jobs = [[checkpoint, 'workflow.py', ['acceptance']], [delivery, 'delivery_audit.py', []]];
  for (const [bound, scriptName, prefix] of jobs) {
    if (bound === undefined) continue;
    if (typeof bound !== 'string' || !path.isAbsolute(bound)) {
      process.stderr.write('ABSOLUTE_CHECKPOINT_REQUIRED'); process.exitCode = 2; return;
    }
    const script = path.join(root, 'scripts', scriptName);
    if (!fs.existsSync(script)) {
      process.stderr.write('SKILL_ENTRYPOINT_MISSING: ' + script); process.exitCode = 2; return;
    }
    const result = spawnSync(process.env.THESIS_PYTHON || 'python3',
      [script, ...prefix, '--input', bound], { encoding: 'utf8', timeout: 60000 });
    if (result.status !== 0 || result.error) {
      process.stderr.write('A5_NOT_COMPLETE: ' + (result.stdout || result.stderr || String(result.error)));
      process.exitCode = 2; return;
    }
  }
  process.stdout.write(bytes);
});
