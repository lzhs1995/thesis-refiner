# 高效握手、多执行者与双向投递

本页在 efficient-bidirectional.2026.10.09.2 基础上同步
[论文通信统一合同](verified-compose-delivery.md)，保留任务准备、握手、
分工、同版安装和原会话恢复要求。旧屏幕确认、queue 即收到、Ctrl+Enter
路由及独立按键预算不再作为操作规则。文档、离线测试、安装、客户端加载
和实机原生 receipt 分别验证；历史读取证据不替代当前运行状态。

## 先备任务，再握手

先备好任务目标、精确输入、允许写入目录、报告路径、完成条件和验证方法，
再对当前同 workspace 的原会话做真实身份核验、握手与 finalize。首条挑战
提供 pending receipt 的绝对路径和固定完整 skill；握手只核身份及通道，
不夹带科学审查。正式提示含 TASK_PACK、REQUIRED_SKILL、CALLBACK_TARGET、
完成模板及 READ_AND_OBEY_REQUIRED_SKILL_FIRST。

健康的同任务 ACK 复用，迟到 ACK 按原 task/provider/nonce 有界只读核收，
保留原失败和投递不确定性，不制造提交时间。ACK 可满足握手条件，但不替代
原生投递凭据。使用相位要求的观察预算；600 秒预算不是强制等待时长，
有效 ACK 到达立即继续。观察窗口不足不能归因执行者失效。

## 按独立待办选择执行者

复用用户指定且携带上下文的会话。第二执行者仅接独立工作，例如数据链条
核查与工具审查；各有 task_id、nonce、产物根和写入范围，共享代码只有一个
整合写入者。同 pane 的不同 tab 如实记拓扑，UI 输入串行并重核 UUID。
共享 Stata、Office 和网盘继续服从原资源队列。无独立待办可待命。

只有需要计划共识的任务才走既有共识流程；普通已授权审阅不增加科研审轮。
执行者只写任务包允许目录，主管安装权限单列且来自已有授权，不反向改写
已冻结的任务包。

## 输入和核收都由共享 transport 执行

发送 prompt、状态或 callback 前，原 attempt 固定完整 payload/hash、
task/nonce、适用的任务包/报告 SHA、workspace/surface/pane UUID，以及
接收端原生 PID/birth/TTY/session UUID、认证后的 transcript path/device/inode。
原 PASTE_INTENT 在真实输入前保存新鲜 EOF fence；不按 newest mtime、
焦点、标题或 marker 搜索选择会话。原记录不可改，索引不能新建发送槽。

共享 bridge 使用 `terminal.paste` 与 `submit_key=none`，只粘贴一次。
完整原草稿逐字符未改且稳定后提交一次：忙碌 Codex 明示
`tab to queue message` 且受支持结构和全文匹配时直接 Tab；
其他清晰受支持状态 Enter。不得改走 `cmux send` 或 Ctrl+Enter。
保留空格、Tab、空行和字面转义；折叠摘要、前缀或归一化不能证明完整草稿。
SHELL/UNKNOWN、压缩、重连、外来草稿或未知结构在输入前拒绝；
已有输入意图后，不能因识别失败改称零输入。

仅同一 workspace/surface/process/session/transcript，在原 PASTE_INTENT
新鲜 EOF fence 后新增、全文精确相等的 native user 才为 NATIVE_RECEIVED。
Claude `queued_command` 仍 pending；ACK、按键、空 composer、屏幕活动
和队列横幅不证明收到。原生接收、执行、正式 receipt 和报告接受分别留证。

## 只恢复原 attempt

先沿原 controller 有界零输入核原生证据；已收到只结算，已排队不补键。
自动和显式恢复共用最多一次补键；现场支持的 Enter 或 Tab 共用预算，
意图落盘即耗用，崩溃、按键失败和重启不重置。原身份、binding/fence、
完整未改且稳定的原草稿及全部历史门禁必须可核。UNKNOWN、压缩、排队、
重连、结构变化或用户改稿均禁止补键；缺原绑定/fence 不追补，不重贴、
不换 nonce、不删 journal，不因 pending 或旧格式另建一次发送。

