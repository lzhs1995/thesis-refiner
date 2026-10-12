# 全局通信配置与显式主动求派

本 skill 2026.10.12.3 复用 multi-agent-collaboration **0.4.27** 的
[配置与请求生命周期](https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/configuration-and-reasks.md)。
本机执行时解析已安装协作 skill 的真实路径并读取同名参考文件；在途任务保留原控制器。

协作工作流 hook 全部使用非阻断 observer。普通工具与 Stop 不因旧任务、未结算
回调、身份不明、等待主管或审查轮次不足被封锁；明确参加协作的会话也适用。
全局安装不代表任务入组，任务绑定只描述责任与证据归属，不授予封锁整个会话的能力。
冻结报告和原 attempt 保留；新诊断、已授权维护握手和独立工作照常继续。

CLAUDE.md 和 skill 文档不能替代 JSON 中的实际注册。cc-switch 切换或导入后，
唯一配置守护器修复自有条目并保留 foreign hook、provider 与非 hook 字段。
实际命令为同版 `cmux_workflow_advisory.py --hook <原检查器名>`；不自动运行旧 gate、
求派循环或报告核收。主管 PostToolUse 另做已认证、有限且去重的文件请求发现，
通过支持的 hookSpecificOutput/additionalContext 提示。遥测失败不跳过该次发现，
发现失败也返回0；不回复、不派包、不结算。真实终端操作的 workspace/panel 保护与显式发送器继续生效。

使用 `cmux-agent self` 的原生 foreground resolver。共享 daemon 的 raw cmux identity
可能包含继承环境，不能拿它代替当前线程的 caller。已获用户授权的继任 supervisor
可用 `successor-rebind-v2` 联系指定原 executor，包括跨 workspace；固定授权正文与
双方 workspace/surface/pane UUID，无须旧主管批准或先结算旧任务。维护通信本身不
转移旧 callback、共享文件写入或科学任务责任。详见[非阻断恢复](nonblocking-collaboration.md)。

shell 可以通过 exec 优化替换自身，令实际工具成为 managed daemon 的直接子进程。
0.4.21 在该结构下读取工具自身的内核 thread selector，并重核进程、原生 foreground、
唯一客户端、TTY 和 UUID。不能因为少一个 shell/rtk 祖先就否认合法 caller，也不能
以 caller 自填环境或共享 daemon 的旧 workspace 代替证据。真实冲突仍只拒绝该次
终端输入；普通工具、诚实报告与已授权 SOLO 工作继续开放。

用户明确授权后，可显式运行 `executor_reask.py run`，每60秒以新 marker 询问，
每5秒查答复，单次轮询预算最多540秒，同步 I/O 可延长实际耗时；原 episode 可在命令退出后继续等待，按既有授权显式
续同一段。绑定主管回复或用户停止可结束等待。新派发自动出口依赖旧 idle binding，
现役 advisory hook 不写该绑定，不能凭新包存在宣称自动结束。Stop hook 不发起或强迫该循环。原终端消息
未确认时仅更新已配置文件通道，不堆叠 prompt。主管主动检查原 mailbox，按原请求的
caller、supervisor、task、episode 和 marker 回复；等待类回复写明解除条件。
询问次数、文件写入、正文已读和实际送达分别计数；不能将已退出命令称为仍在运行。

主管先写原请求精确 mailbox 答复，让 executor 的显式等待返回，再核实时输入边界
和正式派单；TASK 回复本身不是任务包。文件请求提示只在主管实际 PostToolUse 时
运行，不能唤醒完全空闲的客户端。原接收进程退出时保留旧 pending、controller 与
原生证据，不冒造新绑定、清 pending 或重开 episode；独立核出的历史原生收到与
官方回执结算分列。沿原邮箱答复可以结束等待，无须重放旧消息。

新消息仅经共享受保护发送器输入。Codex 接收端直接走原生 control socket：
运行中 turn/steer、空闲时 turn/start，固定原 thread 和 NATIVE_INPUT_INTENT，
不改变设置、不读写 composer、不入 Tab 队列。Claude 终端保留 PASTE_INTENT。
两路均保存原文、接收端绑定与新鲜 EOF fence；只有其后新增、全文逐字相等的
native user 证明收到。RPC 接受、queued follow-up、Claude queued_command、屏幕、
按键或旧 ACK 均不能代替。异常只读核原次，不重试，不转发历史 queued callback。

配置修复、客户端实际自动调用、完整原生接收、真实 callback 与业务核收分别验收。
advisory receipt 记录真实父进程，手动测试不能冒充自动客户端采用。源码或文档更新
不能证明所有活跃客户端已加载；逐会话列出实际通过与待验项，不作整体假成功。

每个工作区恢复后立即接回原论文任务。通信维护不新增科研审轮；按独立未完成交付物
与当前容量使用零、一或两个 executor。通信入口故障不是 Claude API 故障；按既有
授权继续 Codex SOLO 并标记 `solo_self_review`，原 Claude 到安全边界后再恢复协作。
两个 tab 可以并行计算；同 pane 的终端输入串行核验。

0.4.20 的普通文档分类与 Claude footer 修复也属于共享实现：写 PR/HANDOFF 的
字面 heredoc、搜索字符串中出现发送命令不得被当作执行；实际发送仍走受保护入口。
模型与 cwd/时间换行、`+N more` 工具摘要只有完整已测布局才可识别；不清空用户
草稿，也不以历史回顾的错误词推断当前状态。保留原失败证据、更新同版实现并实测，
不能通过删 marker、改 nonce 或重发消息来修解析器。

## 独立文件求派与真实线程（0.4.27）

显式授权的executor_reask start认证当前双方后登记独立文件scheduler，按
原task、purpose、workspace、supervisor和完整controller固定episode。
launchd每60秒运行，容量256、单次10秒、非阻塞锁；不读转录或旧idle binding，
不发送消息、不迁移旧episode、不唤醒空闲模型。保留UNKNOWN与terminal_pending，
只归档真实episode转换。安装job、登记、实际sweep和收到绑定回复分别核验。

PostToolUse保留已认证foreground.thread_id，actual/inherited/parent分列，
child不能把继承root当自己或消费parent收件箱。每次最多8条文件提示，公平轮转，
未答至少60秒再提示，输出成功flush后才更新游标。提示后主管核正文并回精确mailbox；
文件存在不证明已读，TASK答复不证明派包。详细实现及命令只在协作skill维护。

## 0.4.28：显式持续求派

持续模式仅由用户明确授权后，原执行者显式 `start --continuing`，固定总任务、
授权正文、原控制器及双方身份。WAITING 回件必须包含责任人、触发条件、期限和
next_due；ANSWERED 不等于消费。原执行者实读完整正文后用精确SHA执行 consume，
记录检测与消费时间，再按不早于60秒及next_due续询。正式harness任务预留暂停
求派，精确子任务解除后按总授权恢复；TASK邮箱文字不证明派发。Stop、总任务
完成、撤权及授权到期停止；未知原投递不重发，不迁移旧controller。实现统一在
multi-agent-collaboration，文件scheduler不发输入、不唤醒模型、不阻断Stop。
安装、登记、实际sweep、正文消费及两轮现场采用分别核验。
