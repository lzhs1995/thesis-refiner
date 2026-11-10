# 新 NLM 任务的显式执行绑定

`nlm_runtime.py run` 可显式采用 MAC 的 `resource-execution-v1` 执行约束。
这是实际传输进程启动前的检查；不约束直接 NLM CLI、MCP、浏览器或远端服务，
也不能撤销已提交请求。原预算、请求键、答案检查与 UNKNOWN 回执继续使用。
没有 `execution_contract` 的旧 binding 保持原入口，不自动迁移 controller 或票据。

## 绑定文件

在原完整 binding 中增加以下对象；示意值须替换为本任务真实身份与字节固定引用。
所有文件引用都使用绝对规范路径、`bytes` 和完整 `sha256`，不得用示意值运行。

```json
{
  "execution_contract": {
    "schema": "nlm-execution-adoption-v1",
    "new_tasks_only": true,
    "actor": {
      "workspace_uuid": "实际外层workspace UUID",
      "surface_uuid": "实际surface UUID",
      "pane_uuid": "实际pane UUID",
      "session_id": "真实native foreground thread UUID"
    },
    "controller": {
      "source": "/absolute/immutable/mac/source",
      "files": [
        {"relative": "scripts/resource_broker.py", "bytes": 123, "sha256": "完整64位SHA"}
      ]
    },
    "cwd": "/absolute/existing/task-directory",
    "environment": {},
    "inputs": [
      {"path": "/absolute/frozen.pdf", "bytes": 123, "sha256": "完整64位SHA"}
    ]
  }
}
```

`controller.files` 必须包含该不可变 MAC 源的**全部** `scripts/*.py`，示意中
的一项不够。`broker_module` 必须与其中 `scripts/resource_broker.py` 的完整
引用一致。`transport_artifacts` 也使用完整引用，包含 argv 的实际可执行文件
及传输脚本；argv[0] 必须是实际规范绝对路径，不能依赖 PATH 或解释器软链接。
`environment` 是完整传给子进程的环境，不合并调用者环境；需要的值须显式固定。
其中若包含敏感值，只存任务私有 binding，不放公开仓库。

`actor.workspace_uuid/surface_uuid` 必须与原 binding 相同。身份由 MAC 原生
checker 重新获取；角色、继承环境、`w1:p2` 或调用者 JSON 都不能代替认证。
当前 MAC 原生 checker 面向 cmux 的真实 caller snapshot；不能据此声称已认证
Herdr 内层不同 agent/session 或相同 pane 名所在的不同服务。没有该能力时拒绝，
不得把内层 actor 降格为外层 surface。JS→Python 的额外祖先链如果不受原 checker
支持，同样拒绝；可使用已支持的直接 Python 入口，但不能放宽 checker。

`inputs` 绑定本次冻结材料。query 的 `document_sha256` 必须对应其中一个真实
文件；source_add 的路径和 SHA 必须都对应其中一个文件。请求禁止覆盖执行、
native、controller、actor、generation、资源、argv、cwd 或环境等字段。
`request_revision`、`attempt_id` 和 generation 由入口与 broker 生成，不由请求指定。

## 实际顺序与恢复

1. 验证完整 controller 与 broker pin，显式编译同版源码，不修改 `sys.path` 或
   读取旧 pyc。缺任一 enforced API 立即拒绝，没有旧 API 降级。
2. 在原预算目录 `enforced-preparations/<原request_key>/` 固定规范化请求、prompt
   和 contract。相同路径的不同字节拒绝覆盖。命令使用这里的 prompt；output_dir
   仍是原 `receipts/<request_key>/`。固定后调用 MAC 静态 preflight，验证原生
   身份、完整输入/transport/controller 字节；这在构造预算/资源 DB 或入队前完成。
3. 沿原 `nlm-account:<account_key>` 队列 request_enforced/grant_enforced。预算
   在拿到原资源票后按既有规则准入，不为构造 contract 提前计费或占用资源。
4. 复用原请求/lease/答案回执流程。薄 facade 核实际 argv 完全等于固定 contract，
   MAC 在原锁内再核 native actor、输入、generation 与操作，再启动进程。
   回执额外保留 `execution` 与 `enforcement_scope=PRELAUNCH_ONLY`。
5. 只有原流程确认终态并排空后才 release_enforced，带原 result.execution。
   预算拒绝等零启动情况带原 lease.execution 和 no_request_submitted。

预算恢复后，同一固定请求若没有预算 request 记录而原票已 RELEASED，入口明确
调用 `requeue_unsubmitted_enforced`。MAC 在原锁内验证原 token/generation、
完整 no_request_submitted 释放证明、零 invocation、无进程及无执行 intent，
在同一数据库保存旧 generation 的完整 lease、binding、release proof 与各自SHA，
再将原票排到 FIFO 尾部。下一 grant 分配新 generation，原 attempt/contract 不变；
旧 token/generation 失效。存在请求记录、UNKNOWN 或曾调用过的票不能这样重排。

重复 COMPLETE 仍做原回执、原答与来源检查，并核同一 execution contract 和
原票已经 RELEASED，然后直接返回缓存，不新增票据或预算。旧缓存缺执行绑定、
旧票或已变化的 controller/contract 都拒绝升级。STARTED/UNCERTAIN 保留原请求、
费用、原票和原 controller；新实例不能重新执行。prelaunch 拒绝若发生在准入后，
也保留原 UNCERTAIN 证据，不以没有答案推断远端无事发生。

`reconcile` 沿原回执处理真实终态；对新执行票继续使用 release_enforced，
原执行元数据不得由普通 release 绕过。执行 UNKNOWN 还须满足 MAC 对原进程与
精确 readback 的要求；不能拿另一请求或一次新查询冒充原请求核查。

## 本机无网验证

`tests/test_nlm_execution.py` 使用实际 MAC Broker、临时数据库和具名无网传输，
只 mock native 身份来源。设置 `COLLABORATION_BROKER` 指向要采用的准确源码：

```sh
rtk proxy env PYTHONDONTWRITEBYTECODE=1 COLLABORATION_BROKER=/absolute/mac/source/scripts/resource_broker.py python3 -B -m unittest discover -s tests -p test_nlm_execution.py -v
```

这些测试证明指定入口的拒绝与原回执流程；不证明活跃客户端已采用新版、不证明
真实 native caller 在所有祖先链均受支持，也不证明远端写入成功或论文科学验收。
正式采用仍须固定完整版本、实际进程入口和合法原生身份；没有新执行约束的旧任务
继续原绑定，不能在新流程中修补或解除旧 UNKNOWN。
