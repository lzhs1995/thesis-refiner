# 音频创建后的阶段限定恢复契约

本契约补充 [音频概览流程](nlm-audio-overview.md) 的执行者继任入口。已有真实创建回执及 artifact 后，继任者只观察该 artifact 或下载到原目标；不再执行 `audio_create`、`source_add` 或 `query`。成功受理后的后台状态 `unknown` 可以继续观察；创建是否受理未知、原请求资源终态未知时，本入口拒绝放行。

`scripts/audio_recovery.py` 是离线完整性检查器，不执行 NLM、下载、计费、队列、锁或应用操作。`OFFLINE_ELIGIBLE` 只表示所提交的这一条请求符合固定恢复范围。当前唯一执行者身份、实际资源准入和剩余额度仍由原运行器核实；不能把此结果当作这些事项已通过。

## 输入与调用

任务私有目录保存 `contract.json`；所有引用均为真实存在文件的绝对路径与 SHA256，格式严格为 `{"path": "...", "sha256": "..."}`。执行者从既有授权交接记录固定契约哈希，不在调用前重新取任意新文件的哈希来覆盖预期值。

```bash
python3 scripts/audio_recovery.py validate \
  --contract /absolute/task/audio-recovery/contract.json \
  --contract-sha256 <previously-pinned-sha256> \
  --request /absolute/task/audio-recovery/request.json \
  --operator-uuid <current-executor-uuid> \
  --workspace-uuid <current-workspace-uuid>
```

| 契约字段 | 固定内容 |
|---|---|
| `schema_version` | 整数 `1` |
| `plan` | 原任务、notebook、account key、format/language/length/focus_prompt、创建上限及目标目录 |
| `intent` | 原生成意图，含 request ID、原请求 pin、来源选择 pin、整数 create_limit=1、automatic_retries=false |
| `created` | 原 artifact 及 request/receipt/release 三个 pin；沿原实际回执，不重新声明创建成功 |
| `download_request` | 原任务的固定下载请求，含原 artifact 和绝对输出文件；目标父目录必须与 plan 一致 |
| `succession` | 原授权继任回执，绑定 created pin、artifact、继任 surface UUID；两项允许操作及三个整数零上限 |
| `binding` | 任务私有观察入口的固定绑定，含 executor/workspace UUID、account/notebook、original_artifact_id、observation_only=true |
| `operations` | 创建后已有操作的 receipt/release pin 对，按原时间顺序列全；没有后续操作时为空数组 |
| `preserve` | 本任务其他应保持原字节的意图、失败或预算记录 pin 数组；不从其中推定尚有额度 |

本实现兼容已验证的既有音频适配器回执结构。`succession` 使用 `executor_surface_uuid`、`created`、`artifact_id`、`allowed_operations`（依次为 `studio_status` 和 `audio_download`）、`audio_create_cap=0`、`source_add_cap=0`、`query_cap=0`、`original_user_authorization` 及 `original_files_and_failures_preserved=true`。`binding` 使用 `surface_uuid` 和 `workspace_uuid`。不同格式应在私有任务边界做有据可查的适配，不能替换或改写原回执。

请求仅含 `task_id`、`notebook_id`、`operation`、`artifact_id`，可附原运行器的 `phase`、`round_id`、`label`；下载另含 `output`。加入来源、prompt、创建参数或其他操作字段会被拒绝。UUID 由当前运行器传入，不能直接照抄契约来冒充身份核验。

## 检查范围

- 原计划、生成意图、原请求、实际 bound request、source selection、真实 artifact 和参数逐项相符；来源列表、prompt 换行与顺序保持。
- 真实终态 receipt、transport、raw result 和 broker release 相互以 pin 连接；lease 身份一致，子进程、在途请求和外部锁归还证据明确。单独的 `COMPLETE`、`RELEASED` 或退出码不能代替整条证据。
- 原生成只有一次本地调用证据，自动创建重试为整数零；所有次数和退出码拒绝 JSON 布尔值冒充整数。它不据此声明全账号只有一次调用或剩余额度安全。
- 创建后的已知失败可以保留，但必须有真实终态与释放证明；`UNCERTAIN` 继续拒绝。原失败文件不改写。
- 下载必须有该 artifact 的实际 completed 状态；其他 artifact、重排的旧状态或来源/提示漂移不授予下载。固定目标使用规范绝对路径，拒绝符号链接或 `..` 改变其实际落点。目标已有文件时返回 `DOWNLOAD_ALREADY_EXISTS_VERIFY_LOCALLY`，交由原流程验哈希与完整解码，不覆盖重下。

哈希只证明输入文件与既定内容一致，不是签名，也不能证明操作者提交的历史列表没有遗漏。调用方负责读取全部原在途记录、核当前 owner/activation 和真实准入；新调用必须再次检查，不能长期复用旧离线结果。异步原业务在变时，遵循既有唯一执行者和固定文件规则，避免核完后修改输入。

## 完成轴与验证

退出码 `0` 返回 `OFFLINE_ELIGIBLE`；退出码 `2` 返回拒绝理由，均不写输入。结果显式将 network、quota、current authority、resource admission、media/content 标记为未执行或未核验。解码通过、机器转录核对、实际听审及逐句学术内容验收仍按原音频文档分别记录。

`tests/test_audio_recovery.py` 通过实际 CLI 子进程检查观察、完成后下载、已有文件、错 artifact/UUID、重新创建、参数漂移、布尔计数、未知终态、缺失或被改写的 pin 和操作顺序。测试全部使用临时合成身份；真实章节回执重放放在任务证据目录，不写入通用 fixtures。集成现役运行器前须另外记录其确实调用了本入口；安装文件存在不等于运行中已启用。
