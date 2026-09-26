# Thesis Refiner / 论文精炼助手

Current source: **2026.09.26.10**. Read the [toolchain lessons](references/toolchain-retrospective.md) and [manifest/link contract](references/delivery-manifest.md) for result assembly, file identity and final delivery.

The [six-repository version map](references/toolchain-versions.json) distinguishes
skill releases from runtime compatibility and current-process loading. Install
test dependencies in an isolated environment with `python -m pip install -r requirements-test.txt`;
the suite includes synthetic loopback TLS probes and makes no NotebookLM requests.

Evidence-led empirical manuscript refinement with interleaved local analysis tracing and NotebookLM review. The agent performs the work; deterministic tools check provenance, frozen versions, review coverage and completion receipts.

Read [SKILL.md](SKILL.md) for the workflow. Python 3.10+ and Node.js 18+ are sufficient for offline checks. Native Word and statistical execution remain in their domain tools. Shared NLM execution requires the `multi-agent-collaboration` resource broker and an explicitly pinned existing transport; this project does not launch browsers or authenticate accounts.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/install.py --canonical /absolute/skills/thesis-refiner --codex-adapter /absolute/codex/skills/thesis-refiner
# Review the dry-run plan, then apply that maintained-file overlay:
python3 scripts/install.py --canonical /absolute/skills/thesis-refiner --codex-adapter /absolute/codex/skills/thesis-refiner --apply
```

Installation overlays only maintained files, backs up every replaced file and writes a hash manifest. It preserves existing research inputs and legacy private resources. It does not change hooks globally, restart Word/RStudio, configure an account or publish a manuscript. Bind the completion hook to a task checkpoint explicitly when required.

The 2026.09.26.9 increment adds [whole-thesis formatting retrospectives](references/full-thesis-format-retrospective.md):
source-qualified institution rules, conditional section decisions, caption/footnote/bibliography checks,
versioned electronic appendices and grounded NLM interpretation review. It reuses OfficeCLI's optional
`thesis_integrity` report within the existing format evidence; it adds no new global hook or retrospective
gate to completed manuscripts. Synthetic fixtures, native Word checks and semantic acceptance remain distinct.

The 2026.09.24 maintenance increment adds explicit derivative-delivery checks, phase-limited audio recovery, hook diagnostics and checked rollback. Existing task-bound runtimes are not migrated by installation. See [runtime maintenance](references/runtime-validation.md), [delivery contract](references/delivery-contract.md) and [audio recovery](references/audio-recovery-contract.md). A doctor probe distinguishes entrypoint behavior from client registration and actual invocation.

The 2026.09.25 increment adds [connection diagnosis and recovery](references/nlm-connection-recovery.md): a bounded TLS-only probe, classification of original pre-origin CONNECT failures, and a recovery preflight that wraps byte-pinned scripts/logs in JSON evidence. It preserves the existing pinned health/runtime files. A successful TLS handshake, a valid necessary query, and sustained continuation are reported separately. The optional probe uses the existing executor's `httpx 0.28.1` / `httpcore 1.0.9` environment and HTTP/2 dependencies; it does not install or switch transports. Loopback CONNECT/TLS tests make no external requests.

The optional `scripts/nlm_stream_wait.py` preserves one pending response read across soft idle notices while retaining a hard total deadline. It does not send or replay requests, poll a server, or alter leases. A task must explicitly bind it after the previous run has returned. Synthetic tests cover delayed data, true EOF, original read errors, total deadlines, and cancellation cleanup; these do not claim live NLM recovery. See [stream interruption recovery](references/nlm-stream-interruption-recovery.md).

The 2026.09.26.8 documentation increment adds operation-wide preflight for SDKs that construct separate RPC and file-upload clients. It keeps registration, upload, processing and fulltext states separate, and resumes an unsubmitted upload under the already registered source ID when the original evidence proves that boundary. Runtime code remains unchanged.

The 2026.09.26.7 documentation increment distinguishes HTTP 200 region refusals from TLS, authentication and quota failures. It documents task-specific route binding, original-session reconciliation, evidence required for connection-only attempts, and cancellation of maintenance reservations that were never handed over. Review guidance now checks native `cited_table` contents before treating a table as missing. Runtime code and active task bindings are unchanged; successful short RPCs, a completed necessary long answer, and subsequent queue progress remain separate evidence.

Public tests contain synthetic data. Real manuscripts, account identifiers, CDP targets, raw executor transcripts and machine-specific evidence belong in private task directories. `simulation` output never counts as an accepted paper or NLM round.

The public JS/runtime integration suite uses a sibling `multi-agent-collaboration`
checkout or `COLLABORATION_BROKER=/absolute/scripts/resource_broker.py`. Its
subprocess transport is synthetic and makes no network calls. Missing that
dependency skips only the integration suite, which must pass separately before
installing a combined runtime. Domain-native acceptance and live NLM benchmark
results are recorded separately from unit tests.

Query health is kept in an explicitly bound `QueryHealthJournal` from
`scripts/nlm_query_health_store.py`. It consumes immutable real return receipts,
persists pauses across restarts, and admits an evidence-bound recovery request
once. Bootstrap from the actual return history; a missing journal never silently
resets health. The journal neither grants network access nor changes account
budgets, broker leases or paper acceptance. A private adapter must explicitly
adopt it; installing these modules does not migrate active executors.

For shared-account throughput, read [concurrency and READY scheduling](references/nlm-concurrency-and-scheduling.md). The optional `scripts/nlm_ready_scheduler.py` keeps a persistent fair queue and consumes original release evidence. It makes no network calls and does not alter a running pinned broker/runtime. A task adapter binds it to an already validated serial or two-query executor; local queue tests are separate from live parallel validation.
