---
name: spatial-reproduction-audit
description: Audit an existing spatial research reproduction chain, reconcile inputs and derived statistics, and reuse authorized project scripts with explicit evidence limits. Use for spatial result reproduction or manuscript numeric checks.
---

# Spatial Reproduction Audit

Audit the supplied project contract, inputs, scripts, saved results and manuscript claims. This skill is a portable instruction set; it ships no model runner, data or validated model implementation.

## Start from the project binding

1. Read the user's selected contract and project binding. Use [project.example.json](examples/project.example.json) as a field guide, not an executable configuration. Resolve relative paths against the binding's declared base directory. Keep private bindings outside this skill package.
2. Identify each component as `audit_existing`, `authorized_replay`, or `historical_only`. Retain explicit exemptions and unresolved scientific items. A historical software audit does not authorize installation or re-estimation. Reuse the original execution owner, completed results and pending attempt records.
3. Pin the selected source, code, environment and result files by path, byte count and SHA-256. Follow named references first; widen discovery only to resolve a specific missing input. Record superseding corrections alongside preserved originals.

## Check before comparing or replaying

Read [reproduction-checks.md](references/reproduction-checks.md) for the comparison procedure. Establish unit membership and order, variable definitions, coordinate/weight specification, full-precision estimands, tolerance and randomness before interpreting any difference.

Use the existing script's actual invocation contract: entry file, working directory, environment variables, arguments, input snapshots and output directory. Read it before invocation; a historical top-level script is not automatically a generic CLI. Do not remove completion guards or resubmit a running/completed attempt to obtain a fresh receipt. If a new authorized replay needs adaptation, preserve the original and use a separately named project sandbox with the exact change recorded. Do not create a new runner framework.

A new dataset requires a new binding and fresh checks of definitions, samples, weights, transformations and model specification. Prior success establishes only the prior project/run. Keep acquired candidates separate from adopted model inputs; reuse saved acquisition receipts rather than repeating successful downloads.

## Deliver evidence with bounded claims

Produce these small artifacts in the project's specified audit output directory:

- `lineage.csv`: `claim_id,source_path,source_sha256,locator,code_path,output_path,evidence_kind`.
- `comparison.csv`: `claim_id,unit_or_term,estimand,expected,observed,abs_error,tolerance_rule,status,note`.
- `audit.json`: requested scope, executed operations, source/environment pins, sample and weight checks, per-component evidence grade, exemptions, unresolved items and artifact pins.

Use `PASS`, `DIFFERENT`, `UNVERIFIED`, or `NOT_APPLICABLE` per comparison; never replace unknowns with zeros. Report execution completion, historical numeric agreement and scientific adequacy separately. Manuscript edits must preserve the estimate's units, uncertainty and causal limits. Installation, actual client reading, model execution and UI verification each need their own evidence.

For direct use in Codex, Claude Code or another agent, see [README.md](README.md). This candidate's validation describes packaging only; it does not certify a general model execution product.
