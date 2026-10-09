# 论文审查的有界交付

复用 multi-agent-collaboration 的 `executor_closeout.py`、
`cmux_executor_closeout_guard.py`（PreToolUse）与 Stop 守卫，不复制发送实现。
统一合同：[原生投递与有界等待](verified-compose-delivery.md)；详细实现只在协作 skill 维护。

派单明确待核问题、必要验证、输出目录和停止条件。报告写好并沿原入口完成
一次 callback 后停止扩展自测；报告、原 task pack、身份及原 attempt 均绑定，
且原回调终态和锁可核时，PreToolUse 冻结既有产物与记录。严格 task-bound
只读诊断及原 controller reconcile 仍可执行，不开放任意工具或新的输入。
未知回调接受普通诚实 WAITING_SUPERVISOR 说明，无须唯一精确 STATUS 模板；
continue:false、suppressOutput:true，保留 task/receipt。无证据的 confirmed/
共识声明仍拦，缺失、在途或漂移证据不享出口；主管和其他任务不被封口。

封口结束的是当前仍 armed 的任务，不是永久停用会话或 API 失败证据。主管核收
并解除 marker 后，沿原通道同步下一动作、依赖和负责人。新的授权状态查询读取
指定最新回执，不沿用旧 recap、不让用户转话、不重发旧 callback。参见
[子任务收尾后续接](collaboration-efficiency-and-closeout.md#子任务收尾后仍由主管推进整篇)。

一次定点核查不等于论文通过。主管读取原报告，沿既有验收/disarm收尾，
再把下一项独立业务交给可用 executor。新增实质问题可派有界后继；
没有新问题就不重跑全套测试，也不把“记录经验”塞回已完成的科研任务。

两 executor 仅用于独立问题，主管继续整合主线。握手只核身份与通道，
原有效握手复用；原消息在队列则观察，不再粘贴。
握手预算由原协作 receipt 固定，业务复核预算另计；ACK 一到即可继续。
confirmed 回执也须与完整任务包 SHA 一致，不能沿用漂移后的旧确认。
持续故障按用户既有 SOLO 授权、原会话及无并发写入边界接管，不等待失效执行者。

主管 PostToolUse 经认证 active markers 有界发现报告；REPORT_DISCOVERED 与
原生接收、正式 receipt、论文接受及 disarm 分列。idle Stop 只写一次状态并放行，
未求派不能阻止结束；显式 persist 最长 300 秒，不无限每 60 秒求派。
CCC 等待有期限，native Goal 单独核证。

自动 PostToolUse 成功结果按客户端官方 JSON schema 输出：只把完整核验结果放进
hookSpecificOutput.additionalContext，hookEventName=PostToolUse；内部 action/results
不得直接作为顶层输出。以活跃客户端的自动执行记录核收，不用手工运行、配置
注册或离线测试替代。完整原生消息、真实 callback 与自动 hook 仍分别留证。

源码/CI、安装、运行中客户端加载、现场收口、报告接受分别记账。
升级前比对现役身份修复，保留旧固定包；安装新规则不宣称旧会话自动生效。

## 绑定报告可嵌套（复用上游校验）

论文任务的 task-pack 可以把 report 绑在 artifact_root 内的子目录（例如
`claude-output/REPORT.md`），receipt 仍直接放在根下。嵌套判定复用上游
`executor_closeout.bound_paths`，不在本仓重写：PreToolUse 与 Stop 必须是
同一个函数，否则会出现「工具没封死、Stop 却以误导理由拦停」的分裂态。
规范化后要求严格位于根内，拒 `../` 逃逸、拒只有经规范化才落回根内的别名、
拒根以下的符号链接分量。写第一个字节前先读 pack 的写入清单，不要因为
「输出放在被审对象旁边更顺手」而落进受保护路径。

## 不许死等，也不许重复

idle Stop 只保存一次持久状态并允许结束；未求派、无后台进程或未答复
均不能阻止 Stop。空闲请求复用共享协作实现，只有显式
`executor_ready.py ask`（旧拼写 request）可在同一 episode 提交一次。
固定原请求、双方 session、marker、nonce 和 attempt；未确认只核原次，
不按时钟重贴、不换措辞生成新 nonce。

显式 `persist` 只读原请求、绑定 transcript 和精确 mailbox，
`input_operations=0`，默认 60 秒、硬上限 300 秒，持有原 session 进程锁。
原期限和已用预算持久化，重启不延长、不另发。旧 CONFIRMED 标签仍核原生
证据；缺绑定/fence或不相容旧格式交原控制器，不补造 pins 或迁移重发。

主管回复沿原 bridge 到达原 surface，或写原请求给出的精确 mailbox。
mailbox 必含原 loop record 的 episode_id、caller_surface_uuid、task_id，
空 task_id 也不能省略；idle binding 的独立 episode_id 不能代替 loop。
任务、主管或绑定 transcript 改变时保留原段并记 UNRESOLVED_IDLE_EPISODE，
不自动换段；损坏请求/停止记录保守终止，不自动重发。原生收到请求、
主管真实答复、WAITING_DEPENDENCY 与论文接受分别核验。

真实答复、新任务、operator stop 或期限耗尽结束观察；到期保留原请求，
不记作已答复、不自动重新 arm、不续起模型催派。CCC 同步合法等待的终态
和期限，native Goal 单独核验。具体 CLI 与状态依[统一合同](verified-compose-delivery.md)
及原完整协作 controller，本仓不另建轮询器或发送器。

## 历史记录：接收端两条排队道

以下仅记录 2026-10-08 单个 Codex build 的观察，不是当前投递或恢复指导。
当前操作一律按[统一合同](verified-compose-delivery.md)：首次受支持的
Tab 提交与恢复阶段的一次共享预算分别核验；历史按键不授予新输入权限。

当时 Codex 的 steer 道（`Messages to be submitted after next tool call`）在下一个
工具边界排空；Tab 道（`Queued follow-up inputs`）只在整轮结束时排空，长 goal
轮里可达数小时，且当时的 `_PENDING_QUEUE_RE` 并不匹配后者。把两者都写成
「下一工具边界即送达」会把「等待」变成无限等待。实测 2026-10-08T07:02–07:03Z：
首个 Enter 后原文仍在 compose，第二个单独 Enter 才进 steer 道；文件声称
07:05:22Z 原生入站，该字段当轮未经主管独核。那几次按键是手动的，只作 lane
行为的历史证据，不是恢复授权，不能据此再次 Enter 或 Tab。另：正文若引用了道名，屏幕文本判 lane
会假阳（实测一个没有待决区的屏幕被判已排队），方向 fail-safe 但不可当送达
证据。以上只在 2026-10-08 实测的那个 Codex build 上成立。

本节只改规则文本。未做、也不宣称：安装到现役 release、运行中客户端加载、
现场发送验证。

## 首次确实零输入时的唯一接续

仅当原任务包、报告及原 attempt SHA 均未变，且 journal 只有 attempt-0001、
phase=NO_INPUT、events=[]、无 receipt/pending，closeout hook 才允许执行一次
任务包所固定的原 controller 同步 callback CLI（rtk proxy + 原 Python -B）；
入口和参数必须完全匹配，不开放其他工具或替代发送器。原 controller 仍重核
活跃身份、完整稳定草稿及最多两次 attempt 的预算。已输入、已排队、未知状态
或第二次 attempt 均不适用，只能沿原证据核收。普通诚实 WAITING_SUPERVISOR
仍可结束回合，不强迫重试。完整原生收到、真实 callback 与自动 hook 分别验收。
