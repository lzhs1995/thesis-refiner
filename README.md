# Thesis Refiner / 论文精炼助手

Evidence-led empirical manuscript refinement with interleaved local analysis tracing and NotebookLM review. The agent performs the work; deterministic tools check provenance, frozen versions, review coverage and completion receipts.

Read [SKILL.md](SKILL.md) for the workflow. Python 3.10+ and Node.js 18+ are sufficient for offline checks. Native Word and statistical execution remain in their domain tools. Shared NLM execution requires the `multi-agent-collaboration` resource broker and an explicitly pinned existing transport; this project does not launch browsers or authenticate accounts.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/install.py --canonical /absolute/skills/thesis-refiner --codex-adapter /absolute/codex/skills/thesis-refiner
# Review the dry-run plan, then apply that maintained-file overlay:
python3 scripts/install.py --canonical /absolute/skills/thesis-refiner --codex-adapter /absolute/codex/skills/thesis-refiner --apply
```

Installation overlays only maintained files, backs up every replaced file and writes a hash manifest. It preserves existing research inputs and legacy private resources. It does not change hooks globally, restart Word/RStudio, configure an account or publish a manuscript. Bind the completion hook to a task checkpoint explicitly when required.

Public tests contain synthetic data. Real manuscripts, account identifiers, CDP targets, raw executor transcripts and machine-specific evidence belong in private task directories. `simulation` output never counts as an accepted paper or NLM round.

The public JS/runtime integration suite uses a sibling `multi-agent-collaboration`
checkout or `COLLABORATION_BROKER=/absolute/scripts/resource_broker.py`. Its
subprocess transport is synthetic and makes no network calls. Missing that
dependency skips only the integration suite, which must pass separately before
installing a combined runtime. Domain-native acceptance and live NLM benchmark
results are recorded separately from unit tests.
