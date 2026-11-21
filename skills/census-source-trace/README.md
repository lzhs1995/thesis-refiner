<p align="center"><img src="assets/logo.svg" width="112" alt="Census Source Trace logo"></p>

# Census Source Trace

[繁體中文](README.zh-TW.md)

A portable instruction skill for finding census and statistical-yearbook tables, reusing verified downloads, and preserving the source and statistical meaning of candidate observations.

It distills an existing acquisition workflow. Bring your already available browser, download adapter and spreadsheet/PDF readers. No crawler, credential manager, live database connector or model-fitting code is bundled.

## Use

1. Read [SKILL.md](SKILL.md) in your agent and give it the current project's task/checkpoint plus the requested tables.
2. Adapt [task.example.json](examples/task.example.json) in a private project folder. The example is synthetic and offline; its fields are instructions, not an executable API.
3. Ask the agent to reuse verified source files, register missing evidence, and use your existing authorized tools only where acquisition is requested.

Example prompt:

> Use census-source-trace. Read my project checkpoint and source register. For the specified census year and regions, locate household-count tables, reuse verified downloads, and return candidate records with page/cell, unit, population and boundary evidence. Keep unresolved definitions explicit.

| Client | Entry |
| --- | --- |
| Codex | [SKILL.md](SKILL.md); [AGENTS.md](AGENTS.md) for repository context |
| Claude Code | [CLAUDE.md](CLAUDE.md), which imports the shared entry |
| Gemini or another agent | [GEMINI.md](GEMINI.md), then the shared entry and skill |

Load these files explicitly if your client does not discover this folder. Merge a pointer into an existing project entry if needed; do not overwrite its rules. Installation locations and tool APIs belong to the host client. Providing entry files is not evidence that a client loaded or executed them.

## Output and boundaries

The [record contract](references/record-contract.md) separates source identity, original values, transformations and acceptance. Candidate data, formally adopted research data and fitted models remain distinct. Real credentials, local paths, source files, receipts and project bindings stay outside the distributable folder.

Historical evidence includes real public-statistics, CNKI and EPS retrieval pilots and saved cache checks. Those pilots do not establish automatic relogin, general online failure recovery or stable multi-database end-to-end operation. See [validation boundaries](references/validation-boundaries.md) for the precise scope.

This is a review candidate. One Codex agent explicitly loaded the skill and used the included offline synthetic fixtures: it checked the declared fields, recorded fixture hashes, and marked the observation `needs_source`; no real table was obtained and no observation was accepted or formally adopted. The fixtures already describe missing evidence, so this was not a blind test. Automatic discovery, Claude/Gemini runtime, live acquisition, relogin and general failure recovery remain unverified. This exercise does not establish publication. The logo is an original SVG drawn for this package; it uses no external image or font.
