# 高效握手、多执行者与双向投递

维护版本 efficient-bidirectional.2026.10.05.1。本文是本次维护后的有效入口；同日其他握手/Enter文档保留为历史，不再作为并列操作说明。

## 先备任务，再握手

先备好任务目标、精确输入、允许写入目录、报告路径、完成条件和验证方法，再对当前同workspace的原会话做真实身份核验、握手与finalize。健康ACK不重复获取；迟到ACK先核原task/nonce。分别记录准备、握手、投递、执行、回调、核收耗时。握手上限不是强制等待，不因设置600秒就等满600秒；观察预算过短不能归因执行者，不强制使用实测时间的三倍。

## 以任务收益决定一个或两个执行者

复用用户指定且携带上下文的会话。第二执行者仅接独立工作，例如数据文件核查与协作工具审查；各有task_id、nonce、输出根，互不改对方结果。只有supervisor整合最终材料和维护公共脚本。两个会话占同一pane的不同tab时如实记拓扑，不称两个额外side split。共享Stata/Office/网盘仍服从原资源队列，executor数量不等于资源并发数。

只有需要计划共识的工作才走既有共识流程；普通已授权的一次审阅不因此增加科研审轮。执行者仅在任务包授权目录写入；supervisor的安装权限另列且须来自用户，不能反向改写已经冻结的任务包。

明确retryable服务故障在原尝试结束后同会话有限重试、每次至少60秒；认证、欠费、额度失败不盲试。投递不确定也不能重贴。重试次数不证明失效：须按[失败窗口规则](collaboration-and-recovery.md)从首次真实API失败起连续至少300秒、阈值处有新鲜失败且当前尝试已终态，期间任一真实成功即重置；排队、静屏、未知投递和握手超时都不计入。满足后沿用户既有授权固定原终态、冻结executor写入并转solo_self_review，继续本机能做的工作。保留原会话，不clear、不新建替代。恢复协作在安全边界使用原UUID。

## 双向发送铁律：Enter后必须读回

supervisor→executor的prompt和executor→supervisor的callback都通过受保护bridge。每次粘贴/按键前重核caller、同workspace、指定目标UUID；首次输入前SHELL/UNKNOWN零输入；已有paste_intent后若识别失败，记为投递未确认，停止按键并核收原次，不能改判为从未发送。按键返回0、文字出现在旧转录块、marker消失或无关新工具输出均不能证明本次消息已消费。

当前bridge粘贴一次并按Enter，随后必须读同一接收端；发送命令成功本身不作送达证据。确认需要：本次完整消息关联的新活动、原身份和尝试绑定一致、消息不在compose或pending queue。marker独自出现不能确认，多个并行调用不能互借同一目标的成功证据。动态参数未解析时保留未验证；正文中的示例和工具输出不能生成发送目标。排队、已消费、报告已审阅分别记录。若完整待提交文字仍逐字匹配自己的payload，且没有用户新增、排队、压缩或重连，bridge至多补一次Enter，不重新粘贴。

实测Codex忙时可显示`tab to queue message`：仅精确提示、Codex字形、完整自身payload均匹配且没有压缩/重连/队列时，允许一次Tab，之后再读回；进入队列仍不算消费。该路径目前有离线测试，不能称全部真实UI版本均已验证。未知多行输入按用户草稿保护，不通过force清除。

## 回调日志与旧任务收尾

先保存固定报告，再调用`submit-completion-callback --task-pack /absolute/task-pack.json`。实际尝试目录与任务包的`completion_receipt`同目录，名称为回执stem加`-attempts/`。新版journal绑定任务包SHA、报告SHA、nonce、原executor UUID与目标，并先写PASTE_INTENT后输入；同inode锁避免两个进程重复回调。记录为零输入的失败最多另试一次；任何可能已粘贴的尝试禁止重贴。

`--reconcile-only`只读取已有真实尝试和接收端，终端输入为0；可以持久化本次观察，且仅在真实消费证据满足原绑定时保存回执。不另发恢复消息。若旧`<receipt>.pending.json`存在，即使内容损坏也拒绝新发送和自动迁移，交supervisor按原证据结案。缺journal不能补造历史尝试，报告SHA出现在supervisor文件只能证明该报告被核查，不能自动生成transport receipt。滚屏丢失证据时如实保留未确认。

旧任务若真实callback已经进入supervisor会话且报告已独立核收，可由supervisor保存原marker及核收依据后，仅`disarm --task-id`该已终态任务。明确记录正式bridge receipt缺失；不得伪造receipt、反复回调、全局禁用Stop hook或让已完成executor无限修复回调。Stop hook提供完成门禁，supervisor负责真实旧任务的有据结案。

## 安装、复测与版本

协作仓安装器现为两端注册PostToolUse确认hook，doctor和harness检查漏注册；临时目录测试覆盖安装、缺失和卸载。配置注册仍不等于当前客户端实际加载。发送器追加Enter或使用明确Tab队列键前，须比较完整可见草稿；禁止删除全部空白后比较。只接受已识别的折行、空页脚间隔及Claude单光标格显示等价，正文空格、缩进、空白内容行和未知尾行必须保留。折叠粘贴摘要不能证明完整草稿。原回调账本及迟到ACK继续由原控制器处理。

