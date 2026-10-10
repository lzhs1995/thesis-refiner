# Thesis Refiner / 论文精炼助手

This version documents the **receiver-bound delivery contract**. Verify the
shared collaboration release's installation, actual client loading and live
native receipts separately before claiming adoption by an active session.

Current source: **2026.10.11.1**, synchronized with collaboration **0.4.23**.
Workflow hooks observe their actual invocation without blocking ordinary tools or
Stop. Authorized successor supervisors can contact designated existing executors
through the successor-rebind-v2 maintenance route, including across workspaces.
See [nonblocking collaboration](references/nonblocking-collaboration.md). The
[global configuration contract](references/global-communication-configuration.md)
covers cc-switch observer restoration, explicitly started 60-second inquiries and
per-session adoption without introducing a second sender. The
[delivery entry](references/verified-compose-delivery.md)
now routes to the authoritative receiver-bound contract. Read the
[toolchain lessons](references/toolchain-retrospective.md) and
[manifest/link contract](references/delivery-manifest.md) for result assembly,
file identity and final delivery.

Collaboration 0.4.20 also distinguishes literal document/search text from real
terminal writes and recognizes measured wrapped Claude model/cwd/time footers
and tool-count overflow. Existing drafts, active tools and unknown trailing rows
remain protected. These parser checks are separate from actual client loading
and a successful current-task handshake.

Collaboration 0.4.21 resolves tools that become direct children of the managed
daemon after shell exec optimization. It reads the actual tool process selector,
then retains native foreground, unique-client, TTY, UUID and process-drift checks.
No wrapper process or historical resume command is required to authenticate the
current caller. This identity fix does not establish a handshake by itself.

The [six-repository version map](references/toolchain-versions.json) is a historical
release snapshot, not an installation selector for this version. Skill release,
runtime compatibility and current-process loading remain separate. Install
test dependencies in an isolated environment with `python -m pip install -r requirements-test.txt`;
the suite includes synthetic loopback TLS probes and makes no NotebookLM requests.

Evidence-led empirical manuscript refinement with interleaved local analysis tracing and NotebookLM review. The agent performs the work; deterministic tools check provenance, frozen versions, review coverage and completion receipts.

Read [SKILL.md](SKILL.md) for the workflow. Python 3.10+ and Node.js 18+ are sufficient for offline checks. Native Word and statistical execution remain in their domain tools. Shared NLM execution requires the `multi-agent-collaboration` resource broker and an explicitly pinned existing transport; this project does not launch browsers or authenticate accounts.

Agent messages use the shared [receiver-bound delivery contract](references/receiver-bound-delivery.md).
The collaboration release binds the native receiver and transcript inode, then
persists the original `PASTE_INTENT` with a fresh EOF fence before input. It pastes
once via `terminal.paste` with `submit_key=none`. After the complete original
composer is stable, a busy Codex with the verified `tab to queue message` hint
receives Tab; other clearly supported states use Enter. There is no Ctrl+Enter route.
Only a new native user record after that original fence, exactly equal to the
full payload with all whitespace preserved, proves reception. A queue or Claude
`queued_command` remains pending; it proves neither reception nor execution.
Automatic and explicit recovery share at most one extra submit key, consumed
when its intent is persisted. `--recover-stranded` belongs only to `submit-text`;
task packs and callbacks reconcile read-only through their original controller.
Missing original bindings or fences cannot be reconstructed. Unknown, queued,
compacting or reconnecting states authorize no recovery key. Never repaste,
change the nonce, delete a draft, or select a session by newest mtime.
This repository does not maintain another sender. Actual hooks and wrappers
must use the same immutable collaboration release; configuration writes do not
prove that an active client reloaded.

New long or multiline ordinary messages use a bounded single-line notice for the
SHA-pinned complete body. Formal packs use their dedicated notice and callbacks
keep their exact task-bound line. A notice receipt does not prove body reading.
Automatic workflow hooks emit no denial or turn-control output; adoption records
identify the original hook, advisory entrypoint and actual process provenance.
A manual hook invocation is not automatic client adoption. Explicit native
reconciliation preserves the original controller and evidence of an in-flight task.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/install.py --canonical /absolute/skills/thesis-refiner --codex-adapter /absolute/codex/skills/thesis-refiner
# Review the dry-run plan, then apply that maintained-file overlay:
python3 scripts/install.py --canonical /absolute/skills/thesis-refiner --codex-adapter /absolute/codex/skills/thesis-refiner --apply
```

Installation overlays only maintained files, backs up every replaced file and writes a hash manifest. It preserves existing research inputs and legacy private resources. It does not change hooks globally, restart Word/RStudio, configure an account or publish a manuscript. Bind the completion hook to a task checkpoint explicitly when required.

Before applying an overlay, compare the source commit and file hashes with the
current installation manifest. Preserve newer maintained content by integrating
it into the source first; a metadata bump alone does not make an older checkout
safe to install. The installer does not reject version downgrades automatically.
See [installation and rollback](references/runtime-validation.md#安装与回滚).

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

## 身份识别失败不得封锁会话

协作 hook 无法识别当前 caller 时，不具备施加任务门禁的依据，必须放行普通
工具和 Stop。已入组会话也能诊断、编辑修复、记录状态、执行已授权 SOLO 和
诚实结束回合；不重复触发阻断。任务标记、冻结报告、原回调与投递预算原样保留，
不能据此冒称收到、接受或多 agent 共识。恢复后下一次核验重新检查真实任务。

新建、切换和接手的 Codex supervisor 均可按现有用户授权主动握手，使用当前
原生 foreground thread、内核进程和 workspace/surface 证据；不要求固定的
codex resume 命令，也不绑定旧主管会话号。终端发送仍核验真实双方。

优先推进用户原任务，按独立交付物与当前容量使用零、一或两个 executor。
本机通信入口故障不等于 Claude API 故障；经有限重试仍不可用时，按已有授权
由 Codex 接管并标注 solo_self_review。原 Claude 恢复后只在安全边界重新接入；
不为通信维护重开已接受的科研审轮，同 pane 两 tab 的终端输入保持串行。
