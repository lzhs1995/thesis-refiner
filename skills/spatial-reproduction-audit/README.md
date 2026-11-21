# Spatial Reproduction Audit

![Original spatial audit mark](assets/logo.svg)

**繁體中文**：把既有空間研究的來源、樣本、權重、腳本與結果連成可核查的證據鏈。先辨別點估計、模擬均值與自訂公式，再按原契約復用腳本，分別交代實際執行、歷史吻合及科學限制。這是可直接閱讀的技能候選；沒有附帶資料或通用模型執行器。

**English**: Audit the provenance, units, weights, scripts and results of an existing spatial study. Distinguish point estimates, simulation summaries and custom formulas before comparison. Reuse the project's execution contract and report replay, historical agreement and scientific limitations separately. This is an instruction package without bundled data or a generic model runner.

## Use with an agent

Read [SKILL.md](SKILL.md), then supply your own project binding outside this package using [the JSON example](examples/project.example.json). Its paths and values are illustrative and require replacement; it does not run anything.

> Read spatial-reproduction-audit/SKILL.md and my project.json. Audit the named saved results into the binding's audit directory. Preserve historical-only components and unresolved items; execute only replays explicitly included in my task.

Codex can read [AGENTS.md](AGENTS.md); Claude Code can read [CLAUDE.md](CLAUDE.md); Gemini-compatible clients can read [GEMINI.md](GEMINI.md). Each points to the same instructions. Other agents can open SKILL.md directly. Explicit file reading works without installation; automatic discovery depends on the host and has not been tested here.

The logo is original SVG artwork. Packaging checks, publication, installation and actual cross-agent execution are separate acceptance steps. No public release or model-runtime acceptance is asserted by this candidate.
