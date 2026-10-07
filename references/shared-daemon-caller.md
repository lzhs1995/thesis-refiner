# 共享后台身份与有界回调收尾

Codex managed daemon 可继承首个客户端的终端环境。这不必然代表当前任务所在窗口。协作工具必须用当前线程、工具进程祖先、唯一原生客户端、PID/birth、执行文件、TTY 与 cmux UUID 联合核验，并在发送前复读。身份不明或漂移拒绝输入；不能改写 CMUX 环境、借当前焦点或跨 workspace 发送来绕过。普通客户端保留既有核验。

传输、握手角色及 active-marker 必须消费同一个核实后的 caller。仅修发送入口而让任务注册继续使用后台环境，会导致回调或任务收尾再次错位。assembled runtime 必须覆盖这一接合，以及身份漂移和其他 workspace 的负控。

报告完成后，回调只提交一次。compose、排队、原生消费、正式回执与报告接受分别记录。已排队的回调沿原次观察，不反复 Enter，不开秒级 watcher，不要求用户为通信手动换窗口。收到原生消息但缺回执时，固定原 task/report/nonce/controller，在原 journal 下零输入核收。旧控制器不原地覆盖。

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
not proof of an unreachable executor. Preserve its artifacts, disarm only that
failed task and use a new task/nonce after repair. Cover the assembled path as
well as identity helpers. Once an executor accepts useful work, continue the
main product task instead of adding coordination-only reviews.


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

任务提交后若被其他用户提示隔开，屏幕中的后续活动可能无法归属原任务。
保留原 attempt，不能将未确认解释为未收到、叠加催促、重复派单，或放宽
跨消息归属检查。报告完成后独立核收，正式传输回执另列；监督侧继续主线。
两执行者均有实际工作时不再派通信维护审轮。下一任务在安全终态后接续，
执行者持续失效则沿既有授权冻结其写入并由监督侧接管。
