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
