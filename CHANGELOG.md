## 2026.10.13.3

- 对齐协作0.4.32，由 CURRENT 自身解释审查过的旧 v2 纯文件协议；完整核验
  原 MANIFEST、所有实际成员、controller 与 issuer scheduler pins。保留原 controller、
  UNKNOWN、pending、journal 及首次跨版写前的完整旧证据，不在后台执行旧代码或输入。
- 同步 PREPARING/token 登记事务与原 SHA 绑定的显式 enroll-existing。提交前失败保留
  原 state/channel；提交后故障幂等恢复原事务，不能新建 episode 或覆盖后来的 channel。
  新 episode 与旧错误主管登记不自动迁移；已停止、终结或正式占用不补登记复活。
- 正式 reservation 不再依赖 continuation 或协议兼容：同主管暂停，属于原 caller/
  workspace、晚于 episode 的合法新主管 reservation 结束旧求派。精确 RELEASE 才
  移除暂停；TTL、heartbeat、marker 消失不授释放或继任。旧0.4.27普通 WAITING 也适用。
- 同步单引号 `; Codex alone` 的残余 launch 误判修复：保留原消息，区分 literal
  与 shell 代码，继续检查真实相邻 CLI、嵌套执行和 wrappers；不复制协作检测器。
- 采用显式 `resume_task_no_input.py` 入口：默认只读，指定原不可变 controller、
  executor、pack、精确 notice；apply 必须绑定计划的完整 history_sha256。仅连续全
  NO_INPUT/events=[] 且 COMPOSE_OCCUPIED 或 RECEIVER_COMPACTING、原身份/native/锁/
  pack/payload/nonce 不变、当前 composer 空时，通过原 controller 追加一次 attempt。
  原字节保留，输入意图/UNKNOWN/队列/receipt/历史改变均拒绝，草稿不清理。普通自动
  预检仍限两次，零输入不冒充实际发送预算耗尽；不重发未知消息。
- 正式 reservation 只暂停新请求，仍发现原绑定 reply；ANSWERED 和精确 consume
  都不解除 reservation，须原匹配 RELEASE。仅原认证 executor 经原 controller
  消费；显式 start --file-only 与 transcript 通道互斥。
- 同步原迟到握手 ACK 的有界只读观察入口：固定原 controller、超时 receipt、
  dispatch attempt 及精确 notice，独立留证而不改原回执、不输入；收到短通知、
  全文读取、ACK 与业务接受分别报告。
- 明确主管主链 callback → 核收/disarm → 预备下一包 → fresh preflight → 派送。
  60秒求派仅兜底，文件定时器不能唤醒模型；ANSWERED 未 consume 不重复派单或
  替换现业务 episode。按去重核收的有效覆盖、问题关闭和真实分阶段 latency p50/p95
  衡量成效，列明样本数/窗口/缺失样本，不奖励 ask_count。历史检测到消费时长
  不当作纯空闲、因果或本版现场采用证据。

协作全套回归1846项通过、0失败、0错误。论文回归使用requirements-test.txt，
跨仓验证显式绑定兼容的真实resource_broker.py。登记、scheduler真实执行、自动hook、
正文完整读取及两轮真实continuing request/reply/consume/rearm分别需要现场证据。
协作0.4.31 / 论文2026.10.13.2的维护通知正文提示、原生投递、非阻塞hook及不重发
规则继续保留。版本文档和离线结果不证明活跃客户端已经采用。

## 2026.10.13.1

- 同步协作0.4.30的PID复用修复：可信且早于当前进程的可选旧foreground记录不再拖垮无关caller发现；不采用旧thread、不削弱必需observer和当前身份校验。
- 删除无关foreground异常的全局否决：坏时间戳、非法或缺失记录仅排除对应候选；保留选中caller重核与真实多重匹配检查，不改旧证据、不新增发送器。
- 统一当前SKILL与README的协作版本引用；保留原任务、callback和身份记录，区分源码验证、安装及活跃客户端自动hook证据。

## 2026.10.12.5

- 同步协作0.4.29握手探针共用pane/target互斥与自动续跑防碰撞合同。
- 混合入站保留原次，分别核精确回执、任务包实读与业务接受；不为补回执重派原论文工作。

## 2026.10.12.4

- 正常继任握手默认允许；同步 ASCII footer 误报修复与无关旧 pending 的独立保存，不再阻塞新任务联络。

- 同步继任握手迟到ACK的原次核收、主管延迟归因、同pane原生Codex限定通道与至少20GB主动空间管理；不重放历史任务。

- Adopt collaboration0.4.28 explicitly authorized continuing inquiries, exact reply consumption and task reservation boundaries.
- Preserve ordinary finite waits, original controllers, nonblocking hooks and separate research acceptance.

# 2026.10.12.3

- Synchronize collaboration 0.4.27: preserve actual root/child hook identity, fair bounded file reminders and cursor updates after successful context output. Inherited root identity cannot give a child the supervisor inbox.
- Document the separate explicitly enrolled 60-second file scheduler and its finite sweep/capacity limits. Installation, enrollment, actual execution, file exposure and body reading are distinct; no idle-model wakeup or legacy-controller migration is implied.
- Remove remaining active instructions to use the Codex Tab queue or blocking closeout hooks. New Codex callbacks use the original native thread once; uncertain and historical attempts are observed without resending. Retain ordinary tool/Stop access and original research ownership.
- Explain executable-argument checks for Python heredocs so subprocess imports do not turn document prose into a CLI launch. Shared code remains solely in multi-agent-collaboration.

