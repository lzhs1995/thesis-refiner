# 从研究执行到交付：可复用经验与边界

用于复盘已有论文工作、维护工具或接续交付。经验工程不重新开启已完成的模型、NLM审查、Office或音频生成。旧任务保留原入口与回执，新工具用合成数据验证。

| 情况 | 有效处理 | 不能据此声称 |
|---|---|---|
| 旧缓存或运行根失效 | 核归档映射、输入SHA、真实源根；必要时以新身份建立后处理入口 | symlink可读就是根绑定程序可运行；缓存复现就是全模型重估 |
| R结果表行数异常 | 用模型、项、组别等复合键核唯一性、完整行集和逐格映射；保留失败表 | 行数相同就是正确；完整p向量可放入一行记录 |
| NLM源查重命中 | 复用相同PDF SHA对应的真实source ID，核原状态与全文 | 旧上传超时就是未上传，必须重新注册 |
| 原答引文、目录或旧稿错配 | 保留原答和原引；同次检索片段单列来源，再做本地裁决 | 检索片段是修正后的原编号引文；改写文字是原文 |
| 引用增加bytes字段 | 核同一字面路径、SHA，bytes存在时核真实大小 | 可忽略不同路径、不同哈希或错误大小 |
| cmux返回75/UNCONFIRMED | 按原UUID和marker核原界面、队列和后续回执 | 一定未发送、对方已同意或任务已完成 |
| 已验包但聊天路径拼错 | 从冻结清单角色生成绝对链接，核存在、后缀和字节 | ZIP通过保证手写链接正确 |

## 实证组装与复现

`scripts/empirical_trace.py` checker 1.1保持schema 1兼容。表可以声明`row_keys: ["model_id", "term"]`、完整`expected_rows: [["model_a", "exposure"], ["model_b", "exposure"]]`、可选`expected_n: 2`，以及`expected_cell_rows: [{"key": ["model_a", "exposure"], "values": {"n": "42"}}]`。

期望行集来自审核过的当前模型规格，不使用某章固定行数。单键旧合同继续使用`row_key`及字典形式`expected_cells`；两种键声明不能混用。检查器不重估模型、不修改数据、不调整容差。

相同缓存后处理在原生R与独立Rscript得到一致输出，是两个实际入口的后处理复现证据。两者仍读同一缓存，不能视为独立数据或全链条模型重估。分别记录输入、代码、依赖、原执行ID、输出身份、样本单位、精度、区间方法及限制。

## 文件身份与复制关系

`scripts/evidence_refs.py`的`same_identity()`核两个真实文件的哈希和可选大小，再比较**字面绝对路径+SHA256**。元数据增加不再触发字典全等的误拒绝；原回执不改写，重复归还不重复计数。不同路径的同字节复制须有单独来源映射。交付检查的`same_ref()`按其既有复制合同允许同字节成品副本；不能把这种语义用于原请求身份判断。

## 归档后的可用性

文件可读、字节正确、规范根绑定通过、实际可运行分别记录。若入口绑定canonical root或依赖祖先目录，保留其真实运行根并外置映射，可另存独立APFS副本；不修改历史校验器伪造兼容。

空间去重另属用户明确授权的归档任务，需要冻结的逐路径清单和无在写句柄证据。只读父目录阻止已批准的逐件操作时，只对本人拥有的确切目录临时增加owner-write，在finally恢复mode/mtime；核ACL、用户扩展属性、创建时间和内容，系统provenance/ctime变化另列。此经验不授予通用清权限、清环境或删除权限。独立COW副本与新硬链接的后续写入行为不同。

## 工具边界与版本

- R执行、描述表和配对抽样：[R工具集合](https://github.com/lzhs1995/clauder-rstudio-workbench)。
- 可见Stata、内存和重放：[Stata skill](https://github.com/lzhs1995/stata-workbench-shared-session-skill)，运行时另由[插件仓库](https://github.com/lzhs1995/stata-workbench-shared-session)管理。
- 身份、输入类型及投递：[协作工具](https://github.com/lzhs1995/multi-agent-collaboration)。
- 字段、格式及原生渲染：[OfficeCLI](https://github.com/lzhs1995/officecli-word-revision)。
- 科学链、原答裁决及[清单交付链接](delivery-manifest.md)：本skill。

源代码、安装、实际进程加载版本分开核验。旧开放PR可能落后于已发布补丁；合入时逐项比较。运行中任务继续固定解释器和私有依赖；新安装不触发应用或agent重启。研究原文、私有路径、账号绑定和原始回执只存本地经验索引，公开仓库仅含通用规则、代码和合成例。
