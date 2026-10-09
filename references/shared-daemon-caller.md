# 共享后台身份与有界回调收尾

Codex managed daemon 可继承首个客户端的终端环境。这不必然代表当前任务所在窗口。协作工具必须用当前线程、工具进程祖先、唯一原生客户端、PID/birth、执行文件、TTY 与 cmux UUID 联合核验，并在发送前复读。身份不明或漂移拒绝输入；不能改写 CMUX 环境、借当前焦点或跨 workspace 发送来绕过。普通客户端保留既有核验。

传输、握手角色及 active-marker 必须消费同一个核实后的 caller。仅修发送入口而让任务注册继续使用后台环境，会导致回调或任务收尾再次错位。assembled runtime 必须覆盖这一接合，以及身份漂移和其他 workspace 的负控。

报告完成后，按[共享接收端绑定契约](receiver-bound-delivery.md)提交一次回调。
发送前固定原生接收端及 transcript inode，整条原文稳定后才按 provider 提交键。
compose、客户端接受、执行、正式回执与报告接受分别记录；Claude `queued_command`
仅证明客户端接受。已排队的回调沿原次有界观察，不反复按键，不要求用户换窗口。
仅原次之后绑定 journal 的完整相等 payload 可零输入核收；固定原 task/report/nonce/
controller，不原地覆盖旧控制器，不用新 nonce 恢复。

监督侧在等待期间继续独立工作。原任务达到安全终态后立即分派下一项有价值的任务；两个原执行者各用 task/nonce/目录，若同 pane 不同 tab 则 UI 输入串行。握手预算至少600秒，收到有效ACK即继续，不机械等待预算耗尽。持续失效者按用户已有授权转 SOLO，不新建替代会话。

效率用已接受工作量、有效工作时间和阻塞原因衡量，不能用消息/轮询/重复独审次数衡量。文档更新、工具安装、原生投递、独审和论文/产品验收分别记账。

## Closeout without consuming executor time

Read the receipt at the absolute path bound by the task pack. A relative `ls`
from a changed working directory cannot establish that a receipt is missing.
When a report is already accepted, a transport delay is a separate closeout
item; do not repeat the audit or ask the user to relay the same callback.
Record the next independent assignment, and dispatch at a verified safe
boundary. A native API retry is not idle capacity: preserve the session and
continue independent supervisor work under existing SOLO authority.

A post-submit detector may return unconfirmed before the message becomes
visible. Preserve that result and inspect the original attempt; a later exact
receiver message is new evidence, not permission to send it again. Do not turn
this recovery into continuous polling or another model-consuming conversation.

For offline harness tests, fixture workspace IDs must not reach live process
ancestry. The suite runner supplies an ordinary-client process fixture; identity
tests override it with their explicit daemon and drift cases. Do not weaken the
production guard or alter CMUX environment values to make tests or routing pass.


## Carry caller identity through every phase

A valid identity gate is insufficient if discovery, provider detection, marker
ownership, naming or screen reads fall back to the daemon's inherited workspace.
Use the resolved native caller throughout, select actual live tree members,
and address naming/reads with workspace and surface UUIDs. A focused executor
or old title does not identify the supervisor; global dock panels are not
workspace members. Recheck identity before mutations.

Preflight failure before challenge dispatch is a supervisor tooling failure,
not proof of an unreachable executor. Preserve its artifacts and establish
zero input from the original journal. Repair the failing layer without minting
a task/nonce to recover the same message. Any input or ambiguous evidence stays
with its original attempt and controller. Disarm only an independently verified
terminal task. Cover the assembled path as well as identity helpers. Once an
executor accepts useful work, continue the main product task instead of adding
coordination-only reviews.


## Compaction and delayed observation are separate from idle capacity

An executor compacting after a submitted challenge is not idle or unreachable.
Record its actual progress and the original handshake handle; do not stack another
challenge or generic continuation message behind it. A pending failure-shaped
receipt is not final while its original process is still observing a late ACK.
Follow that handle to its terminal result, then reuse the exact nonce for supported
read-only recovery. If the handshake ends without proof, record the outcome and
continue independent work under existing authority; do not claim it succeeded.

