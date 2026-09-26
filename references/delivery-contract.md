# 派生交付文件的离线完整性契约

`scripts/delivery_audit.py` 核对当前任务的受控母稿、PPTX、notes、逐字稿、来源和外部验收回执。它不修改 `workflow.py` 的论文审校契约，也不替代原生应用、NLM 或逐页视觉检查。

```bash
python3 scripts/delivery_audit.py --input /absolute/run/delivery-contract.json
python3 scripts/delivery_audit.py --input /absolute/run/delivery-contract.json --output /absolute/run/new-integrity-report.json
```

通过退出 `0`，结果为 `INTEGRITY_VERIFIED`；缺失、类型错误、内容或身份漂移退出 `2`。报告输出必须是尚不存在的绝对路径，避免覆盖正文、输入或旧证据。没有当前任务的显式契约就不要启用交付 hook；历史章节不会因安装工具自动增加验收要求。

## 范围与状态

- `binding_mode: chapter` 适用于单章/指定章节演示，不要求全论文冻结。
- `binding_mode: final_thesis` 只用于用户要求与最终统稿绑定的交付，增加最终稿冻结和逐来源定位映射。
- 两种模式均按当前任务契约核已要求的 PPTX、其原生 PDF、逐字稿 DOCX、其原生 PDF、内容审校及视觉回执。此 v1 不校验音频，也不自动调用任何应用。
- 输出仅表示文件、内容及回执之间的完整性一致。它没有独立证明回执作者的身份、实际执行、审校正确性或研究结论真伪。`mode: real` 是外部证据声明，不能由填一行 JSON 取代原始操作记录。

所有文件引用 `REF` 均为：

```json
{"path": "/absolute/file.ext", "sha256": "64个小写十六进制字符"}
```

工具实际打开文件重算 SHA256。别把 `source_id`、语义标签、页数、文件名或同事的 DONE 当成文件引用。复制到交付路径的文件允许复用原回执，但原路径与新路径都须存在且重算哈希相同；任务、来源 ID 和范围仍分别核对。路径别名不能使内容漂移通过。

## 契约与一份受控母稿

顶层 JSON 必备字段：

```text
schema_version: 1
contract_kind: "derivative_delivery"
task_id: 非空当前任务 ID
binding_mode: "chapter" 或 "final_thesis"
master: REF
sources: [{id: 非空唯一文件 ID, file: REF}, ...]
required_review_rounds: 整数，至少 2，取当前已授权完成条件
review_receipt: REF
artifacts:
  pptx: {file: REF, pdf: REF, native_receipt: REF, visual_receipt: REF}
  speaker_docx: {file: REF, pdf: REF, native_receipt: REF, visual_receipt: REF}
```

母稿是单独冻结的 JSON：

```json
{
  "schema_version": 1,
  "task_id": "example-task",
  "speaker_prefix": ["逐字稿"],
  "speaker_auxiliary": {},
  "slides": [
    {
      "id": "s1",
      "status": "active",
      "blocks": [
        {"kind": "text", "paragraphs": ["研究问题", "本页简述"]},
        {"kind": "table", "rows": [[["表头一"], ["表头二"]], [["单元格第一段", "第二段"], ["另一单元格"]]]}
      ],
      "speech": ["我先介绍研究问题。", "接下来说明研究边界。"],
      "speaker_heading": "第1页 研究问题",
      "sources": [{"id": "front-document", "locator": "物理第5页，1.2节"}]
    },
    {"id": "historical-slide", "status": "archived"}
  ]
}
```

`sources` 中的 ID 必须在顶层来源表解析到存在且哈希匹配的文件，每个 active 页须有非空定位。母稿顺序中的 active 条目构成实际页序；archived 条目保留历史但不参与生成或核验的预期内容。旧内容混入任何现代页、notes 或逐字稿都会造成差异。

支持三种内容块：

| 块 | 精确比较内容 |
|---|---|
| `text` | 一个文字形状内的有序段落字符串，保留空段、Tab、换行 |
| `table` | 有序行 → 单元格 → 段落字符串，保留空格及单元格边界 |
| `image` | `{"kind":"image","sha256":"..."}`，图片 ZIP 部件实际字节哈希 |

PPT 顺序由 `presentation.xml` 的 `sldIdLst` 和 relationship 解析，不按 `slide1.xml` 等文件名排序。文字形状和表格按 slide XML 创建/叠放顺序核对，组内递归；此顺序不自动推断读者视觉阅读顺序。notes 的 body 段落必须与每页 `speech` 完全一致，普通备注文字不能落在未声明形状里；标准页码/日期/页眉页脚占位符不算 speech。

逐字稿正文必须等于：`speaker_prefix`，然后逐页的 `speaker_heading` 与 `speech`。不做去空格、同义改写或句子排序。含文字的页眉、页脚、脚注、尾注须在 `speaker_auxiliary` 用实际部件路径逐段声明，例如 `{"word/footer1.xml": ["答辩逐字稿"]}`。v1 拒绝逐字稿正文中的表格、修订、绘图及嵌入替代内容；不要静默遗漏。

母稿可以按实际需要声明 `boundaries`。没有该字段的旧章节契约不增加此项要求；声明后每条必须包含：

```text
id: 唯一边界 ID
source: {id: 已固定来源 ID, locator: 母稿中实际来源定位}
estimand / time_window / unit / risk_set / tested_status / interpretation_limit:
  分别为非空的实际估计对象、时间窗、单位、风险集/分母、检验状态及解释限制
applies_to:
  - slide_id: 受影响的 active 页 ID
    blocks_excerpts: [需逐字保留在文字/表格中的短语, ...]
    speech_excerpts: [需逐字保留在 speech 中的短语, ...]
```

