## 2026.10.19.8

## 2026.10.20.1

- Adopt the shared three-state continuity contract: original trio, available Codex takeover, or original Claude peer continuation; bound child agents across the whole task.
- Require explicitly enrolled task-scoped proactive Stop continuation and full reply consumption; preserve old episodes and uncertain callbacks.
- Remove stale raw-send, separate-pane and mandatory300-second-wait rules from collaboration recovery guidance. Shared runtime remains in multi-agent-collaboration.


- Adopt MAC 0.4.54 direct communication, pre-input socket fallback and native marker user receipts.

- 对齐协作0.4.54：同pane不同tab可通信与握手，身份和实际布局分别核验。
- 输入仍串行，旧消息、原会话与登记保留；callback接口健康单独验证。

## 2026.10.19.7

- 对齐协作 0.4.53 的 Claude 2.1.303 实测通知布局修复。
- 已粘贴通知按原次核实；已入队不补键、不重贴，正常登记不重复重启。

## 2026.10.19.6

- 对齐协作 0.4.52：Claude 版本化原生进程身份与握手异常结算统一由协作仓修复。
- 升级后逐会话核对进程、启动配置、自动 hook 与实际双向通信；不以安装替代采用。
- 同 session 换 PID 后先只读预检，再授权原执行者显式登记新 episode；旧回件不伪造消费。

## 2026.10.19.5

- 对齐协作 0.4.51：自动回件提示取消旧的 idle-preflight 要求。正常工作、原生
  Goal 和自动续轮不阻止就绪信息发送；新任务包仍核身份、握手及 validation。
- 完整核验的 0.4.50 文件协议保留原权限，在途 episode 无需为升级停止重登；
  原控制器、正式预留与未确认输入保持不变。
- 只同步协作说明，不复制 runtime、hook 或发送器。已证问题是自动提示文本，
  不能据此声称发送器仍以忙碌为门禁、历史停顿根因已解或真实往返已完成。

## 2026.10.19.4

- 对齐协作 0.4.49：原执行者可显式恢复旧求派登记，提交前保留旧 stop，
  继承同一协作绑定的正式预留；历史未确认消息不重放。
- 说明预留期持续文件询问须显式授权，版本安装与旧 episode 实际采用分别验收。
- 本仓只更新协作说明；登记事务、历史兼容、发送器与 hook 继续由协作仓唯一维护。

## 2026.10.19.3

- 修正非阻断 observer 段落残留的旧协作版本：新任务统一引用本页顶部声明的
  0.4.48，不再维护第二个容易漂移的版本号；在途任务继续固定原控制器。
- 仅修正文档与本技能版本标识，复用已发布的协作运行时及验证结果；
  配置安装、活跃客户端加载和真实双向收件仍分别核验。

## 2026.10.19.2

- 对齐协作 0.4.48：完整边框外 elapsed 字段中的已测 auto-compact 百分比提示
  不再被误判；正常工作与 Goal 继续允许及时双向通信，真实草稿逐字保护。
- 区分核包 SHA、原生收件、正文已读及明确任务接受。接受时点须有对应原生
  记录；未知预算起点不生成虚假截止时间。
- callback 端点缺失时保留原失败；已有授权下的文件独审和精确 RELEASE
  不冒称 callback 已送达。不重放旧次、不增加科研审轮。
- 本仓只同步技能文档；页脚解析、旧 0.4.47 文件协议兼容、发送和 hook
  仍由协作仓唯一实现。配置、发布安装与活跃客户端采用分别核验。

## 2026.10.19.1

- 对齐协作 0.4.47：显式 profile 修复、原控制器诊断及完整核验的 0.4.46 文件协议
  由协作仓唯一实现；数据库配置、实际 settings、自动 hook 与线程认证分别核验。
- 互核列作者、完整源 SHA、字节域、重测项、负对照、未核范围和各方独立回件路径；
  主执行者抽核关键事实，页码、表号及位置按原文或几何证据重定位。
- 导出保留原始字符逐项差；空白归一化仅作辅助，行数、坐标等版面检查独立记录。
  规范或验收器变更须注明 pins，保留旧规范 FAIL，不改旧验收器来换 PASS。
