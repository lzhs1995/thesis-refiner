# 高效握手、多执行者与双向投递

维护版本 efficient-bidirectional.2026.10.09.1。投递的有效规则为[Enter 与原生投递回执](verified-compose-delivery.md)；旧屏幕确认、Tab 队列和全局 marker 检索只作历史记录，不再作为操作说明。

## 先备任务，再握手

先备好任务目标、精确输入、允许写入目录、报告路径、完成条件和验证方法，再对当前同workspace的原会话做真实身份核验、握手与finalize。健康ACK不重复获取；迟到ACK先核原task/nonce。分别记录准备、握手、投递、执行、回调、核收耗时。握手上限不是强制等待，不因设置600秒就等满600秒；观察预算过短不能归因执行者，不强制使用实测时间的三倍。

## 以任务收益决定一个或两个执行者

复用用户指定且携带上下文的会话。第二执行者仅接独立工作，例如数据文件核查与协作工具审查；各有task_id、nonce、输出根，互不改对方结果。只有supervisor整合最终材料和维护公共脚本。两个会话占同一pane的不同tab时如实记拓扑，不称两个额外side split。共享Stata/Office/网盘仍服从原资源队列，executor数量不等于资源并发数。

只有需要计划共识的工作才走既有共识流程；普通已授权的一次审阅不因此增加科研审轮。执行者仅在任务包授权目录写入；supervisor的安装权限另列且须来自用户，不能反向改写已经冻结的任务包。

明确retryable服务故障在原尝试结束后同会话有限重试、每次至少60秒；认证、欠费、额度失败不盲试。投递不确定也不能重贴。重试次数不证明失效：须按[失败窗口规则](collaboration-and-recovery.md)从首次真实API失败起连续至少300秒、阈值处有新鲜失败且当前尝试已终态，期间任一真实成功即重置；排队、静屏、未知投递和握手超时都不计入。满足后沿用户既有授权固定原终态、冻结executor写入并转solo_self_review，继续本机能做的工作。保留原会话，不clear、不新建替代。恢复协作在安全边界使用原UUID。

## 双向发送铁律：原生全文回执才确认收到

supervisor→executor的prompt和executor→supervisor的callback都通过受保护bridge。每次粘贴/按键前重核caller、同workspace、指定目标UUID；首次输入前SHELL/UNKNOWN零输入；已有paste_intent后若识别失败，记为投递未确认，停止按键并核收原次，不能改判为从未发送。按键返回0、文字出现在旧转录块、marker消失或无关新工具输出均不能证明本次消息已消费。

输入前绑定接收方 UUID、进程、原生 session 和 transcript 追加边界，先持久化原 attempt 再粘贴一次。只读观察到自身完整 payload 与稳定 composer 后才按 Enter；等待预算耗尽不按键。确认必须来自原 transcript 在原边界后新增、全文精确相等的 user 记录。屏幕活动、ACK、空 composer、全局同 marker 或同目标其他调用均不能代替。动态参数未解析时保留未验证；正文示例和工具输出不能生成发送目标。

Claude 原生 `queued_command` 可证明接收并排队，执行、报告完成和主管验收仍另列。完整 payload 卡在 composer 时沿原 controller 的 `--recover-stranded` 恢复；自动和显式恢复共用一次补 Enter 预算，`EXTRA_ENTER_INTENT` 落盘即消耗，按键失败也不重置。恢复先核迟到原生回执，再核身份、原完整草稿与稳定状态。不另走 Tab，不重贴、不换 nonce；未知、被改写、压缩、重连、排队和外来草稿均不按键。预算用完仍可只读核收。

## 回调日志与旧任务收尾

先保存固定报告，再调用`submit-completion-callback --task-pack /absolute/task-pack.json`。实际尝试目录与任务包的`completion_receipt`同目录，名称为回执stem加`-attempts/`。新版journal绑定任务包SHA、报告SHA、nonce、原executor UUID与目标，并先写PASTE_INTENT后输入；同inode锁避免两个进程重复回调。记录为零输入的失败最多另试一次；任何可能已粘贴的尝试禁止重贴。

`--reconcile-only`只读取已有真实尝试和原生接收记录，终端输入为0；可以持久化本次观察，且仅在全文精确相等的原生证据满足原绑定时保存回执。不另发恢复消息。若旧`<receipt>.pending.json`存在，即使内容损坏也拒绝新发送和自动迁移，交supervisor按原证据结案。缺journal不能补造历史尝试，报告SHA出现在supervisor文件只能证明该报告被核查，不能自动生成transport receipt。原生文件被替换、截断或身份不可核验时保留未确认，不猜成功。

旧任务若真实callback已经进入supervisor会话且报告已独立核收，可由supervisor保存原marker及核收依据后，仅`disarm --task-id`该已终态任务。明确记录正式bridge receipt缺失；不得伪造receipt、反复回调、全局禁用Stop hook或让已完成executor无限修复回调。Stop hook提供完成门禁，supervisor负责真实旧任务的有据结案。

## 安装、复测与版本

