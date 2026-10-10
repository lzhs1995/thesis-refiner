# 全局通信配置与主动求派

本 skill 复用 multi-agent-collaboration 0.4.17 的
[配置与请求生命周期](https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/configuration-and-reasks.md)。
本机执行时解析已安装协作 skill 的真实路径并读取同名参考文件；在途任务保留原控制器。

全局安装不是任务入组。普通新会话不受 supervisor 工具/结束门禁约束；只有明确
参加协作并绑定当前 native session ID 的参与者才受任务门禁约束。先判作用范围，
再认证 caller。已有绑定的任务仍严格验证身份、原始投递及 callback。旧 marker
没有 native session 证据时只保留原记录，不用新会话补造绑定或把旧任务派给它。

CLAUDE.md 和 skill 文档是规则入口，不能替代 JSON 中的 hook 注册。
cc-switch 切换或导入配置后，由协作 skill 的唯一配置守护器修复自有 hook；
不复制凭据、不切换 provider、不另造发送器，也不为每个会话创建 watcher。
配置已修复、当前客户端自动执行 hook、完整原生日志接收和真实 callback 分别验收。

用户明确授权后，executor 每60秒询问直到绑定的主管回复、新派发或用户停止。
Stop hook 与命令共用一把锁；原终端消息未确认时只更新文件通道，禁止堆叠新 prompt。
主管通过已有 PostToolUse hook 发现请求并按原 mailbox 模板回复；答复须精确绑定
caller、supervisor、task、episode 和已发 marker，等待类答复必须有具体解除条件。
询问次数、文件写入和实际送达分别计数。API 或客户端中断须报告，不能虚称仍在运行。

queued follow-up inputs 是忙碌 Codex 的待处理状态，不能当成功接收，也不能据此重发。
只按原接收端新追加的完整 native user 验证。跨工作区由原主管核其 executor；
通过一个工作区就恢复其原论文任务，通信维护不新增科研验收轮。

## 身份识别失败不得封锁会话

协作 hook 无法识别当前 caller 时，不具备施加任务门禁的依据，必须放行普通
工具和 Stop。已入组会话也能诊断、编辑修复、记录状态、执行已授权 SOLO 和
诚实结束回合；不重复触发阻断。任务标记、冻结报告、原回调与投递预算原样保留，
不能据此冒称收到、接受或多 agent 共识。恢复后下一次核验重新检查真实任务。

新建、切换和接手的 Codex supervisor 均可按现有用户授权主动握手，使用当前
原生 foreground thread、内核进程和 workspace/surface 证据；不要求固定的
codex resume 命令，也不绑定旧主管会话号。终端发送仍核验真实双方。

优先推进用户原任务，按独立交付物与当前容量使用零、一或两个 executor。
本机通信入口故障不等于 Claude API 故障；经有限重试仍不可用时，按已有授权
由 Codex 接管并标注 solo_self_review。原 Claude 恢复后只在安全边界重新接入；
不为通信维护重开已接受的科研审轮，同 pane 两 tab 的终端输入保持串行。
