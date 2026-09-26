# 运行时检查与经验维护

## 先确认实际入口

`scripts/hook_doctor.py` 只读显式配置中的 hooks 子树，并通过真实 Node 入口检查“未绑定任务放行”和“缺失的已绑定回执拒绝”。它区分文件安装、当前配置注册、历史配置和实际客户端调用；退出 0 只表示入口探测通过，不表示正在运行的客户端已重载。

```bash
python3 scripts/hook_doctor.py --config /absolute/current/settings.json --legacy-config /absolute/old/hooks.json --output /absolute/run/hook-doctor.json
```

实际客户端配置随产品与平台确定。序列化字符串包含 Windows 路径、旧 hooks.json 中有条目、脚本语法通过，都不足以证明 macOS 的当前客户端加载了 hook。不要为修诊断程序而无授权重写其他 hooks。安装器不自动注册全局 hook；显式任务编排可以直接调用当前入口。

`a5-termination-auditor.js` 只处理显式 `workflow_checkpoint` / `THESIS_REFINER_CHECKPOINT` 和可选 `delivery_checkpoint` / `THESIS_REFINER_DELIVERY_CHECKPOINT`。两者都是绝对路径。未绑定任务原样放行；已绑定任务缺少回执则拒绝。复制 hook 到另一个运行目录时通过绝对 `THESIS_REFINER_ROOT` 指向同版 skill，或保留原目录结构；不要依赖复制后的 `../scripts` 恰好存在。`THESIS_PYTHON` 固定实际解释器。完成边界调用，不阻断普通中间工作。

## NLM 工作器的离线依赖预检

查询、原会话状态读取和历史读取可能通过不同的启动脚本进入同一套 SDK。主查询能运行，不证明临时读取脚本带有相同的 `sys.path`。已出现的真实情况是：读取脚本遗漏固定 h2 依赖，在本地 HTTP/2 transport 构造时失败；恢复原工作器依赖后，同一原会话的历史读取才实际返回。第一次失败不能记成空历史，也不能归因于 Google、代理 TLS 或 ALPN。

在准入前复用已批准工作器的解释器、cwd、环境和依赖路径，执行以下离线预检；只预检本次实际使用的组件，不重新安装共享 SDK：

1. 记录 `sys.executable`、Python 版本、实际 cwd 及固定依赖目录。不要只记录命令中的 `python3` 名称；交互 shell、子进程与临时脚本必须使用同一解释器和相同路径顺序。
2. 导入实际 SDK、`httpx`、`httpcore`、`h2` 与本次 transport，记录各模块的 `__file__`、版本和原字节哈希，并与任务 binding 对照。仅语法编译或在父进程中导入不够。
3. 在同一个子进程中，用实际批准的参数构造并关闭 HTTP/2 transport/client；禁止调用 `request`、`send`、SDK RPC 或任何登录/刷新方法。客户端构造会发现延迟到此阶段才暴露的可选依赖缺失。该步骤不作 TLS、认证或网络可用性证明。
4. 导入或构造失败时保持原 READY，不调用准入入口；保存本地异常和实际失败阶段。若历史实现已登记调用，沿真实记录核收，不能自行清票、退款或把旧请求复用为新请求。修复只补原绑定已具备的依赖路径，需改依赖版本时另做明确绑定。
5. 预检成功后仍须核原请求终态和共享资源边界；用既定必要操作取得真实响应。原会话读取的 HTTP 200、完整 RPC 和返回值分别记录，未取得响应不能填写 `[]`。

新接续脚本、解释器路径或依赖绑定变化时重做这项预检；相同字节和相同入口的已验证阶段可复用记录。不得在正在接收长答时修改其固定模块。

## 文件来源的多客户端预检

一个文件来源操作可以先用 RPC 客户端注册来源，再构造独立的文件上传客户端。只构造第一个客户端、或只导入上传模块，不能覆盖第二个客户端的延迟初始化。一次真实故障在注册返回 source ID 后，因第二次构造把已存在的共同追踪文件判为重复运行而触发本地断言；文件上传请求尚未开始。这是适配器故障，不能标作 NLM 断网或来源全文丢失。

