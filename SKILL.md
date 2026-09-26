---
name: thesis-refiner
description: Refine empirical theses through evidence tracing, concise revision, native document checks and grounded NotebookLM review; derive requested defense slides, scripts and audio from verified manuscript versions.
metadata:
  display_name: 论文精炼助手
  aliases: [论文精炼助手, 论文精选助手]
  version: "2026.09.26.10"
---

# 论文精炼助手

## macOS 自动化故障：优先执行规则

用户已明确授权自动处理时，沿用该授权，读取当前安装的 `officecli-word-revision/references/macos-tcc-zotero-word.md`，不得再次把同一个 Automation 开关或确认问题交给用户。先按实际发送方核查，再按已授权范围自动恢复；TCC.db 备份/重置是有证据的恢复动作，不是普通文稿流水线的隐含动作。多个 agent 只保留一个恢复执行者，其余继续离线工作；Claude 持续失效时沿既有授权切换 supervisor 单 agent，不停整个任务。实际原生操作未通过前，不得把“已记录规则”“权限条目存在”或“退出码0”称为恢复成功。

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

## 执行模式和资源

用户授权双 agent 时优先复用已绑定的 Claude 会话，并用 `multi-agent-collaboration` 的真实握手与任务包。用户已授权自动接管时，执行者发生持续故障即保存回执并按安全边界转 Codex 单 agent；不能因此停止整体任务。单 agent 自审标 `solo_self_review`，其他 Codex 会话的独立审查单独署名，不能冒称 Claude 参与。

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
