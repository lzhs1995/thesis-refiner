# NLM 并发能力与自动调度

## 规则来源和能力边界

截至2026-09-21，已核的 Google [额度说明](https://support.google.com/gemininotebook/answer/17670842?hl=en) 与 [套餐说明](https://support.google.com/gemininotebook/answer/16213268?hl=en) 没有规定“同账号只允许一个请求在途”。本机旧单并发来自 skill、预算 runtime、broker 和 transport 的保护范围。它解决共享状态冲突，不能当作 Google 官方账号安全数值。

两个上游工具本身支持并发，默认值代表不同层次：

| 固定源码 | 已核能力 | 使用边界 |
|---|---|---|
| [jacob-bd batch](https://github.com/jacob-bd/gemini-notebook-mcp-cli/blob/f212ed9a321351aadf7ff7271469d6d4663df7d3/src/notebooklm_tools/services/batch.py#L98) | 批量查询默认5 | 不是 Google 推荐安全值 |
| [jacob-bd base](https://github.com/jacob-bd/gemini-notebook-mcp-cli/blob/f212ed9a321351aadf7ff7271469d6d4663df7d3/src/notebooklm_tools/core/base.py#L514) | 共享状态锁不覆盖网络I/O | 不等于本机旧 transport 可直接解除锁 |
| [notebooklm-py MCP聊天](https://github.com/teng-lin/notebooklm-py/blob/d39a459d63d5ecc1b76cec14beca655866802509/src/notebooklm/mcp/_chattasks.py#L77) | Semaphore/FIFO，默认3 | 维护者也记录过账号并发突发节流 |
| [SDK参数](https://github.com/teng-lin/notebooklm-py/blob/d39a459d63d5ecc1b76cec14beca655866802509/src/notebooklm/client.py#L351) | RPC默认16、上传4 | 不可直接换算成长问答并发数 |
| [会话保护](https://github.com/teng-lin/notebooklm-py/blob/d39a459d63d5ecc1b76cec14beca655866802509/src/notebooklm/_chat.py#L451) | 按notebook保护新会话，按conversation保护续问 | 同一会话依赖顺序保留 |

本机已用原计划中的必要题完成多批两路真实验证。复用条件是账号、执行器、共享预算、transport和实际证据均绑定；不能把这个结论迁移成其他账号的无条件保证。新环境先使用串行能力，缺少的并发能力在任务私有目录验证。能力已存在时直接复用，无须重复探针或重新请求已经给出的授权。

## 一个账号，一套预算和受控容量

- 已验证入口：一个全局 broker ACTIVE 租约组内最多两题，来自不同notebook、使用新conversation。两个worker隔离请求ID、响应缓冲、原流、取消和cleanup。旧串行入口与新组不能同时绕过同一预算/锁运行。
- 配额与并发槽分离。两题原子检查预算/暂停/保留额度，按各自原始ID各登记一次；失败可能已消耗，不能退款或抹掉旧行。组内并发不增加Google额度。
- 保留现有原ID，代理执行器/transport单独记账。按账号、notebook、操作、文稿哈希、来源集合、轮次和完整prompt做逻辑去重；换代理名称不产生新请求。
- 同notebook的待审题仍有序；上传、处理完成、来源身份/全文核验及查询保留依赖。来源写入和尚未验证并发的控制操作使用独占短窗；不能直接挤入正在运行的两题组。
- 需要重试时，固定 `retry_of`、原FAILED终态/消耗、必要范围和新ID；不能只改 `round_id` 把失败重发包装成新审查。未送出的本地准入失败保留零发送证据后可复用原ID。
- 三路以上仍未验证。先缩短真实空档并稳定两路；只有两路持续饱和且账号实际响应支持时，才为必要任务准备新的隔离执行器和逐级实测。不能用上游5/16默认值直接放宽当前策略。

## READY到下一批的连续执行

1. Owner一次交齐已批准的固定请求、来源/版本、顺序、独立会话要求和执行委托。准备、哈希核验、离线审读及Claude复核放在网络窗口外。
2. 只有真正可消费的协调器才做本地 `claim`；授予/准入时间从这时开始，不能在发聊天通知时提前耗掉窗口。文件等待器可以报告活跃PID/心跳，但屏幕上的“等待”不证明资源空闲。
3. 以任务公平轮转，任务内部保持原顺序。优先长期未服务的就绪任务，组内每任务至多一题；另一个notebook可填第二槽。没有兼容伙伴时用已验证串行入口，不为凑两题无限等待。短来源操作在下一个安全边界服务，不无限排在长问答之后。
4. 立即调用固定任务adapter；它仍须核准账号、原ID、预算、broker、锁、源和实际在途状态。输入或前置条件失败时暂停该候选，继续不受影响的离线工作，不降级检查。
5. 保存完整原流、原生引用/会话与终态、cleanup和进程回收证据；真实归还后直接选下一批。通知只发一次，聊天ACK与本地论文裁决不占网络槽或成为额外门禁。
6. 文稿改版/owner撤销时使受影响的未发送请求失效，保留旧清单。已受理请求先处理原终态，不偷偷取消、重发或把旧答计入新版。

现有“两题一组”在组内等待两条流全部排空后才交接。它没有实现某一worker早结束就立即补第三题的滚动池；报告效率时说清此边界。要改成滚动池，先验证预算原子登记、每槽租约、同对象顺序和独立失败回收，不能仅缩短等待器sleep。

READY 应交付当前实际执行者可用的命令数组、输入和依赖；移交前离线核实入口文件、解释器、执行者身份及绑定。文件名叫 READY、材料齐全或消息已发出，都不等于已进入现役队列或实际发送。素材短批和已冻结材料的音频，不应误挂在无内容依赖的另一篇稿件修改或本地审读之后；仍在原共享资源的安全边界按公平顺序准入。

连续入口中断时先找最后一个已保存的阶段。已结束批次与下一条尚未发送的请求分别处理；有原调用日志、预算/队列记录证明下一条未提交，且原在途已真实排空时，沿原身份和顺序接续未发任务。执行 agent 的模型服务高负载、shell 启动失败、准入前进程检查被终止，与 NLM 额度/认证故障分别记账；不为诊断本地命令另发 NLM 测试题。没有这些证据时不能把本地退出或空表快照单独当成零发送。

## 超时、归还和论文验收分开

准入期限只禁止开始新请求，不能用它截断已接收中的健康原流。绑定的transport应区分首数据等待、无新字符进展和总接收上限。本机已验证配置为首数据300秒、连续无字符进展180秒、总接收900秒；这些是可审计的任务配置，不是Google限制。超时后的状态由实际原流证据决定，不自动重POST。

`COMPLETE`需要完整原答和当前响应契约；HTTP200或退出0不足。完全收回但没有原生引用的回答保留，记来源/覆盖缺口。它的网络资源可以在原流/cleanup/进程/锁均终态后释放，论文审查仍不能计通过。`UNCERTAIN`则保留账号隔离和原租约，核清原请求后显式reconcile；不能因本地进程消失或租约过期清空状态。

本批归还与下一批准入分别判断。归还证据绑定本批原请求、原流、cleanup、子进程和原租约；本批已经实际 `RELEASED` 后，后来者的 `WAITING` 或新 `ACTIVE` 不会使其重新变为未归还。下一次准入另查全局资源、预算及队列顺序。不能为了完成本批归还要求后来者队列为空，也不能把自身归还写成“全账号当前空闲”。

若封装器在真实释放后才发生观察或通知异常，保留原异常，从原终态和释放回执补齐本批归还记录；不重新运行原请求，不动后来者的锁或票据。原票未释放、原流未知或身份不一致时仍须隔离。通知结果与网络结果分别记录，投递不确定先核接收端，不自动再发。

429、额度提示、认证故障按账号暂停新准入；按服务端提示及现有恢复规则处理，恢复先用一条必要任务验证。已有两路健康流是否结束由原证据裁定，不因别路缺少引用去粗暴abort。限流、网络失败、原答缺引用、检索覆盖不足、本地确认稿件错误分别统计。

## 查询空答、持久暂停与单题恢复

`scripts/nlm_query_health.py` 是不发网络的状态机；
`scripts/nlm_query_health_store.py` 提供 `QueryHealthJournal` 和本地 CLI。
它们读取现有两路 `RETURN` 或已规范化的单路 `RETURN`，逐项验证原请求、
完整原答的字符/引用数、终态、释放及被引用文件的哈希，原始回执保持原字节。
`COMPLETE` 仍须满足原生引用和来源契约；普通非空缺引用单独记失败，不能记为额度故障。

- 同一账号使用一个由当前协调者绑定的健康日志；它与权威预算、broker及READY日志分工独立，不额外创建网络槽。
- 两次累计连续空答或一次单路空答暂停后续查询；HTTP200空帧的原因记录UNKNOWN，不能自行解释为认证或Google限流。
- 先从已有真实归还序列 `bootstrap`；常规打开日志时文件丢失、损坏或账号不符会报错，不能自动新建HEALTHY状态。重启保持暂停和已使用的恢复决定。
- 来源操作不改变查询健康状态。暂停期间可以完成来源全文、本地审读及交付准备；普通迟到成功不清除暂停，也不覆盖最后导致暂停的失败引用。
- 当前协调者形成 `FIXED_SINGLE_RECOVERY_DECISION`，绑定同账号、最新暂停失败回执、新恢复依据、一个既有必要请求ID、`query_cap=1`及`automatic_retry=false`。不得复用已送出的旧ID或旧恢复决定。
- 私有adapter在自己的真实准入边界调用 `admit`；恢复准入原子记录为已用，重复调用会拒绝。请求的未知终态继续保留，不能以重启重置这条记录。真实归还后 `record`；成功恢复到既有容量，失败继续暂停。
- 健康模块返回 `network_authorized=false`、`review_credit=false`；预算、资源准入、来源及论文验收仍由原工具负责。安装与离线测试不表示服务已经恢复。

```bash
python3 scripts/nlm_query_health_store.py bootstrap --database /absolute/task/query-health.sqlite3 --account ACCOUNT_KEY --input /absolute/task/real-return-history.json --sha256 HISTORY_SHA256
python3 scripts/nlm_query_health_store.py status --database /absolute/task/query-health.sqlite3 --account ACCOUNT_KEY
python3 scripts/nlm_query_health_store.py record --database /absolute/task/query-health.sqlite3 --account ACCOUNT_KEY --input /absolute/task/RETURN.json --sha256 RETURN_SHA256
```

`real-return-history.json` 的 `returns` 是按实际顺序排列的 `{path, sha256}` 列表。
恢复与准入分别使用 `recover --input DECISION --sha256 SHA` 和
`admit --request-id ORIGINAL_ID`；均须使用相同数据库与账号参数。
若恢复依据含脚本、日志或二进制文件，先用
`scripts/nlm_recovery_preflight.py` 形成兼容的 JSON 证据清单；实际边界调用
`validate_prepared(store.status(), decision_ref)` 后再 `store.recover(decision_ref)`。
原附件和失败决定保留。TLS 分层、原请求未提交判定和实际接续见
[连接诊断与自动接续](nlm-connection-recovery.md)。
现役被pin的runtime、broker及transport保持原字节，由新私有adapter接入。
真实回执重放、持久化测试、当前adapter采用情况分别交付，不用合成测试代替真实恢复。

## 可复用READY日志

`scripts/nlm_ready_scheduler.py`提供 `ReadyQueue`，使用独立SQLite调度日志；它不发网络、不生成Google调用、不修改权威预算或broker。所有协调器复用同一账号调度日志，实际全局互斥仍由原broker/OS锁执行。私有任务adapter负责把原READY转换成以下条目：

- `request_id`：原绑定计算出的64位ID；`task_id`和非负`position`保持任务内顺序。
- `logical_identity`：`account_key/notebook_id/operation/document_sha256/round_id/prompt_sha256/source_ids`；两路不接受既有`conversation_id`。
- `owner_reservation`、`fixed_inputs`：现有授权与所有影响身份的固定文件 `{path, sha256}`；`payload`可保留adapter需要的原始引用。
- `dependencies`：可选的前置网络请求ID。论文语义验收前置条件另外作为已核的输入证据，不能把网络RETURNED当作稿件PASS。
- `retry_of`：必要时保存原FAILED ID、原回执引用和明确范围。

策略包含账号匿名键、`coordinator_id`、`capacity`（1或2）、`admission_seconds`（最多600）和`protected_artifacts`。两路另需 `parallel_capability` 指向私有、已核的 `LIVE_TWO_QUERY_CAPABILITY`：同账号、`validated_capacity=2`及真实验证文件的pin。该声明由协调者据原始证据建立，不是Google安全认证。任务adapter仍核实具体执行器与此能力一致。

常用顺序：`enqueue` → 在执行端已READY时 `claim` → adapter的离线校验 → `mark_started` → 原执行器 → `finish`。`finish`消费包含当前 `group_id`、`batch_return` pin的薄层；实际批次归还须包含原请求回执、网络终态与broker释放，身份、原prompt、原流指纹均保持。它始终返回 `review_credit=false`，由owner另做论文裁决。

未交给adapter的本地RESERVED可以 `cancel_unstarted` 并保留原ID；已STARTED的超时不能这样撤销，使用 `quarantine`，拿到真实终态后再 `finish`。过期不会自动删除活动组。配额失败归还后仍暂停；不要直接改数据库恢复，沿原账号恢复流程固定新状态和后继日志。

CLI只做本地入队和查看：

```bash
python3 scripts/nlm_ready_scheduler.py --database /absolute/task/ready.sqlite3 --policy /absolute/task/scheduler-policy.json enqueue --input /absolute/task/approved-entry.json
python3 scripts/nlm_ready_scheduler.py --database /absolute/task/ready.sqlite3 --policy /absolute/task/scheduler-policy.json status
```

连续执行循环保留在任务私有adapter，使用命令数组和已固定的真实入口。现有被pin的runtime/broker不原位修改；安装新调度模块不等于所有旧任务已自动迁移。模块离线控制与真实NLM配对验收分别保留，不为测试重复成功题。

## 衡量提效

至少记录 READY→消费、消费→首字节、流接收/分块取回、末终态→真实归还、归还→下一准入，以及离线裁决/改版耗时。同时报告完整接收数、原生引用合约通过数、覆盖缺口、确认问题和零重复。

可以报告真实同时RECEIVING时段与交接空档缩短；没有同题、同源、同负载的串行对照时不称“速度翻倍”。两个配对批次之间的时间差也不证明账号一直空闲，须核是否有来源操作、其他任务和必要准备。优先减少程序可消除的等待，不能以少问主题、跳过全文/尾页或降低独立验收换取表面速度。

## 音频后台生成与网络窗口

音频 create、来源写入等控制操作沿已验证的独占短窗；创建 RPC 完整收回并实际排空后即归还。后台音频生成不占本地问答执行槽，状态查询和下载按各自的短操作取得资源并归还。不要因一个音频仍在生成，就让其他已授权的必要工作等待整个生成周期。生成期间的服务端状态与本地 HTTP 在途状态分别记录，原 HTTP 未终态时仍不能提前释放。

问答容量、音频/影片生成额度和本地共享锁属于不同层次。两个问答并发的验证不能自动证明两个生成类写操作可并发；一次下载的 CDN 重试也不是第二次生成。音频只沿原 artifact 观察与下载，详见 [音频流程](nlm-audio-overview.md)。
