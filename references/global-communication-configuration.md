# 全局通信配置与主动求派

本 skill 复用 multi-agent-collaboration 0.4.8 的
[配置与请求生命周期](https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/configuration-and-reasks.md)。
本机执行时解析已安装协作 skill 的真实路径并读取同名参考文件；在途任务保留原控制器。

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
