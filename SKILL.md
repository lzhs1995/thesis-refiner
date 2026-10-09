---
name: thesis-refiner
description: Refine empirical theses through evidence tracing, concise revision, native document checks and grounded NotebookLM review; derive requested defense slides, scripts and audio from verified manuscript versions.
metadata:
  display_name: 论文精炼助手
  aliases: [论文精炼助手, 论文精选助手]
  version: "2026.10.10.1"
---

# 论文精炼助手

本次配置与主动求派修订纳入 **2026.10.10.1 版本契约**，保留原生核验、
同版安装及用户已授权的每60秒新 marker 主动求派。默认有界观察与该可选
求派入口分别记录。共享协作 release 的安装、客户端实际加载、Claude →
supervisor 原生 receipt 和正文已读分别核验；文档与离线检查不证明现役采用。

cc-switch 切换、全局 hook 与每60秒求派按
[全局通信配置](references/global-communication-configuration.md)执行：复用协作
skill 的唯一守护器，原消息未确认时走文件通道；每个工作区通过后立即回原任务。

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

## 同 workspace 握手硬门禁（不可绕过）

只准与 **当前真实 caller 所属 workspace UUID 相同** 的独立 terminal pane 中的 agent 握手。
每次先读 `cmux identify --json` 的 caller，再与实时 tree 的 UUID 对齐；focused、标题、旧摘要、
历史 surface 编号和环境变量都不能代替身份。用户指定的 executor surface UUID 必须同时精确匹配。
指定工作区与真实 caller 冲突即拒绝输入，不能回退旧 Claude、伪造身份、搬动面板或另开会话。

必须使用 `multi-agent-collaboration` 的 `cmux_workspace_guard.py`、现役 PreToolUse hook 和
受保护的 `cmux_bridge`。harness 固定 `--expected-workspace-uuid` 与
`--expected-executor-uuid`；bridge 在每次粘贴和按键前重核，并用双 UUID 发送。
跨区、缺 UUID、旧绑定、面板移动或身份不明一律 fail-closed，零发送。裸 `cmux send/send-key`
被 hook 拒绝。普通消息可直接调用绝对可执行 helper 的 `ask/send/broadcast/reconcile`，
但完整渲染字节、同版 adapter 与 Python 必须通过守卫核验；允许 `rtk`/`rtk proxy`
前缀，拒绝 shell/env 包装、嵌套、重定向及替代发送器。helper 仍走唯一 guarded bridge，
正式任务包与 callback 使用各自绑定专用入口；不得借 STATUS、force 或超时绕过。
用户明确指定的目标可存于协作 skill 的 caller-scoped workspace-scope 文件，不因不可用自行撤销。

跨工作区资源协调继续使用现有文件/队列回执，不借资源协调重新指定 executor。
安装后实测 hook 的 exit 2 与零输入；配置写入不等于运行中客户端重载，旧导入模块也不算自动更新。
协作 skill 缺失或身份门禁未通过时，禁止发送；已授权的单 agent 离线工作可继续。

## 执行模式和资源

按[协作提效与收尾](references/collaboration-efficiency-and-closeout.md)决定零、一或两个 executor，使用相位握手预算，及时结案已接受成果；通信维护不扩大为新科研审轮。

交付后执行[有界收口运行规则](references/executor-closeout-enforcement.md)：
协作 skill 的 PreToolUse 冻结报告、task pack 和原 attempt，保留严格 task-bound
只读诊断与原 controller reconcile；Stop 接受普通诚实 WAITING_SUPERVISOR
说明，无须唯一精确 STATUS 模板。回调未确认交主管核原次；不能为回执追加测试。
本 skill 复用同一实现，不复制第二套发送器或 hook。