- 正常忙碌、Goal 续轮和无关 pending 不限制独立新信息及时发送。原消息只对账、
  不重发；共享写入仍明确交接。不增加科研审轮、不复制 sender/hook。

本地 Python 3.14 全量 205 项通过，使用协作 0.4.47 候选的真实 resource broker，
跨仓测试无跳过；配套协作库 2,391 项及握手 schema 6 项通过。

本次修改为技能文档。复用已接受研究证据；既有 Claude 局部审阅不扩大为本版
整体 PASS。离线检查、发布安装、客户端采用和真实双向收件分别记录。

## 2026.10.18.4

- 对齐协作 0.4.46：双方 prompt 就绪后及时经支持入口发送，正常忙碌、原生
  Goal 和自动续轮不构成通信禁令，不要求先暂停 Goal 或等待空闲。
- 新握手直接核身份、ACK 和 validation；输入并清除字符的探针仅用于显式诊断。
  原失败探针、迟到 ACK、旧 controller 和未确认输入保持原归属与证据。
- 接收方安排任务执行次序；共享文件写入交接、草稿保护、原次去重与原生收件
  分别核验。预留期暂停的是 runner 的自动终端求派，不限制 agent 发送就绪信息。
- 仅更新技能及配套文档，不复制 sender、hook 或调度实现，不重开已接受科研审轮。
  最终提交由 CI 验证，安装、活跃客户端自动 hook 和原生收件另取现场证据。

## 2026.10.18.3

- 对齐协作0.4.41，纠正磁盘政策：保留至少10GB（10,000,000,000字节），
  低于20GB（20,000,000,000字节）触发主动管理与已授权备份。
- 安装及回滚预算另计，20GB不能当作用户指定的安装硬底线；旧文档的归因撤回。
- 仅更新文档与当前版本入口，运行实现和安装器源码保持2026.10.18.2原样。
  复用已完成验证，不增加Claude科研审轮；发布、安装、自动hook和原生回调分别留证。

## 2026.10.18.2

- 对齐协作0.4.40：嵌入式原生工具与hook核验完整进程祖先链，中间模型不能
  继承父Codex身份；历史文件episode只保留原已登记的预留询问权限，不补造授权。
- 安装器在写入前检查全部受管目标，拒绝以不同字节覆盖已有canonical或adapter；
  升级必须使用独立版本目录，相同源码重复安装保持原文件不变。
- 新任务固定新源码的真实路径和SHA；旧任务继续使用原路径、原字节与原控制器。
  公共安装器仅管理所列文件，完整源码封存及新任务alias路由由统一安装流程完成。
- 保留schema-v2历史安装回执的显式回滚与并发写入保护，不提供原位覆盖绕过开关。

本地安装器定向验证11项通过；最终CI绑定本次提交。协作0.4.40的原Claude审阅
不扩大为本次论文安装器的独立审阅。源码验证、发布、安装、自动hook、正文消费
与原生callback分别记录，不把已发布称作已在活跃客户端生效。

## 2026.10.18.1

- 对齐协作0.4.37的单轮完整版本验证复用：成员及父目录变化立即失效，
  每轮重建验证，身份、授权、STOP、预留与回复仍实时核验；保留容量和时间预算。
- 区分只读验证提速、实际定时sweep、原回复发现、正文读取及原controller消费。
  安装和基准均不证明活跃客户端加载或真实callback通过。
- 同步0.4.36原主管迟到ACK的嵌入式身份限定；该入口不扩大普通发送或hook权限。
- 保留完整核验的0.4.36及更早文件协议和原有预留询问权限，不迁移在途任务。
  调度实现仍由协作仓唯一维护，本次只更新技能说明，不增加研究审轮或发送器。

文档增量由维护者审阅，最终CI按本次提交记录；不扩大先前Claude冻结审阅范围。
运行实现、不可变安装、自动hook与原生回调分别验收。

## 2026.10.17.1

- 对齐协作0.4.35的新投递30秒确认窗、有限0至60秒选项及默认一次只读reconcile；
  保留原RPC诊断与controller来源，不把超时或turn abort当成消息丢失或重发权限。
- 同步从上一条原生确认后至少60秒起算的终端求派、独立文件节奏及runner返回边界；
  返回不停止episode、不改Goal、不证明终端空闲，正式派单仍核新鲜preflight。
