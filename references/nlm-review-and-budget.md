# NLM 审查与账号级预算

先做本地可机械验证的字号、编号、表格数值、域结构、PDF 字体/裁切和来源指纹检查。NLM 聚焦长文的结构、内容、逻辑、术语语言及跨页一致性；返回意见须本地裁决。不能把“低幻觉”理解为不会误报。

默认六类审查：理论/方法、数据图文、结构、术语语法、引文、格式。三包方案（前两类合并、结构语言合并、引文格式合并）只有在真实对照证明覆盖与问题召回均无损后才启用；模拟、离线重排回答不证明查询合并有效。对照不足仍用六类，绝不靠降低覆盖节省额度。长附录按实际检索缺口拆分，尾节单独列入矩阵。

正式复核先冻结排版与 PDF。相同 PDF/source 两轮复用，使用独立 conversation；不是每轮重传一次。同主题的定向补问绑定原问题与来源，避免重复做开放扫描。保留所有原回答，即便最终全部判误报。判断“无新问题”依据本地裁决后的新确认问题数，不能篡改回答成空列表。

## 覆盖、检出与正确保留分别记账

完整 source 全文不证明每次回答审读了全文。原生 `references[].cited_text`
只证明暴露的引用内容；缺少某页引用不证明服务端内部从未检索该页。对答案明确
标为“未能核实”的范围，以及本地清单中没有对应审读证据的实质内容，保留覆盖缺口。
不能因回答声称“已检查全部页码”，或把实质页误称为占位说明，就记为完整覆盖。

问题检出须同时有错误原文或定位、回答明确指出的问题性质及本地裁决。仅在引用中
出现错误文字、数字关键词相同，或正确验证了局部算术，都不等于识别了跨页冲突。
良性对照分别记录“未被误报”和“经明确审读后正确保留”；零误报不能替代后者。

查询方案对照按每轮完整方案的回答联合计算召回，不要求每个单主题问题检出所有
其他主题的错误。同时列出各主题结果、共同漏检、末节覆盖和良性对照。数值条件
全部达到后，仍需独立裁定范围覆盖；计分程序不得仅凭召回和零误报自动启用三包。
保留六主题也不能免除缺口核查，后续按真实页码/章节锚点做定向复核或来源分片。

## 配额事实与策略

截至 2026-09-19，Google [新版公告](https://support.google.com/gemininotebook/answer/17670842?hl=en) 说明从 2026-09-02 起采用 compute-based limits，受 prompt、模型、功能和对话长度影响，5 小时刷新并有每周上限。[旧套餐表](https://support.google.com/gemininotebook/answer/16213268?hl=en) 仍保留部分每日次数说明；[中文指南](https://notebooklm-guide.com/zh/notebooklm-system-limits-benchmarks/) 仅作补充。账号是否已经迁移、剩余额度和可恢复时间以当前 UI/响应为准。

- regime 为 legacy_daily_count、compute_weekly 或 unknown；记录观测来源、时间、时区和原提示。不猜午夜刷新，不以“500次/24小时”作为通用默认。
- 同账号默认一个网络请求在途；不同 notebook、target 和 workspace 共用预算。短批最多两个 query 或 10 分钟，当前请求安全结束再交窗；本实现每个调用独立归窗，排队任务优先。
- 可把已批准短批的串行调用、终态核验、排空和归还通知接成连续执行步骤，避免在网络结束与归窗之间插入离线审读。遇不确定终态立即停止后续调用并按原证据核清；到期本身不是释放证明。分别记录授予、请求结束、实际释放和等待时间。
- 明确任务调用预算，已知可计量额度保留 20% 给最终验收与必要恢复。compute 余量未知时只报告观察到的请求数、耗时和覆盖，不把次数冒充计算单位。每次预算调整保留新观测，不能清掉 UNCERTAIN 请求“恢复余额”。
- 相同账号、notebook、操作、文件版本、轮次、来源和 prompt 去重。相同 PDF 上传可跨轮复用，不能误用其他 notebook 的 upload 回执。
- 空控制帧、超时或进程退出不等于服务端请求结束。UNCERTAIN 会隔离账号并保留资源租约；核对原请求终态及 transport 后才能显式 reconcile。可能已受理的失败不退款。
- 限流账号级暂停。到实际提示时间后只有一个必要审查问题充当恢复探针，失败就保留暂停；不通过登录、换账号、新页或改 default 绕开限额。

## 执行入口

`scripts/nlm_runtime.py` 使用 `multi-agent-collaboration/scripts/resource_broker.py` 的共享队列和 OS 锁。准备私有 binding：账号匿名键、notebook/target、workspace/surface UUID、broker 文件哈希、transport 文件哈希、按 operation 列出的 argv 模板及严格复用标志。`commands` 是已验证 transport 的命令数组，使用 `{notebook_id}`、`{source_ids_csv}`、`{prompt_file}`、`{file}` 等占位；不拼 shell 字符串。

```bash
python3 scripts/nlm_runtime.py configure --account ACCOUNT_KEY --input /absolute/quota-policy.json
python3 scripts/nlm_runtime.py run --binding /absolute/binding.json --input /absolute/query.json
python3 scripts/nlm_runtime.py report --account ACCOUNT_KEY
```

先核查现场 CLI 的 `--version` / `--help`，再固定模板。已观察到 `nlm 0.9.12` 用 `notebook query NOTEBOOK QUESTION`；`notebooklm 0.8.1` 的上传是 `source add CONTENT -n NOTEBOOK --type file`，全文要 `source fulltext SOURCE -n NOTEBOOK --json`（默认文本只显示 2000 字符），没有 copy 命令。文件不存在时可能被当内联文本，因此上传前必须检查存在性与 PDF 签名。不要从一个 CLI 的帮助推导另一个 CLI 的语法。

已绑定 transport 优先于泛用 skill 的自动登录、备用后端或新页面恢复。`NLMUnifiedClient` 明确拒绝未验证的 copy、自动建 notebook 和绕过队列的 batch；备用 CLI 只有单独测量并写入 binding 才可用。通道错误不自动切后端重发。

## 全文输出丢失身份字段

`nlm 0.9.12` 的全文 JSON 可能只有 content/title/source_type/url/char_count，
即使底层 `hizoJc` 响应包含来源 ID。不能把请求中的 ID 填回去冒充服务端回显，
也不能因 CLI exit0 或全文看似相同就撤掉来源检查。

已验证的 transport 可在原请求 fully_received、终态回执和原始响应哈希均核实后，
调用 `scripts/nlm_fulltext.py` 的 `normalize_rpc_fulltext`：从服务端响应提取 ID，
核对请求 ID、完整文本、标题和字符数，并另存归一化结果。保留原 CLI 字节及所有
失败回执；本工具不发请求、不改变预算/租约、不把原 UNCERTAIN 改成 PASS。
notebook 归属来自实际请求绑定，不能声称该响应回显了 notebook ID。
没有可靠原始响应时保持失败并核清；已有可验证全文则离线复用，避免重复上传或读取。
