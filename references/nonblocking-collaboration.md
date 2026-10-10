# 非阻断协作恢复

适用版本：论文技能 2026.10.10.5 / multi-agent-collaboration 0.4.19。
实现统一放在协作 skill；本文不复制 hook、发送器或身份解析器。

旧实现把冻结报告、待核回调或无法解析的 caller 变成所有工具与 Stop 的拒绝条件，
使执行者无法自行诊断，也让继任主管接不上原 Claude。0.4.19 将 closeout、握手回执、
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
