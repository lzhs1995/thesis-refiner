---
name: thesis-refiner
description: Refine empirical thesis chapters through full local evidence tracing, concise revision, Word-native verification and grounded NotebookLM review. Use for a submission manuscript or a reproducible review of its claims, tables and figures.
metadata:
  display_name: 论文精炼助手
  aliases: [论文精炼助手, 论文精选助手]
---

# 论文精炼助手

目标是形成有据可查、可提交的精简文稿。精简以前必须全量追溯初稿的实证链条；文字删减量不是完成指标。保存用户原始问题、研究设计、目标稿件、允许补核范围和完成条件，恢复任务时先读这些记录。

## 两个交叉推进的循环

**循环 A**：冻结初稿 → 全量清点主张、表图、公式、脚注和附录 → 追溯数据、清洗、变量、样本、模型、输出和论断 → 精简修订 → 按发现补核数据或更新图表 → 再修订。

**循环 B**：候选 Word → 原生刷新、排版和 PDF → NLM 长文审查 → 本地逐项裁决 → 修改 → 新版本复核。严重的数据、图表或模型冲突立即回到 A；可以并行做不受影响的离线工作。NLM 的回答是待核实的审查证据，不能取代数值、来源身份和视觉检查。

开始实际工作时读 [双循环与证据契约](references/dual-loop-workflow.md)。NLM 阶段读 [完整审查与额度协调](references/nlm-review-and-budget.md)；多会话或执行者故障时读 [协作与恢复](references/collaboration-and-recovery.md)。原生 Word 阶段使用 `officecli-word-revision`，R/描述表使用 `clauder-rstudio-workbench` / `comparegroups-guide`，Stata 使用其共享会话 skill。各领域工具产出真实回执，本 skill 消费这些回执。

## 可执行入口

从本 skill 的安装根执行。输入/输出路径必须属于当前任务的新 run 目录。

```bash
python3 scripts/workflow.py inventory --input /absolute/original.docx --output /absolute/run/original-inventory.json
python3 scripts/workflow.py audit-chain --input /absolute/run/checkpoint.json
python3 scripts/workflow.py affected --input /absolute/run/checkpoint.json --changed model-id
python3 scripts/workflow.py acceptance --input /absolute/run/checkpoint.json --output /absolute/run/acceptance.json
node adapters/codex/closed-loop-orchestrator.js --checkpoint /absolute/run/checkpoint.json
```

`inventory` 是机械全量清点，覆盖正文、表格、公式、图片、脚注、尾注、页眉页脚及媒体。Agent 仍须把每段的多个实证主张拆开；数字提取不是语义复盘。每个原稿条目都要处置，未改条目也须审读。模板字段和示例见 [checkpoint 契约](references/checkpoint-contract.md)。

`acceptance` 必须读取存在且哈希一致的真实回执。编排器只消费证据；没有实现的自动 Word 修改/估计路线不会模拟成功。`--dry-run` 只能返回 `SIMULATION_ONLY`，不授予 A5。受影响依赖清单用于决定下一步，不自动扩大重跑范围。

## 不可混淆的完成状态

- 找到文件、数值相容、找到唯一来源、全模型重估分别记录。
- 正常结束、有效标准误、保存的有效抽样和逐次收敛分别记录。
- 文档交付完成与完整实证复现分别报告。必要且已接受的科学 partial 可以保留；不得把它们改名为复现通过。
- 正文与附录单独验收。只复用哈希、来源与审查范围均一致的证据；一个文件变化不自动让另一个失效。
- 正式终验必须在最终 Word/Zotero、格式、实际 PDF 字体和视觉检查后，对同一冻结 PDF 完成连续两轮完整审查。没有新的本地确认问题，既有确认问题全部解决。三轮同一问题只触发专项裁决，不能自动通过。
- HTTP 200、空控制帧、上传 READY、退出码 0、同事的 DONE 和模拟回答都不能单独表示审查完成。

## 执行模式和资源

用户授权双 agent 时优先复用已绑定的 Claude 会话，并用 `multi-agent-collaboration` 的真实握手与任务包。用户已授权自动接管时，执行者发生持续故障即保存回执并按安全边界转 Codex 单 agent；不能因此停止整体任务。单 agent 自审标 `solo_self_review`，其他 Codex 会话的独立审查单独署名，不能冒称 Claude 参与。

Word/Zotero 是串行应用资源，NLM 是账号级共享资源；不同 notebook/target 不代表独立额度。用统一资源队列及实际 OS 锁。资源交接与论文验收是两件事。网络结束即归还 NLM 窗口，再离线裁决；请求终态未知时保留隔离并核清，不能预填“无在途”。

在已绑定的 NLM 环境中，始终复用既有 target/transport，不新页、不导航、不登录、不改 default。账号限额兼容 legacy daily count、compute/weekly、unknown，以带时间的官方信息和账号真实响应为准，不写死 500/24 小时。

## 交付与安装

交付当前有效候选清单、Word/PDF 哈希、逐条处置、实证复盘报告、NLM 原始回答与本地裁决、独立完成轴和资源释放回执。正式论文包冻结后，经验工程进入新的任务目录，不重复原任务模型。

本仓是通用维护源；历史章节材料、账号绑定和本机运行日志不进公开仓库。旧安装的章节专用脚本和参考资料会备份保留，但不能覆盖本入口的双循环与验收契约。安装步骤见 [README](README.md)。
