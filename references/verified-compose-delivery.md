# 论文通信的统一合同适配

prompt、任务包、callback、封口与 idle/CCC 等待使用协作 skill 的
[原生投递、原次恢复与有界等待](https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/verified-compose-delivery.md)。
该页是唯一详细权威；论文 skill 不复制发送实现、重试器或 hook。
实际执行使用原 task pack 固定的完整相容版本，不迁移在途任务。

本版对齐0.4.35：新提交默认观察原生确认30秒，`--wait-seconds`仅接受有限的
[0,60]秒，并在输入前验证。`--reconcile-only`默认0秒，即一次只读观察；时间与
`ceil(seconds)+1`次数同时有界，同步I/O仍可能延长实际耗时。exit75保留RPC诊断、
原controller及同参核原次入口；缺旧controller记为 `UNKNOWN_LEGACY_CONTROLLER`，
不能从CURRENT补齐。turn abort既不证明丢失，也不增加重发或补键预算。

- 只认同一 workspace/surface/process/session/transcript，在原输入意图的
  新鲜 EOF fence 后新增、与完整正文（含全部空白）精确相等
  的 native user。Claude `queued_command` 是 pending，不是 NATIVE_RECEIVED。
- 新 Codex 消息、任务包和 callback 经原生 control socket 回原会话，先固定
  NATIVE_INPUT_INTENT 及 EOF fence；运行中一次 turn/steer，空闲时一次
  turn/start，不改变设置、不操作 composer、不发 Enter/Tab。RPC 接受不是
  原生收到，异常只读观察原次，不重试或退回队列。历史 queued callback 不重放。
- Claude 终端首次完整稳定草稿只提交一次。旧终端恢复共用最多一次补键，
  意图落盘即耗用；显式补键仅属于 submit-text 的受保护恢复分支。
  任务/callback 及新 native attempt 只读核原次。缺原绑定/fence 不追补。
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

遵循协作[终端发送冲突与原次恢复](https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/input-collisions.md)。0.4.29握手探针也使用既有pane/target互斥。后台自动续跑须采用同一锁和完整草稿保护；安装共享skill不证明后台实际加载。混合入站保持原记录及未确认回执，沿原执行者核包实读和审稿产物，不重贴、不换nonce、不删除续跑草稿。定向静默须从运行健康记录确认，只涉及原受影响会话。