- 同步原ANSWERED全文与consume入口、待ACK/超时提示及独立CALLBACK_SETTLEMENT。
  提示不代正文读取、ACK、论文核收或精确RELEASE；不增加下一任务ask_count。
- 对齐精确reservation复用、终态RELEASE清理、有界公平发现和0.4.34历史文件协议。
  仅reask scheduler采用Standard，配置守护器仍Background；实测Monitor/Goal与
  padding不授权全局strip/rstrip、清草稿或额外补键。原controller与旧证据保留。
- 更新全局通信、投递和收尾参考；协作恢复后接原论文待办，不新增科研审轮。

本次只改文档，运行实现由共享协作skill提供。R1冻结的协作提交
`60a992cd51413e8799235c6012dba5559be8ec31` 在macOS/Ubuntu与Python 3.10/3.14
四个CI环境各运行2,111项（含2项skip，实际执行2,109项），0 failures/errors。
该计数只对应R1冻结提交；后续整改与最终发布须引用各自精确HEAD的CI，不能沿用。
论文仓R1冻结提交`c4bb88aeb5de912b1bd8335a679eabf9a9e2b906`的Python 3.10/3.12
CI通过；更早的本地计数不记成本次最终验证。
原会话独审、CI、不可变安装、真实自动hook、正文读取与native receipt分别核验。

## 2026.10.14.1

- 将 SKILL metadata、当前版本说明与 README 统一对齐协作 0.4.34；旧版本记录保留。
- 同步 0.4.34 精确 ACK 解析：唯一 text ACK 可与严格结构的 thinking /
  redacted_thinking 共存，不输出其内容；额外文本、工具、畸形块及任何 nonce /
  空白差异仍拒绝。composer 的空白归属未知时保留原次，不作全局 strip/rstrip。
- 同步 0.4.33 特定 REJECTED / DRAFT_NOT_READY / STRANDED_IN_COMPOSE 原握手
  的迟到 ACK 核收，须完整证明原粘贴历史且未提交；只由原主管先预览再显式 apply，
  使用原 writer/validator，不补键、不重贴、不将 ACK 当作完整通知原生接收。
- 同步完整 composer 边框外的上下文输入/缓存统计 footer 识别，以及经完整 manifest
  与成员核验的 0.4.32/0.4.33 v3 state/v2 enrollment 文件协议兼容。原 controller、
  pending、reservation 和 consume 权限保持原归属。

本次只改文档，协作实现仍由共享 skill 提供；协作 0.4.34 本机完整回归 1,912 项通过，
0 failures/errors。论文实现未变，复用此前 203 项通过的本地验证，精确提交由 CI 检查。
安装、scheduler 实际执行、活跃客户端自动 hook、ACK 与正文接受仍须独立现场证据。

## 2026.10.13.3

- 同步调度预算耗尽后的游标保留与分阶段诊断：先读轮转游标，再完整验证版本；
  游标读取超时保留原 STATUS，另写 LAST-ERROR。中断时 file_posts 只是部分计数，
  不把0当作完全未执行；4项定点通过，实际求派及消费时效另取现场证据。
- 同步consume可区分结果：新控制器成功返回receipt、正文SHA和消费时间；未消费
  返回consumed=false及非零码。continuing回到WAITING_REPLY与本次消费结果分列；
  原预留不解除，旧控制器沿用原语义并独核真实receipt，不把rc=0当作消费证明。
- Claude的queue remove/queued_command仍是客户端队列证据，不保证随后出现
  native user；派单边界减少竞争性自唤醒，Goal、loop、advisory分别核证。
- 对齐原控制器迟到 ACK 核收入口：原主管先只读预览，原 harness 退出后显式
  apply，保留超时、原 nonce/attempt 和未证通知接收，用原 writer/validator
  重算握手；不重握手、不代派包。协作入口28项行为测试及原完整0.4.31兼容通过。
- 固定审查问题、必要检查和及时报告边界；已接受范围不因等待最终报告重开。
  两轮 continuing 功能闭环与60秒消费目标分别验收，主管不代消费或制造唤醒。

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

协作全套回归1885项通过、0失败、0错误；论文全套203项通过、0跳过。
论文回归使用requirements-test.txt，
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