每个应用位置至少声明一个非空短语；两个数组均显式提供，允许其中一个为空。每个短语须完整存在于对应渠道的一段文字或一个表格单元格段落中，不能跨单元格拼接以假装保留。来源定位须属于该页，归档页不可冒充覆盖。内容审校回执还须 `boundary_ids` 完整列出这些 ID 并绑定相同母稿。改变分母、年份或未检验等限制会造成短语缺失或母稿绑定失效；本工具不判断某段学术结论是否应有更多边界，声明范围由真实学术审读负责。

## 外部回执

v1 回执都须以 REF 固定，包含下列公共字段：

```text
receipt_schema: "delivery-receipt-v1"
kind: 下述明确种类
task_id: 当前任务 ID
mode: "real"
status: "PASS"
producer: 实际核验者/执行者标识
created_at: 含时区的 ISO 8601 时间
evidence: [REF, ...]，真实原始证据，非空
```

历史原生/视觉/审校文件可保持原字节。在当前任务已有核验事实后，建立上述薄回执，把原证据固定在 `evidence`；禁止根据旧 `PASS` 字样自动转换、给未知终态预填成功或编造回执。时间用于记录来源，不以“文件刚生成”代替版本身份判断。

**原生导出** `kind: native_export` 还须有：

```text
backend: "powerpoint_native" 或 "word_native"
input: 当前 PPTX/DOCX 的 REF
output: 对应原生 PDF 的 REF
page_count: 正整数
operation_status: "COMPLETE"
resource_status: "RELEASED"
release_evidence: REF
```

PPT 原生页数必须等于实际解析的 active 页数。PDF 除哈希外检查 `%PDF-版本号` 文件头，不能用任意 JSON 冒充；此检查不等于 PDF 全结构有效性。PDF 页数本身由外部原生/视觉证据承担；本脚本不解析 PDF 页面，也不核应用窗口状态。`release_evidence` 固定实际归还原件，脚本不把普通文件存在称为已经归还。

**视觉核验** `kind: visual_review` 还须有 `pdf: REF`、`page_count` 与逐页 `pages`。每页：

```text
page: 从 1 开始的连续整数
status: "PASS"
method: "inspected" 或 "pixel_identical"
evidence: [REF, ...]
```

使用 `pixel_identical` 还须有 `previous_pdf: REF`、`previous_page` 正整数、`comparison_evidence: REF`。同工具/尺寸/分辨率条件和实际像素相等须由外部比较原件证明，本脚本只核这些证据的绑定。第一页、末页及中间任何页均不得只以总数代替覆盖。

**内容审校** `kind: content_review` 还须有 `master: REF`、与契约对应的 `sources` 和 `rounds`。每轮：

```text
id: 唯一轮 ID
topics: ["theory_methods", "data_figures", "structure", "language", "citations", "format"]
new_required_changes: 整数 0
unresolved_required_changes: 整数 0
content_scope_gaps: []
evidence: [REF, ...]
```

轮数必须等于已明确的 `required_review_rounds`；布尔 `false/true` 不可充当 `0/1`。本脚本消费已完成审读与本地裁决的真实回执，不从回执计数推断会话独立、引用有效、六主题实际覆盖，也不发查询或扩题；这些按既有 NLM 契约独立验收并保留原件。

## 最终统稿绑定

仅 `final_thesis` 模式增加：

```text
final_thesis: {file: REF, freeze_receipt: REF}
mapping_receipt: REF
```

`freeze_receipt` 是 `kind: final_thesis_freeze` 的当前任务绑定回执，含 `file: REF`；其 `evidence` 指向作者真实最终冻结记录，而不是临时目录或尚不存在的计划路径。作者冻结任务 ID 与 PPT 任务 ID 不同时，原件保持原身份，在当前绑定回执中明示核收者和证据，不能改写作者原记录。

`mapping_receipt` 是 `kind: final_source_mapping`，含 `master: REF`、`final_thesis: REF`、`freeze_receipt: REF`、`sources` 及 `mappings`。每个 active 页的每个来源定位对应且只对应一行：

```text
slide_id / source_id / source_locator: 与母稿三者逐字一致
final_locator: 实际最终稿页码/表图/段落定位
disposition: "equivalent" 或 "updated"
evidence: [REF, ...]
```

语义等价和实际修改正确性来自外部核验，不由字符串匹配推断。最终稿发生内容改变时，按实际影响更新母稿、来源及审校证据；不要把旧章节页码冒充统稿页码。

## 边界和验证

v1 不检查字体、字号、颜色、越界、合并单元格几何、图中箭头语义、动画、演讲时长或音频。图片只核字节；PPT 版式/母版继承的显示效果交给原生 PDF 与视觉回执。图表对象、OLE 等非表格 graphicFrame 不受支持并拒绝通过；不可把这些对象当成无文字而跳过。不能把 `INTEGRITY_VERIFIED` 写成“所有科学与视觉检查已由本工具完成”。

`tests/test_delivery_audit.py` 提供可运行的合成契约、OOXML 和回执：真实 CLI 正反出口、哈希不变、关系页序、命名空间别名、同字节副本、表值/notes/旧稿混入、来源缺失或漂移、布尔计数、错任务/旧格式回执、缺页、覆盖缺口及最终映射。合成 fixture 仅验证工具行为，绝不是实际论文或 NLM 信用。