在原工作器环境中，按 SDK 实际顺序预检所有客户端构造和关闭。用明确标为离线 fixture 的临时记录模拟第一阶段已有追踪文件，禁止发送请求或把 fixture 记成真实来源。追踪状态应由整个操作持有：不同客户端共用不冲突的请求编号，各次连接尝试保留到同一操作记录；不能在每次客户端构造时重置、覆盖或要求该记录不存在。仍须保留每个客户端的实际代理、TLS 验证和依赖身份。

修复后先离线核原反例，再在原请求真实终态和原共享资源边界接续尚未提交的阶段。真实注册返回值和原 HTTP、文件尚未发送的证据、原失败与释放记录必须全部保留。已有 source ID 不等于已上传；上传完成不等于处理 READY；READY 不等于全文全等。成功续传与新的完整审读分别记账。

## 经验进入代码的条件

维护“问题—触发条件—原失败—成功修复—边界—实现—回归”映射。先读取上次经验工程和当前安装增量，分别标已实现、需加强、环境专用和未核实；不把同一条规则重复附加多次。原论文、账号、绝对现场路径和原始会话留私有证据包，公开测试用合成数据。

先验证原入口与反例，再扩展现成模块。缺依赖、cwd/登录 shell、输入框解析和投递不确定分别归因；本地故障不计作服务器拒绝或模型不可用。输入框检测有疑义时保留屏幕及解析结果，不强制清空未知输入；依用户既有授权推进独立工作。当前任务握手未通过就不声称 Claude 审阅；其他审阅者独立署名。

新工具不能自动接管现役账号、broker、预算、应用锁或来源白名单。正在运行的任务继续其固定组件；升级后的新任务或已安全归还的阶段才显式绑定新版本。安装通过、离线测试通过、真实回执重放、客户端实际加载四项分开报告。

连接恢复维护优先使用可叠加的工具。`nlm_recovery_preflight.py` 兼容既有 JSON-only 健康入口，`nlm_tls_probe.py` 只处理诊断，不替换正在运行的 query transport。安装后核现役固定文件仍为原哈希；不要为修一个证据解析错误更改所有账号、共享代理、SDK或健康日志。新诊断工具的本地环回测试、旧故障真实回放、既有实际恢复和现役采用分别记录。

## 安装与回滚

沿 `scripts/install.py` 的 dry run 审阅维护文件差异，再执行本地已授权覆盖。原件和文件哈希保存在备份目录，历史私有资源保持。`INSTALLED.json` 是完成安装回执；`INCOMPLETE.json` 是部分失败，不能当已完成。

```bash
python3 scripts/install.py --canonical /absolute/skill --codex-adapter /absolute/adapter
python3 scripts/install.py --canonical /absolute/skill --codex-adapter /absolute/adapter --apply
python3 scripts/install.py --rollback /absolute/backup/INSTALLED.json
python3 scripts/install.py --rollback /absolute/backup/INSTALLED.json --apply
```

安装与回滚的写入入口在 POSIX（macOS/Linux）按目标根使用相同非阻塞 `flock`，同时涵盖 canonical 与 adapter；遇占用直接报 `INSTALL_ROOT_BUSY`。锁文件在目标根的父目录，命名为 `.<根目录名>.thesis-refiner.lock`，保留文件而不删除；进程结束自动释放持锁。其他自动维护写入者须调用同一 `mutation_locks(canonical, adapter)`，手工编辑应在操作结束后进行。不支持该锁的平台拒绝实际写入，dry run 仍可读。

回滚先核全部将改文件与备份，再在临时文件写入及 fsync 后、提交前重新核当前字节；提交后和成功回执前也核结果。检出的冲突保留目标新字节，写入不完整记录，不记成功回滚。该互斥只约束使用同一锁的写入者；字节复核可检出暂存期间的外部编辑，但不是对任意绕锁进程的文件系统原子比较交换保证。回滚测试在临时安装副本完成，不为测试而回滚正在使用的 skill。

hook 将完整 Buffer 拼接后统一解析 UTF-8，并原样输出原字节；分块边界可落在中文或 emoji 的多字节编码中，不能对每块隐式解码。维护源统一并不等于公开发布，推送、PR、合并依用户当次授权。
