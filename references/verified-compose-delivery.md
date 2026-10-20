# 论文通信的统一合同适配

prompt、任务包、callback、封口与 idle/CCC 等待使用协作 skill 的
[原生投递、原次恢复与有界等待](https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/verified-compose-delivery.md)。
该页是唯一详细权威；论文 skill 不复制发送实现、重试器或 hook。
实际执行使用原 task pack 固定的完整相容版本，不迁移在途任务。

本版对齐0.4.54：新提交默认观察原生确认30秒，`--wait-seconds`仅接受有限的
[0,60]秒，并在输入前验证。`--reconcile-only`默认0秒，即一次只读观察；时间与
`ceil(seconds)+1`次数同时有界，同步I/O仍可能延长实际耗时。exit75保留RPC诊断、
原controller及同参核原次入口；缺旧controller记为 `UNKNOWN_LEGACY_CONTROLLER`，
不能从CURRENT补齐。turn abort既不证明丢失，也不增加重发或补键预算。

- 双方 prompt 就绪即发送，包括忙碌、Goal 和压缩期间；允许 raw cmux，bridge 可选。
  不等空闲或 composer 稳定。新消息以原目标转录在原 EOF fence 后新增含唯一
  marker 的 user 消息确认送达；assistant/tool、历史消息及 queued_command 不算。
- bridge 优先原线程 native steer/start；socket 或原生方法不可用且尚无输入意图时，
  降级一次终端粘贴加 Enter。Claude 默认直发。输入意图后未知结果只核原次，不双送。
- 未确认终端消息仍 pending 且见本次 marker 残留或压缩时，先再核转录，最多补一个
  已记录 Enter；不重贴、不清空、不重置预算。已排队只观察。旧 attempt 保留原合同。
  正文读取、ACK、callback 核收和业务接受单列，不从短通知收到推导。
- 封口冻结报告、task pack 与旧 attempt 记录，保留严格 task-bound 诊断
  和原 controller reconcile。普通诚实等待可以正常结束；现役工作流 hook
  只经 advisory observer，不输出 deny、block 或 continue:false，不调用旧 gate。
  无证据保留未确认，不能冒称共识或业务接受。
- 主管经认证 active markers 有界发现报告；REPORT_DISCOVERED 不等于
  收到、接受或 disarm。报告可先独立核收，不为通信重跑既有研究。
- 默认 idle Stop 只记录一次状态并放行；executor_ready 的显式 persist 默认
  60秒、最多300秒，原期限不因重启延长。另保留用户明确授权的可选
  executor_reask：终端新 marker 最早在上一条原生确认后60秒求派，发送前重核
  原receipt；文件求派独立计时。单次轮询预算最多
  540秒，同步 I/O 可延长实际耗时；退出后的 WAITING_REPLY 不证明进程仍在运行。
  原未确认输入仅核原次，后继使用已配置文件通道；Stop 不启动或强迫循环。
  主管先回原精确 mailbox，再进行新鲜派发。CCC 与 native Goal
  独立核验。主管答复绑定原请求，不能把别的线程回复算作当前等待的答复。
- 0.4.35 runner在回复待原执行者消费、正式预留或观察期限时明确返回原因。
  `runner_returned=true`不表示episode停止、终端空闲或Goal改变；返回仍要求
  fresh preflight。ANSWERED正文提示不代消费，独立CALLBACK_SETTLEMENT提示
  不代核收或RELEASE，旧controller保留原行为；详见[配置与求派](global-communication-configuration.md)。
- 新普通消息超过700 UTF-8字节或带尾换行时，使用同版固定SHA正文＋短通知；
  这是保守 wire 预算，不是通用700字阈值。通知 receipt 的
  confirmation_scope=reference_notice、body_read_confirmed=false；先核SHA、
  读全文，再按原授权处理。正式任务和callback不改用普通消息入口。

诊断及核收入口只使用统一合同和原 controller 实际支持的接口；不存在
独立的 `cmux_native_delivery.py --attempt` CLI。通用实现、完整固定版本
安装、真实 hook 执行、现役客户端加载、原生入站和论文验收分别留证。
旧验证记录继续保留其时间与版本范围，不能由文案推定运行时已通过。

## 自动续跑与派单共用输入框

遵循协作[终端发送冲突与原次恢复](https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/input-collisions.md)。0.4.29握手探针也使用既有pane/target互斥。后台自动续跑须采用同一锁及原次去重；新消息不等 composer 准入，安装共享skill不证明后台实际加载。混合入站保持原记录及未确认回执，沿原执行者核包实读和审稿产物，不重贴、不换nonce、不删除续跑草稿。定向静默须从运行健康记录确认，只涉及原受影响会话。
