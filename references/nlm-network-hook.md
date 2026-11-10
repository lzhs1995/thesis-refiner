# Mandatory NotebookLM network boundary

Use the task's expressly approved domain route. Missing, changed or unproved
route evidence must stop a new NLM call before credentials or query are sent.
Do not substitute a proxy port, an exit label or a historical successful query
for the approved route. Keep machine node names, configuration paths and
credentials in the local policy, never in this public repository.

`scripts/nlm_network_guard.py` is a PreToolUse command hook for the observed
Claude/Codex JSON protocol. It recognizes direct NLM MCP names, NLM CLI/SDK/HTTP
execution, shell wrappers, literal nested `functions.exec` commands, and bounded
local wrapper sources. Direct NLM MCP operations (including remote list/status)
are denied: their actual server transport has not been bound to this policy.
Direct CLI/SDK scripts are denied too. Use the exact pinned SDK `prepare`/`run`
entry; a direct `transport` invocation is not an alternative.

The hook does no network I/O. For a permitted entry it validates the registered
policy, Python, code pins, task route and proxy. The entry repeats actor/source/
account/queue validation and obtains fresh route evidence at preparation,
admission and immediately before sending. See [SDK binding](nlm-sdk-adapter.md).
Policy identity, live TLS chain and the provider's service-region acceptance
are three different facts. Neither a hook allow nor a TLS observation is an NLM
query PASS.

## Installation contract

The maintainer creates a private policy using
[the schema example](../adapters/nlm-network-policy.example.json). `code_pins`
contains every `source/scripts/*.py`, sorted by path; each reference is an exact
`path`, `bytes`, `sha256` object. `required_route_label` explains the machine's
required chain and terminal. The pinned `route_binding` supplies the actual
process/configuration/socket/listener/node checks; a label alone is insufficient.

Place `NLM-ROUTE-POLICY-PIN.json` beside the release's `source` directory:

```json
{
  "schema": "nlm-network-policy-authority-v1",
  "policy": {"path": "/absolute/private-policy/NLM-ROUTE-POLICY.json", "bytes": 123, "sha256": "ACTUAL_SHA256"}
}
```

This installation-owned authority is derived from the entry's physical path.
There is no task flag or environment override. New tasks must carry the exact
same policy reference as `route_policy`; absent authority or a self-selected
policy fails. Protect the release, authority, policy and client registration
with the maintainer's normal file controls. This is not a security boundary
against an actor able to rewrite those trusted files or disable client hooks.

Add this command under `PreToolUse`, matcher `*`, preserving all existing hooks:

```text
/absolute/pinned/python -BE /absolute/release/source/scripts/nlm_network_guard.py --policy /absolute/private-policy/NLM-ROUTE-POLICY.json --policy-sha256 ACTUAL_SHA256
```

Use a client timeout above the guard's 4-second local deadline (for example 6
seconds). Refresh any client-specific trusted hook hash using that client's
supported mechanism. Do not replace another hook or claim registration proves
loading. Test an actual client negative event (an NLM command must be refused
without invoking it) and an ordinary read event. Also record direct process
tests separately; they alone do not prove the client ran its hook.

Input accepts `tool_name`/`toolName`/`tool`/`name` and
`tool_input`/`toolInput`/`input`/`arguments`. A permitted event prints `{}` and
exits 0. A denial exits 2, prints a fixed reason to stderr and emits
`hookSpecificOutput` with `hookEventName: PreToolUse`,
`permissionDecision: deny`, and the reason. No raw tool payload or credential is
printed. Invalid events fail closed. Both clients must actually honor the deny
protocol; until that is verified, report installed versus loaded separately.

## Local recovery and limitations

Known read commands such as `cat`, safe `rg`, and line-range `sed` can inspect
receipts, source and status without loading policy or networking. An exact,
reviewed offline parser or original local-settlement command may be listed in
`offline_commands`: `{ "argv": ["absolute", "literal", "arguments"],
"network": "none", "files": ["exact path/bytes/sha256 references"] }`.
List the script and its executable dependencies. No wildcard, argument suffix,
network retry, query or alternate controller is permitted by that exception.
These entries are maintainer attestations about reviewed local code, not a
sandbox that can infer absence of network effects. Existing UNKNOWN receipts,
budgets, and original attempts remain unchanged by installing the guard.

The classifier is intentionally conservative for recognized NLM executions;
compound shell forms, environment substitution and unresolved NLM wrappers are
denied. It is not an OS firewall, interpreter sandbox or proof about arbitrary
obfuscated binaries, remote machines, already-running services, disabled hooks,
or a compromised host. Do not describe it as blocking every possible packet.
Keep raw MCP/CLI transports disabled at this tool boundary until their actual
route can be bound; installation does not make those integrations verified.

Rollback restores a previously recorded client hook configuration only under a
new authorized maintenance action. A route failure never automatically removes
the hook, falls back to a different node, retries a POST, or modifies an old
task's pins. A new policy/release requires a new task preparation.

## Explicit legacy compatibility

