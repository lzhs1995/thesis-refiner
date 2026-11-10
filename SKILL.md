---
name: thesis-refiner
description: Refine empirical theses through evidence tracing, concise revision, native document checks and grounded NotebookLM review; derive requested defense slides, scripts and audio from verified manuscript versions.
metadata:
  display_name: 论文精炼助手
  aliases: [论文精炼助手, 论文精选助手]
  version: "2026.11.02-herdr.1"
---

# 论文精炼助手

目标是忠实原稿语气、证据可追溯、可提交的论文；修改数量不是质量指标。

先读任务检查点，复用已验收结果、原稿风格样本和原参与者。
实际研究按[双循环与证据契约](references/dual-loop-workflow.md)推进：
循环A核数据、模型及论断，循环B核Word/PDF、来源审阅和本地裁决。
两者按真实问题交叉，不为工具维护重做已完成审轮。

## 按任务加载

- 多agent分工和原稿文风：读[分工与忠实审阅](references/voice-and-collaboration.md)。
- 各章独占cmux workspace、内嵌Herdr团队、senior supervisor统稿：读
  [分层章节工作流](references/chapter-teams.md)。四种合作模式与五条
  协作规则引用已绑定MAC的共同契约，纯cmux论文任务仍支持。
- 传输由已绑定的multi-agent-collaboration维护：新任务先读其
  `references/collaboration-profiles.md`；Herdr使用其轻量入口，cmux使用原传输。
- 既有任务或cmux专门恢复：按需读[原版完整流程](references/cmux-legacy-entry.md)，
  旧controller、回执和已授权continuing登记不迁移。
- NLM阶段：[完整审查与额度](references/nlm-review-and-budget.md)。
- 新任务可选 [有界 SDK 入口与依赖绑定](references/nlm-sdk-adapter.md)；仅已确认来源和持久会话，保留原账号队列与预算，不切换同名 MCP 或在途控制器。
  任一新SDK入口须沿领域NLM路线门槛：不能只核代理端口；prepare和发送前核实际监听进程、固定路线及连接所用节点，缺证据在发送前拒绝。本机节点与凭据只写私有任务绑定。
  [NLM 专属强制 hook](references/nlm-network-hook.md)须由客户端固定政策与哈希：未绑定的 MCP/CLI/SDK 网络调用拒绝；只放行已钉入口，入口再次核验专属路线。读取技能或安装文件不等于客户端已加载 hook。
  若任务已绑定有界执行扩展，继续其240秒总期限、90秒无进展规则及原预算；
  不把超时当服务端取消，也不重复询问已有作废许可。
- Word原生检查使用已绑定的officecli-word-revision；保留引文域、
  修订、公式、表格与图像，实际保存重开及PDF检查分别留证。
- 故障与接管：读[协作与恢复](references/collaboration-and-recovery.md)。
- 跨章统稿：[证据复用与总稿绑定](references/evidence-reuse-and-integration.md)。
- 交付链接：[交付清单](references/delivery-manifest.md)。
- PPT：[制作与审校](references/ppt-production-and-review.md)；
  音频：[音频概览与验收](references/nlm-audio-overview.md)。

## 完成口径

找到来源、数值相容、完整模型重估分别报告；建议、拟采纳、实际写入和
最终核收分别计数。科学partial、翻译保留及来源缺口不得改名为PASS。
正式终验仍须最终Word/Zotero、格式和真实PDF检查，以及绑定流程要求的
同一冻结PDF连续两轮完整审查。获准的有限交付明确报告未满足项。
NLM回答是待核证据，HTTP200、上传READY、退出码0及同事DONE均不等于验收。

通用协作契约只在MAC维护。本skill不复制发送器、身份库或hook。
全局hook已安装不代表当前任务入组；原工具授权持续有效。
JEV仅在另行评测通过的排序/分流任务中采用，不增加当前论文收尾依赖。

可执行入口保留：`scripts/workflow.py`的inventory/audit-chain/affected/acceptance，
`scripts/delivery_audit.py`及既有adapter。新版skill不更改其科学验收逻辑。
