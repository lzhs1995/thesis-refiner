# Checkpoint 与回执

所有文件引用使用绝对 `path` 和 SHA-256。公开示例只用合成内容；实际 checkpoint 留在任务目录。`tests/test_workflow.py` 提供完整可执行合成案例。

顶层字段：`schema_version`、`task_id`、`original`、`nodes`、`dispositions`、`required_documents`、`documents`、`review_provenance`。`original` 使用 `inventory` 的完整输出，审计时会重新提取初稿核对。`dispositions` 以原条目 ID 为键，记录 `action`、`reason`、`category`、`claim_ids`、`review_evidence`、逐个 `numeric_dispositions`；移动或删去实证内容还要 `retained_evidence_destination`。

节点字段：`id`、`kind`、`depends_on`、`artifacts`。claim 另外记录 `sample_fingerprint`、`same_sample_as`、`verification`、必要的 `provenance_gap` / `accepted_partial`；数值比较记录 storage_precision、display_rounding、tolerance、ci_method、draws_requested、draws_saved。真正全程复现须另有 `reproduction_receipt`，不能从文件存在推导。

每个 claim 必须声明 `empirical_kind=descriptive|estimated`，并用 `lineage`
分别指向可达的 data、cleaning、variables、sample、output 节点；estimated
还需 model 节点。找到一个输出文件不能代表整条链已核对。历史环节确实缺失时，
用 `lineage_gaps[环节]` 记录 reason、哈希 evidence 和 accepted=true，同时
保留 accepted_partial；不得声称 full_reproduction。每段多项主张的语义拆分
仍需 agent 实际审读，清单和 schema 不能替代这项判断。

每份 document 单独记录：

| 字段 | 要求 |
|---|---|
| `docx` / `pdf` | 冻结文件的引用与哈希 |
| `scope_ids` | 必审范围，包括最后一节附录，不能只列早期目录 |
| `gates` | native、format、visual、pdf_fonts，含 Zotero 时还需 zotero；各回执 mode=real、status=PASS，绑定所检文件 |
| `gates.export` | 同时绑定 docx_sha256 / pdf_sha256，backend=word_native；声明页数或分片时还需由实际 PDF 读取的 page_count |
| `source` 或 `sources` | 已上传来源 ID、READY 原始回执和精确 PDF 哈希 |
| `rounds` | 至少最近连续两轮；每轮由多个主题/分片 query 构成 |

长文分片：保留母本 PDF；每个来源记录 child PDF、母本哈希、原页码列表和 `equivalence_receipt`（text_and_visual_equivalent=true）。回执必须绑定实际 parent_page_count 和 child_page_count；页映射须唯一递增、位于 1..母本页数且条数等于分片实际页数。没有全文来源时，分片必须覆盖母本全部页码；存在全文来源也不能豁免单个补充分片的有效性。多个 family 可以各有独立 conversation。两轮的 conversation 集合必须不相交；不把逻辑 round ID 假扮成平台 conversation ID。

每个 query 记录 request_id、source_id/source_ids、conversation_id、原始 answer 文件、实际执行 receipt 和覆盖矩阵。receipt 必须有 mode=real、status=COMPLETE、exit_code=0、document_sha256、source_id(s)、round_id、真实 conversation_id 和 answer_sha256。保留平台 references 中的 source_id、citation_number、cited_text，使用它们与 PDF 原文核对；不能凭生成的编号假装原生引用。

覆盖矩阵逐条列 scope_id × topic，topic 为 theory_methods、data_figures、structure、language、citations、format。每条有 locator、citation_ids 和本地覆盖核对证据。矩阵代表 agent 已核对覆盖，不能仅因问句提到了该范围就填满。issue 保留 id、original_text、locator、disposition、local_evidence；真实新错误或未决意见阻止通过，误报需要原文反证。

`hooks/a5-termination-auditor.js` 只审计显式 `workflow_checkpoint` 或 `THESIS_REFINER_CHECKPOINT` 绑定的任务。将其用于完成边界，不用不完整 checkpoint 阻断每一次中间工具操作。编排器和 CLI 在没有完整回执时均返回非零，不能用叙述性 DONE 代替。

机器格式见 [checkpoint schema](../schemas/checkpoint.schema.json) 和
[实证 schema](../schemas/empirical-trace.schema.json)。schema 检查类型和字段；
动态文件身份、实际回执与完成条件仍由脚本核验。旧的开发样例若缺少 lineage、
分片实测页数或真实来源身份，需要补证后再审；不得补造字段来继承通过状态。

## 数字去向与完整重跑的绑定

numeric_dispositions 与原稿数字逐项按位置对应。旧字符串形式只能引用该条目 claim_ids 内的有效 claim。结构化形式用 mention 保留原字符串、kind=empirical 和 claim_id；年份或编号等非实证数字用 kind=nonempirical、reason 和哈希 evidence。空值、未知主张、数值对不上或无证据分类均被拒。

声明 full_reproduction=true 的 claim 必须引用 empirical_contract（也可显式使用顶层合同）与同一个 reproduction_receipt。合同及执行回执都绑定当前 task_id/claim_ids，输入与输出覆盖该主张的 lineage，执行脚本属于可达的清洗/变量/模型节点；sample、session、job、脚本和输入输出哈希再由 portable empirical checker 核验。旧的只有 PASS/end_to_end 标记的回执不能证明完整重跑。未完整重跑的既有稿件仍可按真实证据及明确 partial 完成文稿交付，无须自动重估。
