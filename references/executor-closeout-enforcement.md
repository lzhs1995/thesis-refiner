# 论文审查的有界交付

复用 multi-agent-collaboration 的 `executor_closeout.py`、
`cmux_executor_closeout_guard.py`（PreToolUse）与 Stop 守卫，不复制发送实现。
上游说明：https://github.com/lzhs1995/multi-agent-collaboration/blob/fix/helper-delivery-state-parity-20261002/references/executor-closeout-enforcement.md

派单明确待核问题、必要验证、输出目录和停止条件。报告写好并沿原入口完成
一次 callback 后停止扩展自测；报告、原 task pack、身份及原 attempt 均绑定，
且原回调锁已可取得时，PreToolUse 拒绝后续工具。未知回调可用上游精确
REPORT_READY 模板结束；由主管核原次，不伪称送达、不改原报告、不清 marker。
未终态或缺失/漂移证据不享此出口。主管和其他任务不被当前任务封口。

一次定点核查不等于论文通过。主管读取原报告，沿既有验收/disarm收尾，
再把下一项独立业务交给可用 executor。新增实质问题可派有界后继；
没有新问题就不重跑全套测试，也不把“记录经验”塞回已完成的科研任务。

两 executor 仅用于独立问题，主管继续整合主线。握手只核身份与通道，
原有效握手复用；原消息在队列则观察，不再粘贴。
握手预算由原协作 receipt 固定，业务复核预算另计；ACK 一到即可继续。
confirmed 回执也须与完整任务包 SHA 一致，不能沿用漂移后的旧确认。
持续故障按用户既有 SOLO 授权、原会话及无并发写入边界接管，不等待失效执行者。

源码/CI、安装、运行中客户端加载、现场收口、报告接受分别记账。
升级前比对现役身份修复，保留旧固定包；安装新规则不宣称旧会话自动生效。