当前 `--recover-stranded` 仅属于 `submit-text` 的原 NATIVE_PENDING、
PASTE_INTENT/ENTER_SENT、未用共享预算及全部门禁；task/callback 仅支持
原 controller 零输入 reconcile。不存在独立
`cmux_native_delivery.py --attempt` CLI。封口后的只读诊断入口为
`scripts/cmux_callback_diagnose.py --task-pack <原任务包绝对路径>`，
诊断不发键、不造 receipt、不清 marker；核收仍由原 controller 沿原锁完成。

报告完成后沿原入口提交一次 callback，冻结报告、task pack 和既有记录。
主管独立读取报告与产物，再按原证据分别核收通信、裁决业务及精确 disarm。
没有正式 receipt 就保留未确认，不用报告哈希、屏幕 DONE 或 ACK 补造，
不让执行者无限补测试、回调或索取“通知的 ACK”。

## 同版运行与有界收尾

actual hooks、wrappers、bridge 与 journal readers 必须来自同一 immutable release。
不能把新版 reader 单文件覆盖到旧 bridge；旧任务保持原固定控制器和证据。
安装须备份并保留其他设置，分别核实际导入路径、真实 hook 调用和实机 receipt。
配置写入不证明现役客户端重载，不为维护技能重启原会话。
安装迁移与唯一写入者见[协作提效与收尾](collaboration-efficiency-and-closeout.md)；
来源、版本和维护文件哈希先按[安装与回滚](runtime-validation.md#安装与回滚)比对。

共享 PostToolUse `cmux_native_delivery_guard.py` 只核当前投递的原 attempt，
不扫描无关旧账、不发键、不造 receipt，也无 disable/advisory 绕过。
旧格式交原控制器，不补 pins、不迁移重发，也不复制协作 hook。
主管 PostToolUse `cmux_supervisor_report_guard.py` 经认证 active markers
有界发现冻结报告并记 REPORT_DISCOVERED；发现不等于接收、接受或 disarm。

Stop/SubagentStop 的严格布尔 `stop_hook_active is True` 只结束递归，
不生成 completion receipt、不解除任务或授予论文通过。封口保留严格
task-bound 诊断和原 controller reconcile；普通诚实说明可返回
WAITING_SUPERVISOR、continue:false、suppressOutput:true，无唯一模板。
缺失、在途或漂移证据不能伪装合法等待，无证据的 confirmed/共识仍拦截。

idle Stop 只记录一次状态并允许结束，未求派不阻止 Stop。显式
`executor_ready.py ask`（旧拼写 request）同一 episode 至多一次；
`persist` 仅读原请求、绑定 transcript 和精确 mailbox，默认 60 秒、
上限 300 秒，重启不延长原期限或重置已用预算。主管答复必须到原 surface
或原请求指定 mailbox；mailbox 包含原 loop record 的 episode_id、
caller_surface_uuid、task_id，空 task_id 也保留。idle binding 的
独立 episode_id 不能代替该 loop。任务/主管/transcript 改变保留原段并记
UNRESOLVED_IDLE_EPISODE；损坏请求/停止记录保守终止，不重发。
细节见[有界空闲核查](executor-closeout-enforcement.md#不许死等也不许重复)。
CCC 等待有期限；native Goal 独立核验，不开无限 Stop/idle 催派循环。

可重试 API 故障在原次终态后同会话有界重试，每次至少间隔 60 秒；认证、欠费
或额度失败不盲试。按[连续失败规则](collaboration-and-recovery.md)裁定持续失效，
静屏、排队、未知投递和超时不计入 API 失败时钟。满足条件后沿既有 SOLO 授权，
固定原终态并确认无并发写入，由主管继续主线；自审标 `solo_self_review`。
保留原会话，安全边界才恢复协作，不 clear、不新建替代、不重做已接受研究。