A null submission timestamp proves only an absent recorded timestamp. The input
journal can show paste and Enter even when a short screen detector saw nothing.
Determine zero input from the attempt, not from that null alone. Keep report
acceptance independent from missing transport receipts and give the executor no
polling assignment merely to make the supervisor's detector catch up.

## 多任务错误归属与发送核收

同一工作区有两个执行者时，Stop hook 提示必须引用本次判定实际失败的
任务标记，不能重新扫描后取第一个任务。错误提示会诱导执行者核错回执；
修复提示归属不等于改变回调门禁或证明通信全链成功。

任务提交后只核原 attempt 绑定的原生日志与输入前边界；屏幕中的后续活动
不能证明原任务已收到。保留原 attempt，不能将未确认解释为未收到、叠加
催促、重复派单或放宽整条相等要求。报告完成后独立核收，正式传输回执另列；监督侧继续主线。
两执行者均有实际工作时不再派通信维护审轮。下一任务在安全终态后接续，
执行者持续失效则沿既有授权冻结其写入并由监督侧接管。

## 原生 Hook 与工具命令分别核验

原生 Hook 可能由共享后台直接生成，中间 shell 已 exec 消失，且没有
CODEX_THREAD_ID。此时先认证后台祖先，再用 Hook 的 session_id 选取唯一
原生客户端；payload 不能指定 workspace 或 surface。保留内核 PID/birth、
执行文件、TTY、UUID 和末次复读，不修改继承环境。工具命令仍核自身线程祖先。

零任务标记时不应让无关进程枚举阻塞普通工作；有适用标记时身份不明仍拒绝。
显式材料目录不能隐藏另一任务的租约。身份诊断不能误称论文共识未通过，
也不能提示无任务范围的解除命令。身份读取共享有界截止，各子命令只用剩余时间。

源码回归、磁盘安装、现役线程加载及真实投递分别记录。测试必须覆盖真实
Hook main 的输入与退出码，隔离测试目录和内核边界；工具命令探针不能代替
原生 Hook 证据。安装后若仍调用旧版本，先核原生刷新能力及其配置、MCP、
技能和活跃任务影响，不通过重启原会话、关闭 Hook 或重发回调来冒充修复。

Codex 的 Hook 信任单独核验：key 包含配置路径、事件及组/处理器索引，hash
对应规范化配置身份，并非脚本文件哈希。发布路径更新或组顺序变化都可能触发
启动审查。逐项绑定已审脚本，在既有安装授权内备份后仅更新对应 trusted_hash
叶子，核语义差异并保留其他配置、技能和历史信任项；动态命令须即时重算身份。
不得关闭 Hook 或用替换用户配置来消除提示。

操作前核所装版本的刷新语义：已核源码的 TUI 单项 Trust 同样要求全局 reload，
可能影响其他活跃线程及 MCP。仅持久化精确信任项、让新测试自然读取，和证明
旧线程已采用新版分别记账，不把启动提示消失称为实际 Hook 全部执行。

## 普通终端的 login 权限拒绝

同工作区原 Claude 已收到任务、却每次工具及 Stop 都被本地身份读取拒绝时，
检查实际加载版本及失败系统调用。macOS 根用户 login 的完整 BSD 信息可能
返回 EPERM；这不能据以累计 Claude API 的连续五分钟失败。优先复用协作技能的
[窄 login 边界及回归](https://github.com/lzhs1995/multi-agent-collaboration/blob/90901f72fc0955a8a3a24fa07da11798715e694e/references/root-login-permission-boundary.md)，
本技能不复制身份读取实现。修复只认可受保护 login 与仍存活的原有子进程的内核绑定，
不能采用环境改写、跳过 Hook 或扩大跨工作区许可。

共享安装由一个维护者执行，其他执行者继续独立离线工作。原会话真实工具恢复后，
沿原任务安全边界继续；不重新派发同一个任务，不重做已完成的 Zotero 刷新、
Word 保存或远端提交。源码测试、安装及实际恢复分列；论文推进用产物验收衡量。
