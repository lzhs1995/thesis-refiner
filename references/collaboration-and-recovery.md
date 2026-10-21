# 协作、租约与恢复

任务分工、握手预算归因与已验收成果收尾见[协作提效与收尾](collaboration-efficiency-and-closeout.md)。沿用下列原会话、身份与资源边界。

身份不符必须 fail-closed、零发送：发送前核实当前 caller 与指定 receiver 的真实
workspace、surface、pane UUID 和原 session；UUID 缺失、相互矛盾或身份未核实，不可按
标题、焦点或数字 ref 猜目标。正常协作沿原同 workspace；用户明确授权的跨 workspace
继任维护必须固定两端 UUID/session 和授权原文。忙碌、Goal、压缩与输入方式的限制已取消，
身份核验和原次去重仍生效。可使用共享 cmux_workspace_guard/bridge 或已完成等价核验的
直接发送；不恢复裸 cmux 禁令，不把配置写入当现役加载。

## 当前通信与身份

先用原生 `cmux-agent self` 核真实caller，并用实时tree核目标UUID及原会话。
数字ref只作显示；标题、focus、cwd和共享后台继承环境均不授身份。原同workspace
的独立surface可及时互通，同pane不同tab允许协作，输入串行。用户明确授权的
指定维护/继任跨workspace联络沿共享协议办理，不转让旧callback或文件所有权。

prompt就绪立即发送，正常工作、Goal和压缩不是通信禁令。不要求为握手停Goal。
允许直接cmux通信；推荐统一共享bridge，以避免自写重复Enter和全量日志扫描。
新消息以原接收端新增含marker的user消息证明收到；排队、按键和工具成功不算。
正文读取、精确ACK和业务接受分别记录。历史attempt继续由完整原controller核收，
不因超时或升级重贴原消息。配置写入、运行客户端加载与自动hook执行分开验证。

## 三态连续推进与主动反馈

