# 非阻断协作恢复

适用版本：论文技能 2026.10.11.1 / multi-agent-collaboration 0.4.23。
实现统一放在协作 skill；本文不复制 hook、发送器或身份解析器。

旧实现把冻结报告、待核回调或无法解析的 caller 变成所有工具与 Stop 的拒绝条件，
使执行者无法自行诊断，也让继任主管接不上原 Claude。自 0.4.19 起，closeout、握手回执、
consensus、lease、idle、reask、PostToolUse 投递和报告条目改成非阻断观察入口。
观察失败也正常返回；不执行旧 gate，不输出 deny/block/continue:false，不自动续跑。
旧检查器只供显式诊断，不能恢复为全局会话锁。

共享 daemon 可能沿用启动时的 workspace 环境。当前 caller 由原生 foreground
thread 和实际 kernel/cmux UUID 证据确定，不要求特定 `codex resume` 命令或旧主管
会话号。使用更新后的 `cmux-agent self`；其输出与 raw `cmux identify` 不能混用。

用户已授权的继任主管联系指定原 executor 时，可以固定授权正文、双方
workspace/surface/pane UUID，通过 successor-rebind-v2 发起维护握手，包括跨 workspace。
不要求失效主管批准、不以旧任务尚未结算拒绝通信。此授权仅建立当前联系；正式新
任务另定范围，旧 pack、nonce、callback 和共享文件写入责任不会自动转移。

发送器继续保护现有草稿、持久化每次输入意图并防止重复输入。原消息的真实收据
仍须来自绑定接收端，在原 EOF fence 后新增完整相等的 native user 记录。未确认
就保留 pending，沿原 controller 只读核收；维护握手、正文已读、任务执行和业务
接受分别记录，不能把自动 hook 记录或旧 ACK 当新握手。

协作恢复验收分开记录代码测试、不可变安装、每个当前客户端的实际自动调用，以及
各消息的原生接收。手动 subprocess 证明入口行为，不证明活跃客户端已加载。
只有逐会话证据齐全，才可报告该组协作已经恢复；否则交代具体未验项并继续独立
已授权工作。健康执行者继续推进，故障执行者按已有安全交接授权暂转 SOLO，
恢复时复用原会话。修通信不重开已接受的论文审查轮次。

## 普通文档命令与新 footer 的现场修复

维护中出现过两类新问题：一是 PR/HANDOFF 的字面 heredoc 含引号和发送命令示例，
被 shell 词法分类误当成终端操作；二是原 Claude 的模型名与 cwd/时间分行，或工具
摘要出现 `+N more`，导致空闲输入框被错误标为 UNKNOWN。这些是本地分类故障，
不能称为 Claude API 故障、消息拒收或会话永久失效。

0.4.20 对文档和引号搜索按数据处理；词法解析失败本身不再扩大为普通工具门禁。
真实 raw terminal writer、嵌套 shell 和带残缺引号的实际发送仍接受对应检查。
复用原失败输入验证误报消失，同时用真实入口验证实际发送保护仍有效；不通过
跳过原发送器或伪造 caller 环境掩盖问题。

footer 只在完整 composer 边框外按已测字段结构识别。工具计数溢出须为正确的正数
摘要；模型、cwd、时间和上下文字段不完整时保留 UNKNOWN。输入框内长得像 footer
的文字仍是原草稿，活动工具和新增未知尾行不能被闲置状态覆盖。旧报告中的
Compacting、Reconnecting 或 callback 失败字样不能替代当前 activity。

公开回归素材使用合成历史与相同的 footer 几何结构，不发布真实会话、任务路径或
原生回执哈希。通过离线分类回归后，再单独实测当前客户端调用与新原生接收；
不能把解析器通过、空输入框或完整旧 callback 当作继任握手成功。

## shell exec 后的直接子进程身份

现场出现过 helper self 与受保护发送器报告 thread selector 和 ancestry 不一致：
shell 执行最后一个命令时可以被 exec 替换，使工具直接挂在 managed daemon 下，
旧采集器只找父链中的工具 shell，因此漏掉当前工具自己的 selector。这是本地方向
身份采集缺口，不能归因于 Claude API、旧主管未批准或 executor 拒绝继任者。

0.4.21 只在确认当前工具直接属于实际 managed daemon 且没有中间 selector 时，
读取当前进程内核证据；其 PID、父 PID、thread selector 与调用环境须相容。随后
仍核原生 foreground、唯一活跃客户端、TTY、workspace/surface UUID，并在返回前
重新读取进程出生时间、执行路径、父关系和 selector，漂移或真实冲突不能通过。
不要求保留一层人为 wrapper，不接受仅由脚本自填的身份，也不要求旧 resume 命令。

在实际调用方分别验证 self 和受保护投递；多工作区或另一进程形态通过不能代表
本会话通过。新 native user、executor ACK 和任务接受仍分别留证。某个 caller 未通过
时只暂停该次输入，继续其他授权工作，不把修复成功或源码测试扩大成全客户端恢复。

## 排队请求与正式通知恢复

主管在重要工具边界、长批次前和进展报告前，读取当前 surface 的 queued follow-up
inputs，校验固定正文的 SHA/字节数并按原请求 mailbox 回件。相同 marker 去重，
记录已消费和仍待办项；排队、正文已读、native user、ACK、报告接受分别报告。
不因持续运行而让其他主管的维护请求长期不可见。

0.4.22 已测支持完整边框外的模型、目录、计时三行 Claude footer；未知布局与
现有草稿仍保护。0.4.23 在创建正式任务 journal 前校验单行和长度。新派单从
finalized pack 生成 TASK_PACK_V2，不手写旧多行模板。旧 wire 格式若严格零输入
（第一 attempt 为 NO_INPUT、events=[]），由原主管调用协作技能的
repair_task_notice.py；先只读 READY_ZERO_INPUT，再执行一次 --apply。它验证
并使用完整原 controller，原 pack/nonce/callback 和旧 attempt 不变，只追加
唯一第二次尝试。未知、已贴、排队、已收到消息不得转换或重贴。其他情况保留
未确认并继续独立正文/证据工作；健康握手不重跑，已接受科研审轮不重开。

共享维护只有一个合并者。其余主管提交原证据与明确 reply_path 后继续主线；
Claude、协作子 agent 或模型 API 不可用时，按已有授权转 SOLO。双 Claude
仅接独立未完范围，同 pane 输入串行；恢复后在安全边界复用原上下文会话。
