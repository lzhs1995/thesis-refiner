# 论文通信的统一合同适配

prompt、任务包、callback、封口与 idle/CCC 等待使用协作 skill 的
[原生投递、原次恢复与有界等待](https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/verified-compose-delivery.md)。
该页是唯一详细权威；论文 skill 不复制发送实现、重试器或 hook。
实际执行使用原 task pack 固定的完整相容版本，不迁移在途任务。

- 只认同一 workspace/surface/process/session/transcript，在原
  PASTE_INTENT 新鲜 EOF fence 后新增、与完整正文（含全部空白）精确相等
  的 native user。Claude `queued_command` 是 pending，不是 NATIVE_RECEIVED。
- 首次完整稳定草稿只提交一次：忙碌 Codex 明示 `tab to queue message`
  且原文匹配时直接 Tab；其他清晰受支持状态 Enter。所有恢复共用最多
  一次补键，意图落盘即耗用。当前显式补键仅属于 `submit-text` 的受保护
  恢复分支，任务/callback 只读核原次。缺原绑定/fence 不追补。
- 封口冻结报告、task pack 与旧 attempt 记录，保留严格 task-bound 诊断
  和原 controller reconcile。普通诚实等待可结束于 WAITING_SUPERVISOR
  （continue:false、suppressOutput:true）；无证据的确认/共识仍拦截。
- 主管经认证 active markers 有界发现报告；REPORT_DISCOVERED 不等于
  收到、接受或 disarm。报告可先独立核收，不为通信重跑既有研究。
- 默认 idle Stop 只记录一次状态并放行；executor_ready 的显式 persist 默认
  60秒、最多300秒，原期限不因重启延长。另保留用户明确授权的可选
  executor_reask：每60秒用新 marker 求派，直到主管答复、新派发或 operator
  stop；已配置文件通道结果明确记录，绝不重放旧消息。配套 Stop hook 仅用于
  该已授权段，未完成的生命周期后继方案不视为已安装。CCC 与 native Goal
  独立核验。主管答复绑定原请求，不能把别的线程回复算作当前等待的答复。
- 新普通消息超过700 UTF-8字节或带尾换行时，使用同版固定SHA正文＋短通知；
  这是保守 wire 预算，不是通用700字阈值。通知 receipt 的
  confirmation_scope=reference_notice、body_read_confirmed=false；先核SHA、
  读全文，再按原授权处理。正式任务和callback不改用普通消息入口。

诊断及核收入口只使用统一合同和原 controller 实际支持的接口；不存在
独立的 `cmux_native_delivery.py --attempt` CLI。通用实现、完整固定版本
安装、真实 hook 执行、现役客户端加载、原生入站和论文验收分别留证。
旧验证记录继续保留其时间与版本范围，不能由文案推定运行时已通过。
