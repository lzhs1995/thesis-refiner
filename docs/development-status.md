# Development status

[English overview](../README.md) · [繁體中文總覽](../README.zh-TW.md)

This is a dated snapshot, recorded on **2026-11-10**. It separates the public runtime baseline, development work, and actual validation. A later branch or PR update does not change the source pinned by an existing task.

## Public runtime baseline

The installation/trial instructions pin [`c2e14fc86aa51a1efa6cee98fc0c802a02850bba`](https://github.com/lzhs1995/thesis-refiner/commit/c2e14fc86aa51a1efa6cee98fc0c802a02850bba), the reviewed `main` baseline used to prepare this documentation. Its `SKILL.md` declares `2026.10.24.1`.

That checkout reproduces the existing runtime source. It does not contain this new documentation edition, its assets, or the SDK candidate below. Keep the published guide open separately when following the pinned trial. Installing the baseline does not install a development branch or upgrade an active controller.

## Herdr development line

The separate [feature/nested-chapter-workflow-s40-20261104 branch](https://github.com/lzhs1995/thesis-refiner/tree/feature/nested-chapter-workflow-s40-20261104) contains additional collaboration work. The target checked during SDK release preparation was `60cad4925f2a745303981c203f28db2453e8c9b8`. This is a development target, not an instruction to merge its parent history into `main`.

## Optional SDK candidate

[Draft PR #60](https://github.com/lzhs1995/thesis-refiner/pull/60) proposes an opt-in task-bound SDK entry against the Herdr feature branch:

- Candidate commit: [`940a9b10e9724640632b105e86112df11df0be09`](https://github.com/lzhs1995/thesis-refiner/commit/940a9b10e9724640632b105e86112df11df0be09).
- Separately selected upstream SDKs: Jacob `0.16.1` and Teng `0.8.6`.
- Retained controls: existing account queue and locks, explicit budget and source binding, one query POST, a 240-second total limit and 90-second idle limit.
- Status at preparation: pushed for review; not merged, installed or adopted through global navigation by that preparation. No global MCP configuration switch was performed.

The recorded six-query observation used one dedicated synthetic notebook and an explicitly confirmed persistent conversation, serially. All six HTTP streams completed with gzip termination. Five answers passed source and semantic acceptance; one answer contained correct prose but no native references and was rejected. Those outcomes are separate from the transport result. No repeat query was made merely to obtain six passing answers.

The candidate's exact-head CI passed, and the reusable wrapper has offline guard tests, actual local preparation, import checks, and replay of the six original streams. This supports the bounded SDK adaptation. It does **not** establish the new wrapper's complete live lifecycle, the full public CLI/MCP interface, independent model performance, concurrent execution, or a guarantee that future answers cite sources. Synthetic tests do not count as manuscript review.

Jacob's request capture temporarily replaces a module-global `_httpx` object and restores it afterward. It is **not thread-safe**: use one request per dedicated process, not a shared threaded MCP server. Two same-name MCP executables remain separate provider installations; finding either through `PATH` is not a reliable provider selection.

A release must bind actual executor, account, notebook, accepted source, confirmed conversation, Python and dependency paths. The prepared dependency evidence records exact installed file hashes, distribution metadata and source URLs. It does not invent an original wheel hash or signature that was not recorded. The skill installer does not bundle these SDK environments.

## Adoption and existing tasks

Review the chosen revision and its compatible dependencies before installation. Confirm installed files, client loading, tool access and actual execution separately. Preserve original source paths, controllers, attempts and unknown results for in-flight tasks; a candidate release never authorizes replaying an uncertain request through a new SDK.

For users starting from `main`, use the [agent quickstart](agent-quickstart.md). The branch and PR links above expose development work for review, not a claim that all clients are already configured.
