# 论文审查的有界交付

复用 multi-agent-collaboration 的 `executor_closeout.py`、
`cmux_executor_closeout_guard.py`（PreToolUse）与 Stop 守卫，不复制发送实现。
上游说明：https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/executor-closeout-enforcement.md

派单明确待核问题、必要验证、输出目录和停止条件。报告写好并沿原入口完成
一次 callback 后停止扩展自测；报告、原 task pack、身份及原 attempt 均绑定，
且原回调锁已可取得时，PreToolUse 拒绝后续工具。未知回调可用上游精确
REPORT_READY 模板结束；由主管核原次，不伪称送达、不改原报告、不清 marker。
未终态或缺失/漂移证据不享此出口。主管和其他任务不被当前任务封口。

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

## executor 空闲领任务

起因（2026-10-08）：回调 DISPATCH_UNCONFIRMED 后封口守卫封死工具，codex
主管 compose 忙碌，executor 无通道也无义务方催派发，只能死等。现由上游
multi-agent-collaboration 的 `cmux_idle_pull.py` 与两个 hook 强制：

1. executor：报告与原回调 attempt 存在后，运行封口守卫提示的唯一精确命令
   `rtk proxy <release>/scripts/cmux_idle_pull.py --task-pack <原任务包绝对路径>`，
   原子写入 `~/.local/state/multi-agent-collaboration/idle-requests-v1/<ws>/<executor>.json`
   和产物根 `executor-idle-request.json`；不发终端输入，不重发回调。
2. executor Stop：精确 handoff_line 只有在本任务、本报告哈希的新鲜请求存在时放行。
3. 主管 Stop：发给本主管的请求在出现更新的任务派发 attempt 或
   `--ack EXECUTOR --workspace WS --supervisor SUP --reason <非空理由>` 前一直拦截。
4. 请求不是送达确认，不替代 completion receipt；主管仍沿原次核收。

论文任务里主管收到请求后：有下一项独立业务就派新任务包；暂无可派（如
WAITING_DEPENDENCY）则带理由 ack，并在 evidence 目录写明依赖与负责人。
上游说明：https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/executor-idle-pull.md

源码/CI、安装、运行中客户端加载、现场收口、报告接受分别记账。
升级前比对现役身份修复，保留旧固定包；安装新规则不宣称旧会话自动生效。
