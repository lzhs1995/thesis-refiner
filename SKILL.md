---
name: thesis-refiner
description: Refine empirical theses through evidence tracing, concise revision, native document checks and grounded NotebookLM review; derive requested defense slides, scripts and audio from verified manuscript versions.
metadata:
  display_name: 论文精炼助手
  aliases: [论文精炼助手, 论文精选助手]
  version: "2026.10.18.1"
---

# 论文精炼助手

用户授权的正常继任握手、新进度通知与独立新任务联络默认允许，无需旧主管批准或
无关旧任务结算。复用原会话与健康握手，旧次证据单独保留；不再让无关 pending
永久阻塞新联络。完整边框外的 ASCII `...` 截断路径及任务摘要按 footer 识别。

**2026.10.18.1**对齐 multi-agent-collaboration **0.4.37**。文件调度在单轮内
复用完整版本验证，每次复用仍核全部成员及父目录是否变化，任务与授权状态实时读取；
新一轮重新验证。只读提速样本不代表实机发现延迟、正文已读或回调已核收。
0.4.36 的嵌入式 Codex 身份恢复仅限原主管迟到 ACK，不授予普通发送或 hook 认证。
完整核验的历史文件协议保留原控制器及既有预留询问权限。详见
[协作提效与收尾](references/collaboration-efficiency-and-closeout.md)。

新提交默认观察
原生收件30秒，reconcile默认一次只读观察；窗口耗尽或turn abort不授权重发。
终端求派从上一条原生确认后至少60秒起算，文件求派独立计时。PostToolUse提示
原ANSWERED全文、原consume入口、待ACK握手与独立CALLBACK_SETTLEMENT；
提示不代读取、核收或RELEASE。正式预留时本次runner返回，仍须新鲜preflight，
不停止原episode或改变Goal。详见[全局通信配置](references/global-communication-configuration.md)。
共享实现同时保留经完整核验的0.4.36及更早文件协议与实测Monitor/Goal/padding边界；
不迁移原控制器、不清草稿、不复制sender或hook。最终验证见CHANGELOG，
安装、自动hook、正文读取与论文接受分别取证；通信维护不增加科研审轮。

已发布的 **2026.10.13.2 / 协作 0.4.31** 基线保留原生 Codex 投递、非阻塞
工作流观察和已登记 Claude 维护通知正文提示，不作为本次新增修复。新消息与 callback
直接进入原 supervisor 会话：运行中 steer、空闲时 start，不操作 composer、不入 Tab 队列。
主管 PostToolUse 按真实root/child身份每次最多提示8条文件请求，公平轮转，
未回复至少60秒再提示，成功flush后更新游标；child不能冒用继承的root消费收件箱。
窄窗格状态栏的 git 分支省略号只在完整边框外的物理行尾识别。共享 release 的安装、客户端实际加载、
Claude → supervisor 原生 receipt 和正文已读分别核验；文档与离线检查不证明现役采用。
用户已授权的每60秒新 marker 求派经显式入口运行，也可在认证登记后由独立文件
调度持续更新；不由 Stop 强迫续跑，安装不等于登记或实际执行，文件调度不唤醒空闲模型。
明确余额不足按 BILLING 分类，即使同时出现 /login 或 403；未知投递与主管观察预算
不足仍优先保留原分类。分类修正不代表 API 恢复，也不证明写者已冻结或 SOLO 边界成立。

