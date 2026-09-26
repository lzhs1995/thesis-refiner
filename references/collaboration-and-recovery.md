# 协作、租约与恢复

通用实现归 `multi-agent-collaboration`。论文任务包只附研究 profile、完整清单、保护路径、文档适配器精确 SHA、当前模式与任务 checkpoint，不把论文判断硬编码进通用协作工具。

双 agent 必须有当前任务的真实握手、独立 nonce、报告和回调哈希。旧章节 DONE 不能证明新 skill 工程的参与。502/504/524 等明确 retryable 临时故障最多三轮同会话重试，间隔至少 60 秒；401/403、计费/额度/no-account 不盲重试。投递不确定、消息排队、迟到回调和监督端预算太短先归因，不能伪装成 executor 计费故障。

已获用户自动接管授权时：保存失败 → 停止 executor/sentinel 的该阶段 → 核实没有并发写入 → 固定 checkpoint、活动 nonces 和保护路径 → Codex 接管。始终保留原会话，不 `/clear` 或新建替代 Claude。恢复时在 HANDOFF_READY 交接，确认 solo 写入结束，再给同 UUID/同会话新握手；旧回调只可供审计，不能重新启动已经完成的工作。

跨章节会话可通过 cmux 协调资源与文件所有权，不互相接管 executor。使用 task_id、workspace UUID、surface UUID 为身份，数字 surface ref 仅作当前显示。发消息先定位现有 surface；内置 bridge 验证投递。网络已投递但探测不确定时核对接收端，不重复派发。

资源按申请 → 授予 → 使用 → 排空 → 释放。共享 SQLite 队列让调度者退出后仍可恢复，真实 OS 锁保护调用和交接。过期租约不自动授予别人，先核对原进程、pending 和 lock。

Word/Zotero 使用 `word-zotero` 资源：释放原生操作窗口时需原始回执证明 documents=0、windows=0、无模态、Zotero currentDoc/currentWindow=false、无 pending，且锁可实取释放。`-1743` 时文档数必须记 UNKNOWN；不能以 AX 零窗口推导零文档。未知状态可协调诊断，不能据此授予下一次文档写入。

NLM 独立使用账号资源。只有原网络请求确实终态、子进程回收和 transport 可实取释放，才归窗。本地审读回答不占租约；服务端终态未知即隔离，不能用本地进程结束代替。所有租约与恢复说明留在任务目录，不写入公开 skill 示例。
