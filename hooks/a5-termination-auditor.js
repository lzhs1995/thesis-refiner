#!/usr/bin/env node
'use strict';
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
let raw = '';
process.stdin.on('data', chunk => { raw += chunk; });
process.stdin.on('end', () => {
  let input;
  try { input = raw.trim() ? JSON.parse(raw) : {}; } catch { process.exitCode = 2; return; }
  const checkpoint = input.workflow_checkpoint || process.env.THESIS_REFINER_CHECKPOINT;
  // 只审查显式绑定任务，不扫描其他章节状态或把旧回执继承为本次通过。
  if (!checkpoint) { process.stdout.write(raw); return; }
  const script = path.resolve(__dirname, '../scripts/workflow.py');
  const result = spawnSync(process.env.THESIS_PYTHON || 'python3',
    [script, 'acceptance', '--input', path.resolve(checkpoint)], { encoding: 'utf8' });
  if (result.status !== 0) {
    process.stderr.write('A5_NOT_COMPLETE: ' + (result.stdout || result.stderr));
    process.exitCode = 2;
  } else { process.stdout.write(raw); }
});
