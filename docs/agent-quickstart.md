# Agent quickstart

[English overview](../README.md) · [繁體中文總覽](../README.zh-TW.md)

Use this guide to start a bounded manuscript review from the source you actually checked out. It does not configure an agent, grant application access, authenticate NotebookLM, or dispatch a collaborator. For online review, NotebookLM requires a Google account and the selected manuscript sources are uploaded to Google; confirm that the material may be uploaded before submitting it. See [Security and data handling](../SECURITY.md).

## 1. Read the workflow and identify the task

Read [SKILL.md](../SKILL.md), [the evidence loops](../references/dual-loop-workflow.md), and the task's existing checkpoint before doing new work. Treat an old task's pinned source, controller, attempts, budget and receipts as its original contract; an updated README does not migrate it.

For a new task, record:

- The requested deliverable and review scope, including chapters, appendices and tail sections.
- The original manuscript and accepted sources, their absolute paths and SHA-256 hashes.
- The complete source version used by the agent, its resolved `SKILL.md` path and hash.
- The actual executor and permitted tools, the private output directory, and ownership of shared writes.
- Existing Word/Zotero resource rules and the NotebookLM account, source binding, query budget and transport, if online review is in scope.

Do not infer missing authorization or account readiness from an example. A useful initial instruction is:

> Read `/absolute/thesis-refiner/SKILL.md` and the existing task checkpoint. Work on a new derivative of `/absolute/private-task/manuscript.docx`. Inventory the agreed chapters, tables, figures, formulas, references and appendices; map claims to their evidence. Report missing inputs before submitting online requests. Keep original assets and in-flight task bindings unchanged. Save exact source fingerprints, review evidence, local decisions and a resumable checkpoint in `/absolute/private-task/review-v1/`.

Replace these paths and scope with the real task. This example authorizes no external message or remote operation by itself.

## 2. Check local tools first

The base offline checks require Python 3.10+, Node.js 18+, and the packages in [requirements-test.txt](../requirements-test.txt). For a reproducible trial, use a new checkout pinned to the reviewed runtime baseline below. This old commit does not include this new guide or the SDK candidate; keep the guide open separately. Do not switch an existing task checkout underneath a running controller:

```bash
git clone https://github.com/lzhs1995/thesis-refiner.git thesis-refiner-runtime
cd thesis-refiner-runtime
git checkout --detach c2e14fc86aa51a1efa6cee98fc0c802a02850bba
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-test.txt
python -B -m unittest discover -s tests -v
python -B scripts/install.py --help
```

Use `.venv\Scripts\Activate.ps1` for PowerShell activation. Install dependencies into an isolated environment. The tests use synthetic evidence, including loopback TLS; they submit no NotebookLM queries. Cross-repository tests need a compatible sibling collaboration checkout or an explicit `COLLABORATION_BROKER=/absolute/source/scripts/resource_broker.py`. A skipped integration test is not a pass. Native Word, statistical software, and live account transports require separate actual validation.

The public [installer](../scripts/install.py) is optional. A preview is read-only; `--apply` requires POSIX file locks and fresh, separate, non-symlinked version paths outside the source tree. It copies maintained skill files, not the complete documentation/test/assets tree. It does not select a running client's release or configure dependencies, hooks, credentials or MCP. Preserve old pinned installations; use the [version-installation contract](../references/runtime-validation.md#版本安装与在途任务).

## 3. Prepare one controlled manuscript version

Trace each substantive empirical claim to its data, sample, estimator, output and scope. Check units, denominators, spouse or respondent roles, grouping definitions and uncertainty. Use existing accepted evidence where it covers the exact unchanged object; do not rerun an entire analysis just to recreate a record.

Back up the research originals separately and generate a named working copy for changes. Inspect each tool's output path and write behavior; do not assume all tools refuse overwrites. Native Word/Zotero operations and PDF export follow their actual domain-tool and resource contracts; [OfficeCLI Academic Word](https://github.com/lzhs1995/officecli-word-revision) is the companion document project. Its native tools must be installed and validated separately. Independently check affected rendered pages, citations, fields and file integrity. Offline evidence work can proceed in parallel where it does not touch a shared native resource; multiple open documents do not demonstrate safe concurrent native writers.

## 4. Submit bounded, source-bound NotebookLM review

Read [review and budgets](../references/nlm-review-and-budget.md). This repository's shared-account runtime needs the [Multi-Agent Collaboration](https://github.com/lzhs1995/multi-agent-collaboration) resource broker; reading the rules and doing standalone local checks does not require installing that project. Confirm the exact PDF/source, actual notebook, account policy, transport and remaining task budget. Existing transport failures or unknown outcomes remain attached to their original attempts; do not switch SDKs to resend them.

Use the six agreed themes: theory/methods, data/figures, structure, language/terminology, citations, and formatting. Keep the full intended scope while asking for concise, deduplicated output. Do not embed the expected verdict or require a minimum number of faults. Record actual scope evidence and explicit gaps; a prompt's requested scope is not proof that the model completed it.

Inspect the complete answer and native references. Where a citation says `<cited_table>`, inspect its structured table object as well. Source identifiers, text, table cells, ranges and answer anchors are separate evidence. Uploaded source text, an answer's self-report, successful HTTP, and a terminal receipt do not alone establish full review coverage or factual correctness.

## 5. Adjudicate and repeat on the same version

For each finding, record its exact statement, manuscript location, supporting native references, local evidence and disposition. Keep real corrections, false reports, correctly retained content and unknowns separate. Check typography, clipping and page appearance against the actual PDF; do not adopt extracted formula symbols as a visual verdict.

Formal final acceptance requires the agreed two complete review rounds on the same frozen PDF/source in independent conversations, with confirmed issues resolved and no new locally confirmed issues. A necessary supplement closes only its evidenced gap. Changed manuscript content requires a new version binding and renewed affected checks; old review credit does not silently transfer. Keep the original answers, including rejected ones.

## 6. Deliver an honest checkpoint

Use [delivery validation](../references/delivery-contract.md) and [manifest/link checks](../references/delivery-manifest.md) for the actual requested assets. Report separately what is scientifically accepted, mechanically verified, visually checked, released from shared resources, or still unknown. Include exact file paths and hashes, issue dispositions, original receipts, open boundaries and the next executable step.

Do not turn task-specific logs into public fixtures. A completed offline suite, installed files, configured hooks, actual client loading and a successful live task are distinct states.

## Branch-specific capabilities

The trial above uses the reviewed public runtime baseline. Herdr collaboration and the SDK draft are separate development work. Read [development status](development-status.md) for their exact revisions and verified limits before selecting either. Installing one of the three companion projects does not install or activate the others, and new code does not migrate an existing task.
