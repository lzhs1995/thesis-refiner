#!/usr/bin/env node
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

class NLMUnifiedClient {
  constructor(options = {}) {
    this.binding = options.bindingPath || process.env.THESIS_NLM_BINDING;
    if (!this.binding) throw new Error('EXISTING_NLM_BINDING_REQUIRED');
    this.context = options.context || {};
    this.python = options.python || process.env.THESIS_PYTHON || 'python3';
    this.stateRoot = options.stateRoot;
  }
  async _call(operation, fields = {}) {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'thesis-nlm-request-'));
    const input = path.join(dir, 'request.json');
    fs.writeFileSync(input, JSON.stringify({ ...this.context, ...fields, operation }));
    const args = [path.resolve(__dirname, '../../scripts/nlm_runtime.py'), 'run',
      '--binding', path.resolve(this.binding), '--input', input];
    if (this.stateRoot) args.push('--root', this.stateRoot);
    try {
      const proc = spawnSync(this.python, args, { encoding: 'utf8', maxBuffer: 50 * 1024 * 1024 });
      if (proc.error) throw proc.error;
      const result = JSON.parse(proc.stdout);
      if (proc.status !== 0) throw new Error(`NLM_CALL_INCOMPLETE: ${JSON.stringify(result)}`);
      const receipt = JSON.parse(fs.readFileSync(result.receipt.path, 'utf8'));
      const data = JSON.parse(fs.readFileSync(receipt.raw_answer.path, 'utf8'));
      return { backend: 'pinned-existing-transport', data, receipt: result.receipt, cached: result.cached };
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  }
  notebookList() { return this._call('list'); }
  notebookQuery(notebookId, prompt, options = {}) {
    if (!options.sourceIds || !options.sourceIds.length) throw new Error('EXPLICIT_FROZEN_SOURCES_REQUIRED');
    return this._call('query', { notebook_id: notebookId, prompt, source_ids: options.sourceIds,
      round_id: options.roundId || this.context.round_id, document_sha256: options.documentSha256 || this.context.document_sha256 });
  }
  sourceAdd(notebookId, file) {
    const resolved = path.resolve(file);
    const bytes = fs.readFileSync(resolved);
    if (bytes.subarray(0, 5).toString() !== '%PDF-') throw new Error('PDF_UPLOAD_REQUIRED');
    return this._call('source_add', { notebook_id: notebookId, file: resolved,
      file_sha256: crypto.createHash('sha256').update(bytes).digest('hex') });
  }
  sourceGetFulltext(notebookId, sourceId) { return this._call('source_fulltext', { notebook_id: notebookId, source_id: sourceId }); }
  notebookCreate() { throw new Error('OPERATION_OUTSIDE_EXISTING_BINDING'); }
  notebookCopy() { throw new Error('COPY_CAPABILITY_NOT_VERIFIED'); }
  exportToGoogleDocs() { throw new Error('OPERATION_OUTSIDE_EXISTING_BINDING'); }
  batchOperation() { throw new Error('USE_ACCOUNT_QUEUE_FOR_EACH_REQUEST'); }
}
module.exports = NLMUnifiedClient;
module.exports.NLMUnifiedClient = NLMUnifiedClient;