主管核收/disarm 后须[交回结论和下一步](references/collaboration-efficiency-and-closeout.md#子任务收尾后仍由主管推进整篇)。
正常子任务收尾不等于 API 失败或论文完成；新授权查询以最新回执为准，不能永久
沿用旧 recap，也不要让用户替已有主管通道转话。

握手只做身份与通道验证：首条消息直接给出 pending receipt 的绝对路径，executor 读固定文件后回精确 ACK；不在握手期间查全盘、审论文或做三轮共识。健康的同任务握手复用；短观察窗口耗尽不能冒称 executor 失联，迟到 ACK 按原 nonce 只读核收，不重复发送。

探针全文消失不能证明输入区已空；残留前缀、暂时缺prompt glyph和外来文字按
协作harness的有界清理后置条件处理。正常ACK等待及原nonce恢复记录为
`AWAITING_EXECUTOR_ACK/PENDING`，不提前报FAIL。短探针仍逐键核身份、保留
600秒预算；详见[握手清理与等待状态](references/collaboration-efficiency-and-closeout.md)。

**双向通信遵循[原生投递与有界等待](references/verified-compose-delivery.md)。**
只有同一 workspace/surface/process/session/transcript，在原 PASTE_INTENT
新鲜 EOF fence 后新增、全文完全相等的 native user 才为 NATIVE_RECEIVED；
保留全部空白。Claude `queued_command` 仍 pending，屏幕、ACK、按键返回、
队列和空输入区不证明收到。

首次只粘贴一次，完整草稿稳定后提交一次；忙碌 Codex 明示
`tab to queue message` 且完整草稿匹配时直接 Tab，其他清晰受支持状态 Enter。
原次恢复先核迟到原生记录，自动/显式恢复共用最多一次补键，意图落盘即耗用。
当前 `--recover-stranded` 只用于 `submit-text` 的原 NATIVE_PENDING、
PASTE_INTENT/ENTER_SENT 及未耗预算；任务/callback 只读 reconcile。
未知、压缩、排队、重连或结构改变不补键，缺原 binding/fence 不追补、不重贴。

自动 PostToolUse 成功结果按客户端官方 JSON schema 输出：只把完整核验结果放进
hookSpecificOutput.additionalContext，hookEventName=PostToolUse；内部 action/results
不得直接作为顶层输出。以活跃客户端的自动执行记录核收，不用手工运行、配置
注册或离线测试替代。完整原生消息、真实 callback 与自动 hook 仍分别留证。

协作 skill 的 `cmux_native_delivery_guard.py` 在 PostToolUse 只核当前投递，
不扫无关旧账、不发键、不造 receipt，也无 disable/advisory 绕过。
封口保留严格 task-bound 诊断与原 controller 核收；Stop 接受普通诚实
WAITING_SUPERVISOR（continue:false、suppressOutput:true），保留 task/receipt，
无证据的 confirmed/共识声明仍拦。Stop/SubagentStop 重入只认严格布尔
`stop_hook_active is True`；不 disarm、不授论文完成，下一正常 turn 继续核验。

主管通过认证 active markers 有界发现冻结报告（PostToolUse
`cmux_supervisor_report_guard.py`，REPORT_DISCOVERED），再独立审读并裁决。
发现、实际接收、正式 receipt、论文接受和 disarm 分别留证。
空闲 executor 不得死等，也不能因 Codex 主管忙而中断论文任务（用户 2026-10-09 明令）：
`executor_reask.py run` 每 60 秒用新 marker 主动求派，直到主管答复或新派发，无轮数上限；
每轮记录已配置文件通道的实际写入，空 channels/错误不冒充送达；
终端只在受保护输入条件成立时发送。新普通消息超过700 UTF-8字节或含任意 CR/LF/tab，
由同版发送器固定完整正文并发送短通知，保留原 marker 与全部空白；
通知收到不等于正文已读。正式 task/callback 保持专用绑定。
可选 `cmux_executor_reask_stop_guard.py` 约束已授权等待段，
主管答复、新派发或 operator stop 均可结束；不将未完成后继方案标成已部署。
默认 `executor_ready.py persist` 仅是单请求有界观察。CCC 与 native Goal 单独核验。
主管回复沿原 bridge 到达原 surface，或写原请求指定 mailbox；
回复要绑定 loop record 的原 episode_id、caller_surface_uuid 和 task_id。

Claude 新版状态栏可在 CLAUDE.md 与 MCPs 之间显示规则计数。只由同版
bridge 在完整边框外识别；输入框内同样的文字仍保留为草稿。未知格式不清空，
空输入不等于回合空闲，更不等于消息送达；沿原生接收证据结算。


自动 hook 的嵌套核收保持同一原生 caller 采集来源，每次仍重新核验进程和 cmux 树；
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

执行[接收端绑定投递](references/receiver-bound-delivery.md)和[高效协作](references/efficient-bidirectional-collaboration-20261004.md)：完整原文稳定后按 provider 提交键，只在绑定原生日志核整条相等原消息；排队、运行、回执和论文接受分列，未知仅核原次。


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

## 首次确实零输入时的唯一接续

仅当原任务包、报告及原 attempt SHA 均未变，且 journal 只有 attempt-0001、
phase=NO_INPUT、events=[]、无 receipt/pending，closeout hook 才允许执行一次
任务包所固定的原 controller 同步 callback CLI（rtk proxy + 原 Python -B）；
入口和参数必须完全匹配，不开放其他工具或替代发送器。原 controller 仍重核
活跃身份、完整稳定草稿及最多两次 attempt 的预算。已输入、已排队、未知状态
或第二次 attempt 均不适用，只能沿原证据核收。普通诚实 WAITING_SUPERVISOR
仍可结束回合，不强迫重试。完整原生收到、真实 callback 与自动 hook 分别验收。