统一执行 [MAC任务连续性](https://github.com/lzhs1995/multi-agent-collaboration/blob/main/references/task-continuity.md)。
Codex及原双Claude正常时分工、ACK、回传和核收及时进行；Claude真实失效时，
有界原会话重试后由Codex接续，健康的另一Claude继续工作；Codex失效时原双Claude
在同任务内协商CLAIM范围、产物和合并负责人，继续计划。整个任务按需最多2子agent，
核对parent/child/task标识及主agent已读的返回结果，不能把spawn成功当完成。

可重试API错误最多3次独立终态尝试，至少间隔60秒且遵守更长Retry-After；成功重置。
不强制空等300秒，独立核值和候选修订立即继续。busy、queued、无回复、socket缺失
和旧错误重读都不是API失败。认证/计费单独诊断，不盲目重试。实际模式由共享
`scripts/collaboration_continuity.py`结合固定任务/原参与者及哈希证据生成；不另建论文身份库。

新持续任务必须原executor登记 `--continuing --reservation-inquiries --proactive-hook`。
共享Stop hook核原身份和授权后要求继续工作，或运行原 `executor_reask.py run --max-seconds 60`；
仍WAITING_REPLY就续办。新proactive授权允许预留期STATUS，旧登记维持原合同。
收到主管实际reply后原executor读取完整正文、exact-SHA consume并执行指示。
询问到达主管不等于主管已答复；不得仅因收到native回执就永久停问。原输入未确认时
只核原次并继续文件询问，不重复粘贴callback。文件scheduler不代表唤醒模型。
用户停止、授权撤销、任务完成均有效；未登记任务/子agent不受此Stop约束。

API故障下原agent可能仍占共享文件或资源；先明确单写者边界，不能从超时推导释放。
独立候选可继续。Codex SOLO标solo_self_review；双Claude互核标peer_review，
不冒充原主管验收。恢复后立即交回checkpoint、冻结产物、未决nonce和资源事实，
不重做已接受审轮，不重放原任务，不替换原会话。共享工程反馈统一送维护者
surface1000020040，由其检验、合并、发布，业务session只交证据并继续本职任务。

通用实现归 `multi-agent-collaboration`。论文任务包只附研究 profile、完整清单、保护路径、文档适配器精确 SHA、当前模式与任务 checkpoint，不把论文判断硬编码进通用协作工具。

### 场景三WIP上限与共享0.4.61

每位作者最多2包已冻结提交、尚未完成对方互核的成果。以精确包SHA和互核结果SHA
记账；独立复算已冻结、通知收到或询问轮数都不表示互核闭合。到上限先互核、
预登记后续CLAIM/计划但不执行，或运行原授权60秒询问。恢复时已有超额包不作废，
先排空再开作者新包。对方互核完成释放此工作预算，但科学接受仍归原论文主管。

共享[0.4.61](https://github.com/lzhs1995/multi-agent-collaboration/blob/v0.4.61/references/release-0.4.61.md)
沿原文件协议处理有界大记录读取、provider熔断、原executor显式继任登记和单调
work-checkpoint。安装不迁移旧episode；同surface换主管thread须原executor精确计划
登记，旧callback、pending和共享资源归属不转移。自报进展与主管接受分列。
isMeta反馈、工具结果、排队附件和API包装不算原通知native收件；raw行末SHA和
canonical正文SHA各自核验。无需在论文仓复制hook、求派器或身份库。

新工单区分acceptance、progress_path和final_output；只有output时它只指终稿，
进度写独立后缀路径。已消费/回调绑定的成果保持冻结，后到修订另存新后缀并列
前版SHA。派单前核工具链和实际磁盘，缺工具或rc127标NOT_RUN。等待期间用原
60秒runner，返回后先读原会话输入和文件上下文；queued_command不冒充原生收到。
mailbox若引用已直派任务，在独立投递清单附evidence-only duplicate_of_native_marker
及原attempt/pack SHA，此信息不自行派单或授去重权限。缺control socket与压缩
期间pending如实记录，沿原控制器零输入复核；有限等待不授权重贴或换会话。

具体分工、双向Enter后核收和回调停止条件见[以研究进展衡量协作效率](efficient-collaboration.md)。
已核收回调的收尾通知不需要另一轮ACK；修通信不自动成为executor的后续业务。

双 agent 必须有当前任务的真实握手、独立 nonce、报告和回调哈希。旧章节 DONE 不能证明新 skill 工程的参与。

资源按申请 → 授予 → 使用 → 排空 → 释放。共享 SQLite 队列让调度者退出后仍可恢复，真实 OS 锁保护调用和交接。过期租约不自动授予别人，先核对原进程、pending 和 lock。

Word/Zotero 使用 `word-zotero` 资源：释放原生操作窗口时需原始回执证明 documents=0、windows=0、无模态、Zotero currentDoc/currentWindow=false、无 pending，且锁可实取释放。`-1743` 时文档数必须记 UNKNOWN；不能以 AX 零窗口推导零文档。未知状态可协调诊断，不能据此授予下一次文档写入。

NLM 独立使用账号资源。只有原网络请求确实终态、子进程回收和 transport 可实取释放，才归窗。本地审读回答不占租约；服务端终态未知即隔离，不能用本地进程结束代替。所有租约与恢复说明留在任务目录，不写入公开 skill 示例。

多任务 NLM 调度遵循 [并发能力与自动调度](nlm-concurrency-and-scheduling.md)：执行者 READY 后即时消费，归还通知不作为下一批的聊天确认门禁。已授权的固定后续题可自动轮转；发现范围失效时暂停相关候选。Claude 故障后的 Codex 接管沿同一队列、原请求身份和实际资源状态继续，不新建另一套账号并发槽，也不重发已送出的请求。

## 协调者交接与已完成成果

用户已授权协作和推举继任者时，协调者退出后由现存会话明确一个继任者并记录交接，不因等不到旧会话 ACK 停住全部任务。继任者复用原账号队列、预算、请求身份和真实资源状态，先收原在途请求；不能仅凭旧协调者进程消失清票或开第二套调度。资源协调者更换不意味着章节 executor 更换，后者仍遵循原会话保留规则。

经验交流按 workspace/surface UUID 找原会话，数字 ref 仅作当前显示。消息发送或权限请求被中断时，先核接收端实际记录；没有确认不要声称已交流，也不要无条件重发。等待回复时推进本地复查与可审阅修改稿；不得让其他会话代绕本会话的执行权限。

轻量经验交流一次给出待核的具体条目和已有证据路径，不要求每方重新包装整套日志。记录消息已投递、接收端排队、已阅读和实际反馈的区别；将已验证内容先反馈给正在交付的章节。原会话因模型服务故障暂不可回复时，可以据已有原证据继续本地裁决，但将本轮未确认的意见显式保留，不把旧同意或当前静默充作新共识。资源协调者、实际网络执行者与章节内容作者分别署名，持有归还回执不自动授予内容审校通过。

已完成的论文、PPT、逐字稿与音频先用当前文件哈希复核，再消费原审校、视觉或解码证据。将可复用经验写入 skill 时，通用流程和章节私有证据分开；同事原任务的 DONE 不能冒充本次修改审阅。认证/传输恢复参照 [专门规则](nlm-auth-recovery.md)，音频完成条件参照 [音频验收](nlm-audio-overview.md)。

## 继任记录与可变导航

继任记录保留 parent task/phase、当前 task/phase、旧新 session 与 UUID、授权引用、已读日志前缀的字节数/SHA，以及继续、只复用、尚未授权的范围。既有协作 harness 的身份/恢复/availability 负责执行准入；论文 skill 消费其真实回执，不另建并行身份库。

冻结成果按完整文件哈希核；追加日志按已读前缀核；可变 HANDOFF/索引按当时冻结快照及明确 supersedes 关系核。旧回执指向的导航后来更新时，保存对应原 SHA 的快照并另记后继，不改写旧回执、不按 mtime 猜最终版。旧阶段“音频尚无”的事实与后继“音频完成”各自成立；前一阶段完成不授予新统稿完成。找不到对应快照是证据缺失，不能放宽哈希要求。

投递消费保留 request/delivery ID、目标 UUID、消息哈希、transport 状态、接收端观察及内容接受的独立回执。`UNCONFIRMED` 与消息排队可以同时存在；可见不等于已读，已读不等于审阅通过。沿 `cmux_bridge` 的既有分类器与回执接续，禁止因返回 75 就重复任务，也不把迟到旧阶段 callback 当成新阶段写入许可。

普通握手与状态消息也必须绑定可见的稳定 marker，不能只有任务与完成回调才记录投递。协作工具新源码将普通消息写入 message-dispatch-v1；排队或不确定时只用原 marker 做只读核验，不重新粘贴。任务下发、回调和普通消息共用接收端锁，防止两个发送者同时操作同一输入框。发送后 hook 独立核对原记录、完整正文、观察哈希与当前身份，不能仅凭 Enter 返回成功。

论文任务复用已绑定的安装版本与原次控制器。源码测试、GitHub CI、隔离安装、运行客户端加载、实际双向投递分别记账；更新本文不表示现役客户端已升级。原执行者失效时按既有授权继续本地文件整理，不把通信维护扩大为重估模型或改写论文。