0.4.20 进一步修复现场发现的普通文档命令误拦与 Claude footer 兼容：heredoc、
引号搜索中的命令示例不等于真实终端输入；完整边框后的模型/cwd/时间换行及工具
计数 `+N more` 按已测结构识别。未知 footer、活跃工具或现有草稿仍保留，不能拿
历史报告中的失败文字当当前运行状态。详见[现场修复经验](references/nonblocking-collaboration.md#普通文档命令与新-footer-的现场修复)。

0.4.21 补齐 shell exec 后工具进程直接成为共享 daemon 子进程的身份路径：没有中间
shell/rtk 祖先不代表 caller 非法，沿工具自身的内核进程证据取 thread selector，
再核原生 foreground、唯一客户端、TTY 与 UUID，收尾重核进程漂移。身份读取失败
只影响该次输入，不得封锁其他已授权工作；不要通过添加虚假环境或固定旧 resume 修复。

0.4.30 修复无关 legacy 客户端复用 PID 时遗留 foreground 文件导致的全局身份
误判：仅完整可信、双读稳定、早于当前进程出生且当前进程从未成功观察过选择的
可选旧记录可按缺失处理，不采用旧 thread。无关候选的坏时间戳、非法记录、
必需 observer 缺失或读取失败，只排除该候选，不再全局否决健康主管，亦不允许
用 resume 参数替代坏记录。选中主管的重核失败、真实多重匹配仍拒绝该次输入；
无关线程切换不污染主管身份。实现和回归检查复用协作 skill，
不复制身份检测器；不删旧记录、不冒用 daemon 环境，也不重放论文包或 callback。

cc-switch 切换、全局 hook 与每60秒求派按
[全局通信配置](references/global-communication-configuration.md)执行：复用协作
skill 的唯一守护器，原消息未确认时走文件通道；每个工作区通过后立即回原任务。

Claude 已排队的合法继任通知若被旧主管等待循环饿死，使用协作 skill 0.4.31
的显式原次登记与非阻塞 PostToolUse 正文提示；不另写发送器或工作流门禁。
原会话在工具边界读取完整原正文，反馈真实在途写入和 reservation，业务包由继任主管
另派。提示曝光、正文已读、原生 user 接收与业务接受分别留证；旧 callback 不重放。
没有登记的会话不受影响，Stop 不强迫续跑。详见协作 skill 的
`references/nonblocking-recovery.md#queued-claude-maintenance`。

全局安装 skill/hook 不代表所有会话参加协作。普通新 Codex/Claude 会话的工具
调用和结束无需 supervisor 批准；仅阅读或维护本 skill 也不算入组。明确启动协作
后，任务按 workspace、surface、role 和当前 native session ID 绑定参与者，再
记录相应任务状态；不得施加全会话封锁。同目录、旧面板、其他任务和继承环境不能约束新会话；规则
与实现统一复用协作 skill 的 session enrollment，不复制第二套 hook。

## macOS 自动化故障：优先执行规则

用户已明确授权自动处理时，沿用该授权，读取当前安装的 `officecli-word-revision/references/macos-tcc-zotero-word.md`，不得再次把同一个 Automation 开关或确认问题交给用户。先按实际发送方核查，再按已授权范围自动恢复；TCC.db 备份/重置是有证据的恢复动作，不是普通文稿流水线的隐含动作。多个 agent 只保留一个恢复执行者，其余继续离线工作；Claude 可重试 API 故障先按下文的连续 300 秒证据门槛核验，再沿既有授权和安全交接边界切换 supervisor 单 agent，不停整个任务。实际原生操作未通过前，不得把“已记录规则”“权限条目存在”或“退出码0”称为恢复成功。

目标是形成有据可查、可提交的精简文稿。精简以前必须全量追溯初稿的实证链条；文字删减量不是完成指标。保存用户原始问题、研究设计、目标稿件、允许补核范围和完成条件，恢复任务时先读这些记录。

## 两个交叉推进的循环

**循环 A**：冻结初稿 → 全量清点主张、表图、公式、脚注和附录 → 追溯数据、清洗、变量、样本、模型、输出和论断 → 精简修订 → 按发现补核数据或更新图表 → 再修订。

**循环 B**：候选 Word → 原生刷新、排版和 PDF → NLM 长文审查 → 本地逐项裁决 → 修改 → 新版本复核。严重的数据、图表或模型冲突立即回到 A；可以并行做不受影响的离线工作。NLM 的回答是待核实的审查证据，不能取代数值、来源身份和视觉检查。

用户要求论文答辩 PPT 时，按 [PPT 制作、审校与证据复用](references/ppt-production-and-review.md) 完成文稿、可编辑演示文件和逐字稿；内容审校、原生导出与视觉验收各自核实。

用户要求从已审材料制作音频时，按 [音频概览与本地验收](references/nlm-audio-overview.md) 固定素材、一次创建、观察原成品并下载验证。音频生成是独立交付流程，不计作论文审查轮次。

统稿、跨章 PPT 或已有成果续交时，读 [证据复用与总稿绑定](references/evidence-reuse-and-integration.md)。可并行起草衍生内容；正式来源页和最终身份须消费作者真实冻结记录。skill 维护、安装或 hook 排查读 [运行时验证与维护](references/runtime-validation.md)，不把一次环境故障固化成全局门禁。

总结全文排版经验、对标学校要求或维护格式检查时，读 [全文格式沉淀与裁决](references/full-thesis-format-retrospective.md)。数值规范和整稿检查复用 OfficeCLI 的版本化指南/契约；本 skill 负责规范来源、NLM 原答与本地裁决。分节、图表独占页、中文排序等按真实条件判断；未决建议只提示。经验工程独立立项，不给已冻结论文追加审读或验收任务。

开始实际工作时读 [双循环与证据契约](references/dual-loop-workflow.md)。NLM 阶段读 [完整审查与额度协调](references/nlm-review-and-budget.md)；多会话或执行者故障时读 [协作与恢复](references/collaboration-and-recovery.md)。原生 Word 阶段使用 `officecli-word-revision`，R/描述表使用 `clauder-rstudio-workbench` / `comparegroups-guide`，Stata 使用其共享会话 skill。各领域工具产出真实回执，本 skill 消费这些回执。

## 可执行入口

从本 skill 的安装根执行。输入/输出路径必须属于当前任务的新 run 目录。

```bash
python3 scripts/workflow.py inventory --input /absolute/original.docx --output /absolute/run/original-inventory.json
python3 scripts/workflow.py audit-chain --input /absolute/run/checkpoint.json
python3 scripts/workflow.py affected --input /absolute/run/checkpoint.json --changed model-id
python3 scripts/workflow.py acceptance --input /absolute/run/checkpoint.json --output /absolute/run/acceptance.json
node adapters/codex/closed-loop-orchestrator.js --checkpoint /absolute/run/checkpoint.json
python3 scripts/delivery_audit.py --input /absolute/run/delivery-contract.json
python3 scripts/audio_recovery.py --help
python3 scripts/hook_doctor.py --config /absolute/client/settings.json
```

`inventory` 是机械全量清点，覆盖正文、表格、公式、图片、脚注、尾注、页眉页脚及媒体。Agent 仍须把每段的多个实证主张拆开；数字提取不是语义复盘。每个原稿条目都要处置，未改条目也须审读。模板字段和示例见 [checkpoint 契约](references/checkpoint-contract.md)。

`acceptance` 必须读取存在且哈希一致的真实回执。编排器只消费证据；没有实现的自动 Word 修改/估计路线不会模拟成功。`--dry-run` 只能返回 `SIMULATION_ONLY`，不授予 A5。受影响依赖清单用于决定下一步，不自动扩大重跑范围。

衍生文件可按 [交付契约](references/delivery-contract.md) 核机械一致性；音频继任用 [阶段恢复契约](references/audio-recovery-contract.md)。这些检查不替代实际语义裁决、视觉或听审。旧任务保留原证据和已绑定入口，不为使用新工具补造回执或重跑已经完成的工作。

## 不可混淆的完成状态

- 找到文件、数值相容、找到唯一来源、全模型重估分别记录。
- 正常结束、有效标准误、保存的有效抽样和逐次收敛分别记录。
- 文档交付完成与完整实证复现分别报告。必要且已接受的科学 partial 可以保留；不得把它们改名为复现通过。
- 正文与附录单独验收。只复用哈希、来源与审查范围均一致的证据；一个文件变化不自动让另一个失效。
- 正式终验必须在最终 Word/Zotero、格式、实际 PDF 字体和视觉检查后，对同一冻结 PDF 完成连续两轮完整审查。没有新的本地确认问题，既有确认问题全部解决。三轮同一问题只触发专项裁决，不能自动通过。
- HTTP 200、空控制帧、上传 READY、退出码 0、同事的 DONE 和模拟回答都不能单独表示审查完成。

## 协作不得封锁会话

协作工作流 hook 统一采用 0.4.37 非阻断 observer；在途任务保留原控制器。
旧任务、未结算 callback、
身份不明、等待主管或 review 轮次均不得禁止普通工具、接收新握手或结束回合。
原检查器仅供显式诊断，不作为全局拒绝执行的 hook。停止自动求派不能阻塞 Stop。

当前身份使用 `cmux-agent self` 的原生 foreground resolver；raw cmux identify
可能显示共享 daemon 的继承环境，不能据此认定当前 caller 在旧工作区。

任何已获用户授权的继任 supervisor 均可联系指定原 executor，包括跨 workspace。
跨区维护握手使用协作技能的 successor-rebind-v2：固定用户授权正文及双方
workspace/surface/pane UUID，无须故障旧主管批准或先结算旧任务。该通信不授予
重放旧任务或接管共享文件写入。正式新工作另定范围。普通发送继续保护用户草稿、
持久化原 attempt 并核对新原生全文；单次投递未确认时，其他授权工作照常继续。

## 执行模式和资源

按[协作提效与收尾](references/collaboration-efficiency-and-closeout.md)决定零、一或两个 executor，使用相位握手预算，及时结案已接受成果；通信维护不扩大为新科研审轮。

交付后保留报告、task pack 和原 attempt；待核收状态不能冻结整个会话。
诊断、继任握手及独立已授权工作均可继续；旧消息只能沿原次核收，不重复输入。
全局 Stop/reask hook 不强迫无限续跑。显式发送器保留原生证据校验。

主管核收/disarm 后须[交回结论和下一步](references/collaboration-efficiency-and-closeout.md#子任务收尾后仍由主管推进整篇)。
正常子任务收尾不等于 API 失败或论文完成；新授权查询以最新回执为准，不能永久
沿用旧 recap，也不要让用户替已有主管通道转话。

握手只做身份与通道验证：首条消息直接给出 pending receipt 的绝对路径，executor 读固定文件后回精确 ACK；不在握手期间查全盘、审论文或做三轮共识。健康的同任务握手复用；短观察窗口耗尽不能冒称 executor 失联，迟到 ACK 按原 nonce 只读核收，不重复发送。

探针全文消失不能证明输入区已空；残留前缀、暂时缺prompt glyph和外来文字按
协作harness的有界清理后置条件处理。正常ACK等待及原nonce恢复记录为
`AWAITING_EXECUTOR_ACK/PENDING`，不提前报FAIL。短探针仍逐键核身份、保留
600秒预算；详见[握手清理与等待状态](references/collaboration-efficiency-and-closeout.md)。

**双向通信遵循[原生投递与有界等待](references/verified-compose-delivery.md)。**
只有同一已授权绑定的 workspace/surface/process/session/transcript，在原输入意图的
新鲜 EOF fence 后新增、全文完全相等的 native user 才为 NATIVE_RECEIVED；
保留全部空白。Claude `queued_command` 仍 pending，屏幕、ACK、按键返回、
队列和空输入区不证明收到。

新 Codex 输入先持久化 NATIVE_INPUT_INTENT，通过同版共享入口调用原会话的
一次 turn/steer 或 turn/start。RPC 接受不证明收到；超时或异常只读核原次，
不重发、不退回 Enter/Tab。历史 queued callback 保留原控制器，不能原生重放。
Claude 终端输入仍只粘贴一次，完整草稿稳定后提交一次；旧终端恢复先核迟到
原生记录，自动/显式恢复共用最多一次补键，意图落盘即耗用。
当前 `--recover-stranded` 只用于 `submit-text` 的原 NATIVE_PENDING、
PASTE_INTENT/ENTER_SENT 及未耗预算；任务/callback 只读 reconcile。
未知、压缩、排队、重连或结构改变不补键，缺原 binding/fence 不追补、不重贴。

自动 PreToolUse、PostToolUse 与 Stop 的协作工作流条目统一指向同版
`cmux_workflow_advisory.py --hook <原检查器名>`，记录实际调用的来源、版本、
事件和父进程证据。主管 PostToolUse 另读取已认证的文件请求并去重，以原生支持的
additionalContext 提示；不执行旧检查器、不发送消息、不核收历史任务、不返回
拒绝工具或阻止回合结束的控制结果。workspace/panel 的真实终端操作保护仍保留。

原生投递和冻结报告由显式发送器、原 controller 的只读核收及主管主动审读处理。
旧检查器可作显式诊断，其结果不得重新封锁整个会话。未证实的收到、共识或论文
完成不得对用户宣称；这项真实性要求不依赖 Stop 阻断。观察记录、完整原生消息、
真实 callback、论文接受和 disarm 分别留证。详见[非阻断协作恢复](references/nonblocking-collaboration.md)。

主管推进下一包的主链为 callback → 独立核收/精确 disarm → 预备下一包 →
fresh live preflight → 受保护派送。60秒求派仅作兜底，文件定时器不能唤醒模型；
ANSWERED 只表示已检测答复，须由原认证 executor 经原 controller 精确 consume，
未消费不重复派单、不替换现业务 episode。同主管正式 reservation 只暂停新请求，
仍发现原绑定答复；ANSWERED/consume不解除暂停，只有精确 RELEASE 解除。
提效指标采用有效覆盖（去重核收项/明确范围）、有证据的问题关闭，以及按实际匹配
时间戳分阶段统计的 latency p50/p95；同时报告样本数、观察窗口和未完成/缺失样本，
不奖励 ask_count，也不把执行测试数量直接当覆盖。reply_detected → consumed、
callback 收到 → 核收/disarm、下一包就绪 → 精确 native 收到分别统计；
检测到消费的时长不能直接称为纯空闲或延迟因果，需另核业务活动和归属证据。

空闲 executor 不得死等，也不能因 Codex 主管忙而中断论文任务（用户 2026-10-09 明令）：
显式 `executor_reask.py run` 每 60 秒用新 marker 主动求派，每5秒查答复，单次轮询预算最多540秒；同步 I/O 可延长实际耗时。
退出后原 episode 可保持 WAITING_REPLY，不能把落盘等待称为runner仍在运行。
0.4.27 引入的独立文件 scheduler 按显式 start 的认证登记继续每60秒求派，
最多256个登记，单次 sweep 最多10秒。0.4.32 由已批准的 CURRENT 自身解释
审查过的旧 v2 文件协议：核可信只读完整 MANIFEST、全部实际只读成员、六个 controller
成员和 issuer scheduler pin 的完整组合；已列入的原 release 为0.4.28、0.4.30、
0.4.31，版本号、descriptor 或规范路径本身不授兼容。未知旧来源及历史 v3 不支持；
CURRENT 自身状态仍走当前审批。存在 continuation 就必须合法且 controller 完整相等，
旧 v2 缺顶层 controller 时只能由一致的原登记/continuation 证明，不能补成 CURRENT。
不 import/执行旧模块，不读 Tail/转录或 idle binding，不 transport、consume、唤醒模型
或更新 terminal_pending。首次跨版写前保留一次完整原 state/enrollment 字节；
controller、UNKNOWN、pending、旧 journal 与原询问证据保留。

start 在活动 state/channel 变更前预检 CURRENT、认证 live pair、容量、绑定、
授权和正式占用。PREPARING 不是登记成功；原 intent/INDEX/五成员快照与
registration token 绑定，live state 替换是 commit 点。提交前失败显示
REGISTRATION_UNCOMMITTED；替换后 fsync 或收尾失败显示 COMMITTED_RECOVERY_REQUIRED，
由 sweep 幂等完成原事务，不新建 episode、不回滚可见 commit、不覆盖新 episode
channel。首次提交前失败可恢复原 ABSENT enrollment，不能凭 PREPARING 创建 state。
原 executor 前台认证后可显式 `enroll-existing --episode ID --enrollment-sha256 SHA`；
SHA 绑定原登记字节，仅真实缺失可用 ABSENT。保存旧记录后替换登记，原 controller/
UNKNOWN 不变，不新 episode/tick/consume。新 episode 与旧错误主管登记不自动迁移；
SHA、绑定、授权改变，正式占用或已停止/终结时拒绝补登记。

正式 reservation 屏障独立于协议兼容和 continuation，旧0.4.27普通 WAITING 也受保护。
属于原 caller/workspace 的同主管有效 reservation 暂停求派；合法新主管晚于 episode
的 reservation 持久写 STOPPED / FORMAL_OWNER_CHANGED，结束旧主管求派，不迁移
controller 或转交旧 callback。只有精确 RELEASE 移除对应暂停；marker 消失、TTL、
heartbeat 不释放，也不授继任。无关/非法或更早的外主管 reservation 无效；
noncontinuing ANSWERED/CONSUMED 及 STOPPED 不复活。CURRENT marker/reservation
共用 caller 锁，heartbeat 非阻塞重读、不重建已 disarm marker；普通工具和 Stop 不阻断。
兼容解释器不得消费旧 reply；除 operator stop 外，controller 不同须在任何授权、
receipt/state 写前返回 ORIGINAL_CONTROLLER_REQUIRED。
显式 start --file-only 与 transcript 通道互斥。安装、登记、scheduler真实执行、
活跃客户端自动hook、正文完整读取分别留证；两轮真实continuing须由原执行者和
主管完成request→reply→全文读取→精确SHA consume→rearm，其他会话不能代消费。
未登记旧 episode 不自动接管，文件tick不证明模型被唤醒。
每轮记录已配置文件通道的实际写入，空 channels/错误不冒充送达；
终端只在受保护输入条件成立时发送。新普通消息超过700 UTF-8字节或含任意 CR/LF/tab，
由同版发送器固定完整正文并发送短通知，保留原 marker 与全部空白；
通知收到不等于正文已读。正式 task/callback 保持专用绑定。
`cmux_executor_reask_stop_guard.py` 的全局注册仅作 advisory 观察；
主管先按原 caller/supervisor/task/episode/marker 写精确 mailbox 答复，让显式等待返回，
再做新鲜 live preflight 与正式派包；TASK 答复本身不是派包。旧新派发出口依赖 idle
binding，现役 advisory hook 不更新该绑定，不能宣称写了新包就会自动退出求派。
operator stop 保留；不将未完成后继方案标成已部署。主管无工具事件时，文件请求
提示也不会运行，不能称为已唤醒空闲主管。旧接收进程退出时保留原 pending，不改绑或重贴。
默认 `executor_ready.py persist` 仅是单请求有界观察。CCC 与 native Goal 单独核验。
主管回复沿原 bridge 到达原 surface，或写原请求指定 mailbox；
回复要绑定 loop record 的原 episode_id、caller_surface_uuid 和 task_id。

Claude 新版状态栏可在 CLAUDE.md 与 MCPs 之间显示规则计数。只由同版
bridge 在完整边框外识别；输入框内同样的文字仍保留为草稿。未知格式不清空，
空输入不等于回合空闲，更不等于消息送达；沿原生接收证据结算。


显式投递与嵌套核收保持同一原生 caller 采集来源，每次仍重新核验进程和 cmux 树；
共享后台继承的 workspace 不得替代实际客户端。完整 Claude 边框成立时，报告及
recap 中引用的历史 Compacting/Reconnecting 不代表当前状态；只核当前 activity。
Codex steer queue 标题和已测 warnings 尾行按各自结构识别，真实压缩、重连与
未知界面仍不输入。界面兼容不降低原 fence 后完整 native user 的逐字核验。

通用实现只在协作 skill 维护，本文不复制发送器或 hook。报告/pack/既有
attempt 保留原字节，原锁下核收可追加观察及原子发布 receipt；旧任务沿原
控制器，不把新模块单独覆盖到旧 runtime。源码、安装、实际 hook、客户端
加载、原生接收及论文验收分列，不因通信维护重开科研审轮。

两个用户指定的 Claude 可分别承担档案核查和工具审查等独立工作，各自任务包、nonce、产物目录和回调独立；共享代码由一个写入者维护。两个 executor 若同 pane 的不同 tab，则计算可并行，UI 输入须串行按 UUID 重新核验。健康 executor 不因另一位故障重启；持续失效者冻结写入后按已授权单 agent 模式接续，避免维护流程拖住论文交付。

先按[以研究进展衡量协作效率](references/efficient-collaboration.md)划分有界任务：
数据采集保持唯一负责者，第二执行者只解决独立未决问题；报告、回调和资源释放分别核收。
原回调已验证且对应任务监控已解除后，停止该任务的回调探针，不让通信排障持续占用研究执行者。
经验文档更新不表示运行中hook已经改变。

用户授权双 agent 时优先复用已绑定的 Claude 会话，并用 `multi-agent-collaboration` 的真实握手与任务包。可重试 Claude API 故障必须从第一次真实失败起，取得至少连续 300 秒均失败且门槛后有新鲜失败的证据，才可判断该执行者暂时不可用；任何真实 API 成功重置计时，静屏、排队、未知状态与重试次数均不能代替。等待期间推进独立工作；满足门槛后仍须冻结原执行者、核实无并发写入，再依既有授权接管。认证/计费/额度故障不盲重试，用户明确停用或撤回授权单列，详见[协作与恢复](references/collaboration-and-recovery.md)。恢复沿原会话、真实新握手和单写交接；单 agent 自审标 `solo_self_review`，其他 Codex 会话的独立审查单独署名，不能冒称 Claude 参与。

Word/Zotero 是串行应用资源。NLM 的账号预算与执行容量分开：已有真实证据和固定执行器支持两路时，复用该能力；缺少对应能力时使用串行入口。同账号单并发是本地兼容策略，不能称为 Google 官方安全上限；不同 notebook/target 仍共用额度。多任务按 [并发能力与自动调度](references/nlm-concurrency-and-scheduling.md) 消费固定 READY，真实归还后自动轮转，离线裁决并行。资源交接与论文验收分列；未知终态保留隔离，不能预填“无在途”。

在已绑定且健康的 NLM 环境中复用既有 target/transport，不为便利新页、导航、登录或改 default。确有认证或原传输失效时，按 [同账号认证恢复](references/nlm-auth-recovery.md) 在安全边界沿用户既有授权恢复；不重发原未知请求、不换账号绕限额。账号限额兼容 legacy daily count、compute/weekly、unknown，以带时间的官方信息和账号真实响应为准，不写死 500/24 小时。

遇到“NLM 又连不上”，立即按 [连接诊断与自动接续](references/nlm-connection-recovery.md) 区分代理 TLS、认证、请求终态、引用缺口和本地恢复异常。先复用原失败证据，必要时用 `scripts/nlm_tls_probe.py` 沿原路只握手、在源站 HTTP 前关闭；由原执行者用一条未提交的必要审读恢复，再自动接续既有容量。用户已授权恢复时直接执行，不重复询问同一许可。握手成功不能单独宣布 query 恢复，原因未证实时保留 UNKNOWN。

HTTP 200 中的 `REGION_NOT_SUPPORTED` 是服务实际返回的地区拒绝，不能误当 TLS、认证或额度故障。先核原响应、实际代理进程与路由；端口未变不证明出口未变，节点名称也不证明服务识别地区。在既有授权内固定任务私有路线，保留账号和已提交请求，再依真实状态/历史及必要长答验证恢复。原会话读取成功、长答成功和后继续行分别记录，不据一次成功保证永久稳定。

恢复决定先经 `scripts/nlm_recovery_preflight.py` 检查：脚本、日志、二进制附件按原字节哈希固定，再包入 JSON 证据清单，不能把附件本身当 JSON 解析。预检不写健康、队列或预算；实际准入边界重新核验后沿原 journal 执行。此兼容工具无需改动正在运行的固定健康模块；安装新工具与现役 adapter 接入分别记录。

预检须在实际工作器的解释器和固定依赖路径中执行，不能用另一个 shell 的 `python3` 导入成功代替。沿 [运行时检查](references/runtime-validation.md#nlm-工作器的离线依赖预检) 核实 SDK、HTTPX、HTTPCore、h2 的真实文件，并在不发请求的情况下构造、关闭实际 HTTP/2 transport。缺 h2、导入失败或本地参数错误记作本地执行故障；先离线修复原入口，不据此称 NLM 不可用、重发原 query 或换传输参数。

文件来源的注册、上传会话、文件字节、处理 READY 和全文验收分别记录。SDK 可能为同一操作创建多个 HTTP 客户端；离线预检须覆盖实际客户端序列和共享追踪记录。已取得真实 source ID、但本地构造失败且文件上传未发送时，保留原失败并沿该 ID 完成尚未提交的阶段，不再次注册；见 [多客户端与来源阶段](references/runtime-validation.md#文件来源的多客户端预检)。

源站 HTTP 200 后断流时，按 [原会话状态与历史核收](references/nlm-stream-interruption-recovery.md) 处理：保留已提交请求，核原会话身份，各做一次必要的状态/历史读取；主答案为空的思考帧不计答案，空历史本身不证明终态。同步核请求窗口内真实断链、换网和地址变化；晚于错误的 reset 不倒置为原因。原请求真实归还后，用一条尚未提交的必要题恢复，随即接续既有队列。不要为每次断流重新设计整套恢复流程。

本地无字符期限触发时，先核到底是本地计时器取消接收，还是收到真实网络错误。可在安全归还后的后继绑定使用 `scripts/nlm_stream_wait.py`：无进展先记录告警并继续等待同一个读取任务，总期限保持有限且不因新字符重置。该模块不发请求、不读远端状态、不重 POST、不释放未知租约；安装不自动改变现役传输。原会话历史读取若在 TLS 阶段失败，应记为未取得历史，不能记为空历史；依已授权范围在真实可用窗口对同一会话做一次有界只读恢复，优先取回原答。

同机另有网络修复或断线验收时，由原 NLM 执行者在真实无在途边界暂缓下一组，再将窗口交给原网络任务。收到测试实际结束及连接状态回执后复核原边界，自动续原 READY；预计时长经过、普通上网成功与网络锁定状态都不能替代长答终态。窗口交接直接沿用既有恢复授权，详见上述断流流程。

尚未交出的维护预约可明确撤销，由原执行者在新鲜边界只解除该次准入暂停；查询健康另行判定。已经交出的窗口必须等实际归还，不能因预计时长已过自行开调用。后续网络操作必须取得新窗口。

查询健康状态使用 `scripts/nlm_query_health.py` 与 `scripts/nlm_query_health_store.py` 消费原始归还回执并持久化。完整收回但连续空答、单题恢复空答、明确额度/认证故障或传输不完整时保留暂停；空答本身的原因记为未知。会话重启、来源上传成功、迟到的普通成功和旧提示均不会自动解除暂停。实际协调者用新证据固定一条必要请求作恢复，真实有效答案后再继续；安装模块不表示现役执行器已自动接入，具体绑定及真实回执重放另行记录。

## 交付与安装

工具复盘和跨仓维护读 [工具链经验及版本边界](references/toolchain-retrospective.md)。成品冻结后用 [清单生成交付链接](references/delivery-manifest.md) 核角色、目录/ZIP成员和真实字节，再输出聊天链接；解码、文件可读或消息送达不能单独表示内容接受。

交付当前有效候选清单、Word/PDF 哈希、逐条处置、实证复盘报告、NLM 原始回答与本地裁决、独立完成轴和资源释放回执。正式论文包冻结后，经验工程进入新的任务目录，不重复原任务模型。

本仓是通用维护源；历史章节材料、账号绑定和本机运行日志不进公开仓库。旧安装的章节专用脚本和参考资料会备份保留，但不能覆盖本入口的双循环与验收契约。安装步骤见 [README](README.md)。

## 双向投递与高效协作维护

执行[接收端绑定投递](references/receiver-bound-delivery.md)和[高效协作](references/efficient-bidirectional-collaboration-20261004.md)：新Codex消息及callback经原会话native steer/start一次输入，不操作composer或Enter/Tab队列。Claude终端仍核完整稳定原文后提交一次。只有原fence后新增、全文相等的native user证明收到；RPC接受、正文已读、执行与论文接受分列，未知仅观察原次，不重放历史callback。


## 归档双执行者现场经验（2026-10-05）

见[归档回调与独立收尾](references/archive-callback-boundaries-20261005.md)。区分原生入站、正式回执与候选补丁实效；仅文档增量，不替换在途控制器。


## 共享后台与回调收尾

见[共享后台身份与有界回调收尾](references/shared-daemon-caller.md)：统一核实 caller 与任务归属；原次回调零输入核收，等待期间继续主线。

共享后台误认本方客户端时，按[协作提效与收尾](references/collaboration-efficiency-and-closeout.md#共享-daemon-与重复-tty-的正确归因)核唯一原生客户端及 UUID；其他窗口残留同名 TTY 不能否决它。不称 Claude 身份失败、不伪造环境；修复须进入实际启动器与 hook。两个已授权 Claude 的独立工作并行，同 pane 输入串行，已通过的本任务握手直接复用。

普通终端原 Claude 因 login 的 EPERM 无法调用工具时，按[权限边界与原任务接续](references/shared-daemon-caller.md#普通终端的-login-权限拒绝)核本地 Hook；不重发原任务，不重做已完成的原生动作。

完成消息已到达而执行者仍等待时，执行[主管核收与原会话恢复](references/completion-settlement-recovery.md)：优先结算原次回调、独立裁定、精确解除该任务，再以原会话真实回复核验恢复；不要误判 API 死亡或重复派审。

新粘贴统一采用单行：普通/握手用同版 MESSAGE_REFERENCE_V2 保存完整正文；
正式任务经 submit_task_pack 的 TASK_PACK_V2 绑定完整包SHA；callback保持
专用原文。共享门禁拒绝任意 CR/LF/tab 或超过700 UTF-8字节的新粘贴，旧次不重贴。
只有原接收端新增完整 native user 才证明收到；真实 callback 和活跃客户端
自动hook分别留证，手动hook测试不冒充自动加载。验收后接回用户原任务。

## 历史投递接续

原任务包、报告及原 attempt 保留不变。旧 controller 零输入 reconcile 与
新主管维护握手分开：前者核原次，后者建立当前联系，不要求先修好旧主管。
不要用新 nonce 重放已输入、排队或未知消息。未确认状态如实保留，普通工具开放。

## 继承业务会话与恢复协作

继承的业务 session、当前 thread 和当前原生客户端分别核实。新建或切换
Codex 线程复用协作 skill 的原生 foreground 选择与内核/UUID 认证，不能
借用旧 surface。主管身份识别失败不是 Claude API 故障；按已有 SOLO 授权
继续独立正文、证据或排版工作。修通信不能重开已接受的科研审轮。

恢复的原 Claude 仅承担独立未完成交付物；先接空闲者，另一位到安全边界后
再派单。同 pane 不同 tab 只并行计算，输入串行。更新的原生成功、新回合和
真人接管优先于历史错误。源码、安装、自动 hook、原生收到和业务核收分别
记录；当前任务握手、派包与报告前不能声称 Claude 参与，SOLO 自审保持原标注。

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

## 排队请求与正式通知恢复

主管在重要工具边界、长批次前和进展报告前，读取当前 surface 的 queued follow-up
inputs，校验固定正文的 SHA/字节数并按原请求 mailbox 回件。相同 marker 去重，
记录已消费和仍待办项；排队、正文已读、native user、ACK、报告接受分别报告。
不因持续运行而让其他主管的维护请求长期不可见。

0.4.22 已测支持完整边框外的模型、目录、计时三行 Claude footer；未知布局与
现有草稿仍保护。0.4.23 在创建正式任务 journal 前校验单行和长度。新派单从
finalized pack 生成 TASK_PACK_V2，不手写旧多行模板。旧 wire 格式若严格零输入
（第一 attempt 为 NO_INPUT、events=[]），由原主管调用协作技能的
repair_task_notice.py；先只读 READY_ZERO_INPUT，再执行一次 --apply。它验证
并使用完整原 controller，原 pack/nonce/callback 和旧 attempt 不变，只追加
唯一第二次尝试。未知、已贴、排队、已收到消息不得转换或重贴。其他情况保留
未确认并继续独立正文/证据工作；健康握手不重跑，已接受科研审轮不重开。

2026.10.13.3 另采用协作 `scripts/resume_task_no_input.py`，用于原 Claude
正式派发连续零输入预检耗尽后的显式恢复。默认只读；`--controller` 指原不可变
source，`--surface` 指原 executor，`--task-pack` 和 `--text-file` 指原 pack 与
精确 notice。计划返回完整连续 attempt 清单的 `history_sha256`；执行必须
`--apply --history-sha256 SHA` 精确匹配该原清单。
全部历史须为 NO_INPUT、events=[]，且只因 COMPOSE_OCCUPIED 或 RECEIVER_COMPACTING
退出；原身份、完整 native binding、锁、pack/payload/nonce 不变，当前 composer 空且
可输入，才保留全部原字节并通过完整原 controller 追加一次 attempt。
任一 PASTE_INTENT、native input intent、UNKNOWN、队列、receipt 或历史改变即拒绝；
再次遇草稿仍保留，不清空。普通自动预检仍最多两次；零输入不等于实际发送预算耗尽，
此入口只解除经完整证据确认的预检死锁，不重发未知输入。安装及实际采用分别核验。

原握手迟到ACK使用协作 `scripts/observe_handshake_ack.py` 有界只读观察：固定原
不可变controller、超时receipt及SHA、dispatch attempt及SHA、精确notice。
另写观察证据，原task/nonce/超时回执/发送日志保留，不输入或核收旧次；短通知原生
收到、完整正文读取、真实ACK和业务接受分别报告。

在原 harness 已退出且完整超时证据保留后，原主管可使用
`scripts/reconcile_handshake_ack.py` 先只读预览，再显式 apply，以原控制器的
writer/validator 核收原 nonce；共享维护者不能代原主管执行。
queued 附件与真实 ACK 不冒充完整 native user，未证通知接收继续未证。

0.4.33 另支持原 REJECTED / DRAFT_NOT_READY / STRANDED_IN_COMPOSE 握手，
须核完整原 PASTE_INTENT、PASTED 和 DRAFT_OBSERVATION 且没有提交记录；
草稿、原通知接收状态及发送历史保留。0.4.34 允许唯一精确 text ACK 与严格结构的
thinking / redacted_thinking 块共存，不输出 reasoning 内容；额外文本、工具块、
畸形块、nonce 或空白差异均拒绝。不用全局 strip/rstrip 修复 composer 差异。

共享维护只有一个合并者。其余主管提交原证据与明确 reply_path 后继续主线；
Claude、协作子 agent 或模型 API 不可用时，按已有授权转 SOLO。双 Claude
仅接独立未完范围，同 pane 输入串行；恢复后在安全边界复用原上下文会话。

0.4.24 修复本地 SQLite 只读清单和磁盘空间统计的 Python heredoc 误判：字符串内分号后的 Claude 文字仍是正文，不是启动命令。原命令和输入原样保留，按实际 hook 复验；别通过改写关键词规避。相邻真实启动、执行代码与终端输入继续单独核验。

0.4.32 补齐单引号消息中 `; Codex alone` 的残余 launch 误判：按 shell 代码与
literal 数据边界识别，不改写原消息规避。真实相邻 agent CLI、可执行嵌套 substitution
及 wrapper 命令仍检查。以原命令的零输入 `--check-command` 和真实 hook 入口作离线
回归；此前0.4.24/0.4.27的 literal/heredoc 修复不重复记为新增。

按用户最新至少20GB要求主动备份与核验终态缓存，空间不足仍推进独立工作。
继任握手、迟到ACK及同pane原生Codex限定通信见
[协作提效与收尾](references/collaboration-efficiency-and-closeout.md)。
