#!/usr/bin/env node
'use strict';
const path = require('path');
const { spawnSync } = require('child_process');

class VerificationRouter {
  async verify() {
    throw new Error('LOCAL_EVIDENCE_REQUIRED: use a domain tool and save its real receipt');
  }
}

class ClosedLoopOrchestrator {
  constructor(options = {}) { this.options = options; }
  async runClosedLoop() {
    if (this.options.dryRun === true) {
      return { mode: 'simulation', status: 'SIMULATION_ONLY', A5_credit: false };
    }
    if (!this.options.checkpointPath) {
      throw new Error('REAL_RECEIPTS_REQUIRED: --checkpoint must name a complete evidence checkpoint');
    }
    const script = path.resolve(__dirname, '../../scripts/workflow.py');
    const result = spawnSync(this.options.python || process.env.THESIS_PYTHON || 'python3',
      [script, 'acceptance', '--input', path.resolve(this.options.checkpointPath)],
      { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 });
    if (result.error) throw result.error;
    let audit;
    try { audit = JSON.parse(result.stdout); }
    catch { throw new Error(`AUDIT_PROCESS_FAILED: ${result.stderr || result.stdout}`); }
    return { ...audit, mode: 'receipt_driven', A5_credit: audit.status === 'COMPLETE' };
  }
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const index = args.indexOf('--checkpoint');
  const options = { checkpointPath: index >= 0 ? args[index + 1] : undefined,
    dryRun: args.includes('--dry-run') && args[args.indexOf('--dry-run') + 1] !== 'false' };
  new ClosedLoopOrchestrator(options).runClosedLoop().then(result => {
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
    process.exitCode = result.status === 'COMPLETE' ? 0 : 2;
  }).catch(error => {
    process.stdout.write(JSON.stringify({ status: 'INCOMPLETE', error: error.message, A5_credit: false }) + '\n');
    process.exitCode = 2;
  });
}
module.exports = { ClosedLoopOrchestrator, VerificationRouter };
