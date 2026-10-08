# Enter 与原生投递回执

论文任务的 prompt、任务包和 callback 只复用当前安装的
`multi-agent-collaboration/scripts/cmux_bridge.py`。通用实现与完整规则见
[协作仓的 Enter 不等于发送](https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/verified-compose-delivery.md)；
实际调用使用本地完整固定 release，不混装单个脚本。

## 共同判据

- 输入前绑定接收方 workspace/surface/pane UUID、原生进程 PID/出生时间、
  可执行文件和 argv 哈希、session，以及 transcript 的 inode/device、
  追加边界和边界哈希。共享后台的继承环境不代替真实 caller。
- 原 attempt 落盘后只粘贴一次。观察到自身完整 payload 与稳定 composer
  才按 Enter；等待预算耗尽不按键。Enter 被 UI 当换行仍是未送达。
- 只从原 transcript 的原边界后找新增、全文精确相等的原生 user 消息。
  全文包括空白和换行；子串、旧历史、全盘 marker 检索、屏幕活动、ACK、
  退出码、空 composer 和 assistant/tool 引用都不能证明收到。
- `RECEIVED` 才确认收到。Claude `queued_command` 表示接收并排队，
  `execution_confirmed` 仍为 false；执行、报告完成与论文验收分别记录。
  `RECEIVED_ALTERED`、`NOT_RECEIVED`、`UNVERIFIABLE` 均不报发送成功。

## 原次恢复与 hook

先对原 controller 使用 `--reconcile-only`。需要诊断时可运行：

```bash
rtk proxy python3 -B scripts/cmux_native_delivery.py --attempt /absolute/attempt-0001.json --wait 3
```

退出码 0 表示收到，3 表示当前无完整匹配，4 表示正文被改写或证据不可核验。
该命令从协作 skill 的安装根运行；不补造输入前基线，不迁移旧任务控制器。

完整原 payload 卡在 composer 时，沿原 `submit-text`、`submit-task-pack`
或 `submit-completion-callback` 增加 `--recover-stranded`。恢复先核迟到原生
记录，再核原身份、原完整草稿和稳定状态。自动及显式恢复共用一次补 Enter
预算；`EXTRA_ENTER_INTENT` 落盘即消耗，按键失败也不重置。不重贴正文、不
另建 nonce、不删 journal，不另走 Tab。排队、压缩、重连、未知或外来草稿
不补键；预算用完仍可只读核收，未确认就明确保留未确认。

两客户端 PostToolUse 的 `cmux_native_delivery_guard.py` 只核当前投递调用，
未确认 exit 2 并返回原次恢复命令；普通工具不扫旧账，没有 disable/advisory
放行。安装器退役本包旧屏幕确认与 send-proof Stop hook，保留其他完成门禁。
论文 skill 和 CLAUDE.md 引用同一规则，不复制另一套发送器、重试器或 hook。

## 效率与验证

原 Claude 分担独立待办：一人核实现，一人核反例；主管负责整合和唯一安装。
同 pane 两 tab 的输入串行，计算可以并行。报告已落盘就先核报告，不因回调
未确认停主线，也不借同一旧报告让执行者反复空转。下一步与等待依赖必须沿
原通道交回执行者。

disarm 后复用协作安装的 idle Stop hook 与 `executor_ready.py persist`，
每 60 秒处理一次求派发请求，直到主管真实回复、新任务或 operator stop。
未确认请求保留原 payload、marker 和原 journal，重启也不重贴；旧
`CONFIRMED` 记录必须重验原生回执，已排队或读屏失败不堆新请求。全程进程锁
防止重复循环，Stop 递归只结束当前 hook，不清除求派发义务。主管通过原
bridge 或请求给出的精确 mailbox 回复，自己线程里的答复不能算接收方已收到。

源码测试、固定 release 安装、真实 hook 入口、现役客户端加载、完整原生回执
和论文验收分别报告。一次成功不是所有终端 UI 或未来所有消息的无条件保证；
没有证据时明确失败并保留可恢复原次，禁止假报成功。