协作仓的 `cmux_submit_confirmation_guard.py` 是只读 PostToolUse 检查入口，不发键、不写回执；脚本纳入版本管理不表示安装器已注册或现役客户端已加载。当前compose/queue状态优先于历史确认。`delivery_receipts.py` 可依据当前接收者原生会话内的精确user消息、任务定稿时间、原身份及文件pins核收，不把tool/assistant引用算作入站；收到报告仍须独立验收内容。该模块支持其固定的durable attempt格式，遇到旧`*-attempts`或`.pending.json`明确交回原控制器，不默认为“没有尝试”或迁移重发。通用实现只在协作仓维护，不在论文仓复制另一套发送器。

Stop/SubagentStop重入只接受严格布尔`stop_hook_active is True`；数字1或字符串true不能绕过首次检查。重入成功退出仅结束递归，不产生completion receipt、不disarm、不表示论文完成。下一正常turn仍须校验原任务。不提高循环上限，也不让已接收的callback无限重发。

维护源与实际安装两边都保留本文及对应入口。实体目录安装若被manage_install.py判为foreign，保留目录；按已授权窄维护调用现有mutation_locks及replace_bytes，先核原字节，备份后安装，保留mode与before/after SHA。不得将实体目录强换symlink或整树覆盖。新任务启动器及hook必须指向同一完整固定版本，不能先装新journal读取器再配旧bridge；历史任务仍沿原固定控制器。

后置检查必须读取发送器实际写入的原journal格式。任务投递使用task-dispatch-v1，正式回调使用completion_receipt旁的*-attempts；只识别旧deliveries-v1会把已确认回调误报为未确认。新读取器须复核报告与任务包SHA、原executor和接收方身份、原次完整正文及后续活动；只读恢复的观察必须明确input_operations为整数0。确认标志不能代替证据。发现格式不兼容时修读取器，不重发原消息、不制造回执。源码测试、候选安装、全局安装与实际客户端加载分别验收。

安装完成、测试通过、新进程实际导入和旧客户端热加载是四件事；不为更新skill重启正在工作的应用。已冻结任务包保留旧pins，后继显式记录维护版本，不冒称旧输入未变。通用文档不含研究数据；本机维护patch另归档，无Git元数据不得声称已提交或发布。


### Handshake detector recovery (2026-10-04)

A `DELIVERY_UNVERIFIED_BY_DETECTOR` or `DELIVERY_QUEUED_AT_RECEIVER` result must not end the handshake before the configured ACK wait runs. Retain the dispatch error and original task/provider/nonce; use the existing strict assistant-response parser for a bounded read-only wait. Never resend text or Enter. A matching ACK may complete the handshake while the original transport uncertainty remains recorded; do not fabricate a dispatch-submitted timestamp. Compose-busy and never-submitted states still fail immediately. No matching ACK means failure, not permission to resend or proof of executor silence. This source change does not retroactively rewrite frozen receipts or prove live-client reload.

### 当前Claude页脚识别（2026-10-05）
真实边框、模型行和完整已知页脚同时满足时，允许识别计时行与运行中Bash状态行；未知尾行、shell提示或缺边框仍拒绝。识别为agent仅证明输入界面类型，不等于身份、空compose、任务可接收或消息已消费。不能因UNKNOWN重新握手或重贴未确认回调。


## 完整消息的发送后确认（2026-10-05）

双向投递均须在接收端同一条输入记录中看到完整内容及其后的活动。只有nonce、跨记录拼接、附带其他内容或先于消息的活动均不构成成功；只读回调核收不得发送文字或按键。终端转录的空白归一化仅证明显示等价，不是原生字节一致。对应helper PR3 e5fb9ec，429项离线测试通过；尚不代表已安装或实机投递通过。


## 任务提示持久化（2026-10-05）

supervisor的正式任务提示通过submit-task-pack记录原任务、完整文本SHA、任务包SHA及双方workspace/pane身份；粘贴意图先落盘，再执行输入。同任务提示变化不产生新发送槽，未知投递禁止重新粘贴，只有已记录零输入允许一次明确重试。原命令增加--reconcile-only仅观察并核收，不发送按键。delivery10旧记录仍交原控制器，禁止新控制器接管。对应helper PR3 05b638d，440项离线测试通过；尚未替换已安装运行时。

## 配套版本与迟到握手核收

实测旧bridge缺少新读取器要求的`_delivery_confirmed`接口，九项定向用例中混装出现两失败、三异常；完整候选九项通过。不能用宽泛旧套件“失败名称没有增加”代替接口兼容验证。安装后核实际导入根、启动器及hook正反例；这些结果仍不等于现役客户端重载、回调原生送达或论文验收。

握手观察预算应满足阶段最低值。本方预算过短后收到原nonce的真实ACK，应保留旧超时与原投递错误，重核同workspace和原executor身份，用canonical解析器及回执写入器核收原次；不重发握手、不伪造提交时间。正式任务包定稿后，提示必须包含TASK_PACK、REQUIRED_SKILL、CALLBACK_TARGET、完成模板及READ_AND_OBEY_REQUIRED_SKILL_FIRST。输入前拒绝不算派发成功；实际Enter后的确认与最终报告核收继续分开记录。