协作仓安装器为两端注册 `cmux_native_delivery_guard.py` PostToolUse，doctor和harness检查漏注册。hook只核当前投递调用对应的原attempt；未确认exit 2并给原次恢复命令，不发键、不造回执、不扫描无关旧账，没有disable/advisory放行。发送器补Enter前仍须比较完整可见草稿；显示等价仅用于草稿保护，不能替代原生全文精确匹配。折叠粘贴摘要不能证明完整草稿，原回调账本及迟到ACK继续由原控制器处理。

本包旧 `cmux_submit_confirmation_guard` 和 `cmux_send_proof_stop_guard` 注册退役，避免屏幕判据与Stop循环并存；foreign同名hook保留。原生读取器只处理原controller支持的固定attempt格式，遇到旧账本明确交回原控制器，不默认为“没有尝试”或迁移重发。通用实现只在协作仓维护，不在论文仓复制另一套发送器。

Stop/SubagentStop重入只接受严格布尔`stop_hook_active is True`；数字1或字符串true不能绕过首次检查。重入成功退出仅结束递归，不产生completion receipt、不disarm、不表示论文完成。下一正常turn仍须校验原任务。不提高循环上限，也不让已接收的callback无限重发。

维护源与实际安装两边都保留本文及对应入口。协作仓 `manage_install.py` 将可证明属于本包的旧wrapper整目录备份后链接到固定release；配置和资源逐次检查并发漂移，foreign目录保留。论文仓安装器沿 `mutation_locks` 与 `replace_bytes` 备份覆盖维护文件，保留章节资源；不复制协作hook。新任务启动器及hook须指向同一完整固定版本，不能先装新读取器再配旧bridge；历史任务沿原固定控制器。

后置检查须读取发送器实际写入的原journal格式。消息使用message-dispatch-v1，任务使用task-dispatch-v1，正式回调使用completion_receipt旁的*-attempts。复核原任务/报告SHA、双方身份、原生session/追加边界及完整正文；只读恢复的input_operations为整数0。确认标志不能代替证据。格式不兼容时修原读取器，不重发原消息、不制造回执。源码测试、固定release安装、真实hook入口、客户端加载、消息收到和业务验收分别留证。

安装完成、测试通过、新进程实际导入和旧客户端热加载是四件事；不为更新skill重启正在工作的应用。已冻结任务包保留旧pins，后继显式记录维护版本，不冒称旧输入未变。通用文档不含研究数据；本机维护patch另归档，无Git元数据不得声称已提交或发布。


### Handshake detector recovery (2026-10-04)

A `DELIVERY_UNVERIFIED_BY_DETECTOR` or `DELIVERY_QUEUED_AT_RECEIVER` result must not end the handshake before the configured ACK wait runs. Retain the dispatch error and original task/provider/nonce; use the existing strict assistant-response parser for a bounded read-only wait. Never resend text or Enter. A matching ACK may complete the handshake while the original transport uncertainty remains recorded; do not fabricate a dispatch-submitted timestamp. Compose-busy and never-submitted states still fail immediately. No matching ACK means failure, not permission to resend or proof of executor silence. This source change does not retroactively rewrite frozen receipts or prove live-client reload.

### 当前Claude页脚识别（2026-10-05）
真实边框、模型行和完整已知页脚同时满足时，允许识别计时行与运行中Bash状态行；未知尾行、shell提示或缺边框仍拒绝。识别为agent仅证明输入界面类型，不等于身份、空compose、任务可接收或消息已消费。不能因UNKNOWN重新握手或重贴未确认回调。


## 完整消息的发送后确认（2026-10-05）

旧helper PR3 e5fb9ec的429项离线测试只记录当时的显示判据，不能证明本版本送达。当前一律核原attempt绑定的新增原生全文记录；只有nonce、跨记录拼接、附带其他内容或正文空白被改写均不构成成功。只读核收不得发送文字或按键，终端空白归一化不能替代原生精确匹配。


## 任务提示持久化（2026-10-05）

supervisor的正式任务提示通过submit-task-pack记录原任务、完整文本SHA、任务包SHA及双方workspace/pane身份；粘贴意图先落盘，再执行输入。同任务提示变化不产生新发送槽，未知投递禁止重新粘贴，只有已记录零输入允许一次明确重试。原命令增加--reconcile-only仅观察并核收，不发送按键。delivery10旧记录仍交原控制器，禁止新控制器接管。对应helper PR3 05b638d，440项离线测试通过；尚未替换已安装运行时。

## 配套版本与迟到握手核收

实测旧bridge缺少新读取器要求的`_delivery_confirmed`接口，九项定向用例中混装出现两失败、三异常；完整候选九项通过。不能用宽泛旧套件“失败名称没有增加”代替接口兼容验证。安装后核实际导入根、启动器及hook正反例；这些结果仍不等于现役客户端重载、回调原生送达或论文验收。

握手观察预算应满足阶段最低值。本方预算过短后收到原nonce的真实ACK，应保留旧超时与原投递错误，重核同workspace和原executor身份，用canonical解析器及回执写入器核收原次；不重发握手、不伪造提交时间。正式任务包定稿后，提示必须包含TASK_PACK、REQUIRED_SKILL、CALLBACK_TARGET、完成模板及READ_AND_OBEY_REQUIRED_SKILL_FIRST。输入前拒绝不算派发成功；实际Enter后的确认与最终报告核收继续分开记录。