A separately installed release may expose `legacy-run --config ABS --request
ABS` through the same pinned SDK entry. The request argument is a late-bound
`nlm-legacy-run-spec-v1`, not a replacement query prompt. `legacy-transport` is
internal to the original broker and is always denied at the tool boundary.
The new mode does not import the SDK budget/runtime or allocate a new budget.
It validates the approved task contract, original prepared metadata, source
request and new ROOT adoption, then retains the task's original execute, submit
lock, FIFO, Budget.admit, run_bound, receipt and settlement paths.

Install the new release and authority alongside the old release. Do not edit an
old release, authority or policy to add the compatibility code: complete code
pins would invalidate already prepared SDK tasks. Use one registered guard with
an installation-pinned `nlm-network-entry-registry-v1` containing entries of:

```json
{
  "entry": {"path": "/release/source/scripts/nlm_sdk_entry.py", "bytes": 123, "sha256": "ENTRY_SHA"},
  "authority": {"path": "/release/NLM-ROUTE-POLICY-PIN.json", "bytes": 123, "sha256": "AUTHORITY_SHA"},
  "policy": {"path": "/private/policy.json", "bytes": 123, "sha256": "POLICY_SHA"},
  "modes": ["legacy-run"]
}
```

Old entries retain exactly `modes: ["prepare", "run"]` and their old pins. Each
entry path is unique and its authority must be beside its own source directory.
After matching the literal entry path, verify only that selected authority,
policy and full code set. A missing new task contract must not disable unrelated
old SDK tasks. Registry pinning and descriptor uniqueness still apply globally.
Legacy entries cannot carry `offline_argv` or `offline_commands`. If preserving
an existing SDK offline command, its exact argv must be listed in that registry
item's `offline_argv` and remain an exact reviewed item in its original policy.

Register a single guard command with `--registry ABS --registry-sha256 SHA`.
Adding a second wildcard guard alongside the old one does not work: the old
guard would still reject the new entry. Preserve other unrelated hooks. The new
entry also reads its installation-owned `NLM-GUARD-REGISTRY-PIN.json` beside
`source`, with schema `nlm-network-entry-registry-authority-v1` and a `registry`
reference. It explicitly applies the same-release `event_check` to its actual
interpreter argv. Neither a CLI flag nor task config selects this authority.
Record this explicit process check separately from native automatic hook loading.

The new policy's `legacy_contracts` allowlists exact static task-contract pins.
A contract has schema `nlm-legacy-task-contract-v1`, status
`APPROVED_STATIC_LEGACY_CONTRACT`, original task/account/notebook, budget and
resource roots, query budget, submit lock and limits, source-request pin,
authorization, ROOT implementation scope, predecessor preparation and stopped
keys, plus approved runtime/controller/adapter/bridge and executable artifacts.
This is an installation review of named code, not an arbitrary task callback or
permission to choose another runtime.

Store `broker_module` as the canonical physical pin and
`original_controller_alias` as the original binding's exact reference. The
legacy config and binding must retain that alias unchanged; it must resolve
to the approved physical bytes. Do not rewrite an old binding or weaken the
common canonical-pin checker to accommodate a symlink.

The private bridge exposes only:

* `parent_adapter(cfg)` returning the approved task adapter.
* `private_budget(adapter, cfg, run_spec, runtime)` returning a subclass with
  the original `Budget.admit` code; the named semantic exception remains the
  task's separately reviewed responsibility.
* `configure_child(adapter, cfg, before_send, *, validate_operation)` returning the original transport
  module, calling `before_send(host)` at each actual query or bounded original
  lookup send, after the original Clock starts. It must call the original main
  in the broker's direct child process, preserving PID=PGID and lease checks.
  Its original main calls `validate_operation` only after starting the original
  Clock; do not duplicate the legacy validation outside that child deadline.

Legacy local validation has a separately approved `local_validation_seconds`
integer in the static contract, strictly positive and at most 120. Read it only
after the installation policy approves that contract. It is not the SDK's
30-second local preflight and cannot be enlarged by task CFG. Route checks keep
their existing 20/30-second bounds, and the original child Clock, absolute query
deadline and connect deadline remain unchanged.
The original execute function's independent validator is bounded separately;
do not wrap its subsequent network query in the local-validation timer. A pure
local original result-check that never starts a child requires no send gate.
A started child returning success still must have passed its actual send gate;
there is no general lookup exemption and no request sent merely to satisfy a
gate counter.

Keep preparation acyclic: static contract → legacy transport config → public
CFG → binding → plan/prepared/operation/key → ROOT decision → RUN_SPEC. Neither
CFG nor its artifact closure may point back to future keys or outputs. The
internal child command pins public CFG and its SHA; the child recovers its
actual operation from the original receipt request. ROOT explicitly adopts the
new key while retaining unsubmitted predecessors and original failures.

The entry repeats installation-policy and fresh route checks before original
admission, and the child repeats them immediately before sending. It reuses
the existing route checker. No prechecked boolean, old list result or offline
exception replaces these gates. Gate failure means no new send; UNKNOWN,
charges and earlier attempts remain untouched. Fixed-chain TLS still does not
prove service-region acceptance, query completion or review credit.