# 2026.10.12.2

- Route new Codex-bound input and callbacks directly to the original native thread through collaboration 0.4.26, without composer or Tab-queue operations. Require the original native intent/fence and exact received record; observe uncertainty without resending historical callbacks. Remove obsolete blocking-hook instructions from delivery references.
- Synchronize collaboration 0.4.26: measured clipped git-footer recognition and nonblocking, authenticated supervisor file-request context.
- Document exact mailbox reply before fresh dispatch, the explicit runner's 540-second polling budget (synchronous I/O can extend wall time) and the lack of idle-supervisor wakeup. Preserve old pending attempts and separate historical receipt proof from live reconciliation.

# 2026.10.12.1

- Synchronize collaboration 0.4.25: explicit insufficient-balance classification, advisory-only workflow hooks and explicit callback/reask supervision.
- Preserve in-flight task controllers and keep installation, active-client adoption, native receipt and business acceptance separate.

# 2026.10.11.2

- Incorporate the measured SQLite/disk-inventory false-positive fix from collaboration 0.4.24; preserve task-specific peer scope in maintenance replies.

# 2026.10.11.1

- Document live split-footer recovery, prompt consumption, and exact zero-input formal-notice repair in collaboration 0.4.23. Configuration, native receipt and ACK remain separate acceptance facts.

# 2026.10.10.4

Task-hook caller discovery failures no longer lock ordinary tools or Stop.
New and successor supervisors use the current native foreground thread without
a fixed resume command. Preserve task evidence and verify live transport at
input. Continue authorized solo work when the original executor is unavailable;
return to one or two executors only at a safe boundary. Documents track
multi-agent-collaboration 0.4.17 and require actual per-session hook adoption.

# 2026.10.09.9

Synchronize the maintained skill with collaboration 0.4.7: fresh input uses
bounded single-line notices with pinned complete bodies, while task packs and
callbacks keep their dedicated routes. Notice reception, body access and task
acceptance remain separate facts; Enter/Tab success is never native proof.

Document the official PostToolUse output envelope and distinguish automatic
client invocation from configuration registration and manual checks. Retain
the narrowly bound callback successor after a proven first zero-input attempt,
original controllers for in-flight work, and explicitly authorized executor reasks
separately from default finite idle observation. No duplicate sender is added.

These changes update shared workflow documentation, not manuscript acceptance,
active task bindings, or a claim that all running clients passed live stress tests.

# 2026.10.09.3

Synchronize the maintained documentation with the canonical native-delivery and
bounded-wait contract. The original PASTE_INTENT fixes the receiver, fresh EOF
fence and complete payload. A verified busy Codex uses Tab; other supported
states use Enter. Queues and Claude queued_command remain pending. Automatic and
explicit recovery share one persisted extra-key budget; only submit-text exposes
protected recovery, while task packs and callbacks reconcile their original attempt.

Document finite idle observation, ordinary honest WAITING_SUPERVISOR exits and
separate report discovery, native reception, formal receipts and acceptance.
The public source includes the receiver-bound compatibility entry and a portable
upstream contract link. Runtime modules, research acceptance rules and existing
task bindings are preserved; source checks do not claim active-client adoption.

# 2026.10.09.1

Use the collaboration 0.2.0 delivery contract for prompts, task packs and
callbacks: pin the receiver and original transcript boundary before input,
settle the complete composer before Enter, and confirm only an exact new native
message. Reconcile the original attempt without repasting; automatic and explicit
recovery share one persisted extra-Enter budget. Native queueing proves receipt,
not execution or thesis acceptance.

Document the shared PostToolUse guard, installer migration and idle Stop hook.
The 60-second request loop retains unconfirmed requests across restarts and
requires a real supervisor reply. It does not duplicate senders or hook code.
No manuscript, Word/NLM execution or existing task binding is changed.

# 2026.10.05.1

Clarifies full-payload, per-call confirmation for prompts and callbacks, strict
boolean Stop-hook reentry, and native receiver evidence. Legacy journals stay
with their original controller. The generic implementation remains in the
collaboration repository; this documentation neither installs new hooks nor
changes frozen thesis tasks or claims Word/NLM live validation.

# 2026.09.26.10

Imports the verified 2026.09.26.9 maintenance source and adds compound result keys, checked optional reference sizes, idempotent reference identity, exact manifest/ZIP checks and generated chat links. All runtime recovery operations remain explicit; installation does not rebind active tasks.

The 2026.09.26.9 predecessor covers whole-thesis format decisions, original NLM returns and native synthetic fixtures. Historical task evidence is not shipped.
# 2026.10.13.2

- Reuse collaboration 0.4.31 for explicit recovery of a Claude successor notice
  starved by repeated old-supervisor waits. Its original full body is exposed at
  a tool boundary without repasting, blocking tools, resetting context or
  changing native receipts. The executor replies with its actual safe-boundary
  state; the successor remains responsible for business dispatch.
