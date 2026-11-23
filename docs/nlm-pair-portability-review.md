# Pair controller source portability review

Review date: 2026-11-20. Scope: the eleven new pair modules and the changes to
`nlm_contracts.py` and `nlm_sdk_entry.py`, against the repository's PR65 baseline.
This is an independent static source review. The reviewer changed only this
document and did not import or invoke the pair runtime, open an installed
authority/configuration/registry, inspect hooks, use credentials, or send any
network request. Synthetic tests and their results belong to the accompanying
test contribution; this document does not substitute for those results.

**Finding:** no source publication blocker was identified in the reviewed
thirteen files. The code can be published as a bounded, installation-dependent
pair controller. It must not be described as a portable standalone client or a
general concurrency implementation. The boundaries below are part of its
contract, not permissions to relax checks while installing it elsewhere.

## Private data and source closure

The thirteen files contain no fixed personal home directory, account email,
account identifier, session identifier, credential value, proxy IP/port, or
private receipt path found by targeted literal scans and source inspection.
Account/profile/email, executable, SDK roots, broker, source material, receipt
directories and route bindings are supplied through explicitly pinned inputs.
Error output uses types and a small non-secret code allowlist rather than
arbitrary provider exception text.

The literals `s39-original-query-cap-v1`, the three historical-task requirement,
eight prior query identifiers, ten-query cap, US2 route label, and fixed SDK
version basis are public contract identifiers or constraints. They are not
personal data and should not be renamed merely for cosmetic generality: doing
so would break original scope/configuration compatibility. The source-add title
`SDK known-answer fixture 20261110` is a fixed fixture label. This setup path
therefore continues to label its added material as a fixture; it is not a
general document-upload interface.

The complete new dependency set is:

| Module | Role |
|---|---|
| `nlm_pair_budget.py` | Pinned existing runtime, atomic pair admission, task/quota controls |
| `pair_total_budget.py` | Original eight-plus-two scope inside the admission transaction |
| `nlm_pair_identity.py` | Original request key, STARTED row, task/account/operation identity |
| `nlm_pair_locks.py` | Existing lock ownership and inherited file-descriptor validation |
| `nlm_pair_group.py` | Original lease checks, member validation, two bounded child processes |
| `nlm_pair_policy.py` | Installed parent policy and exact complete source pins |
| `nlm_pair_fresh.py` | Fresh scope, explicit history/turn grammar, persistent-ID readback |
| `nlm_pair_http.py` | Raw-read observations around the existing bounded HTTP transport |
| `nlm_pair_setup.py` | Separately bound serial metadata setup operations |
| `nlm_sdk_pair_child.py` | Dedicated original-request transport child |
| `nlm_sdk_pair_parent.py` | Preparation, authorization, shared admission and settlement |

The two existing-file changes are necessary dependencies: `nlm_contracts.py`
rejects UNCERTAIN transport payloads with safe diagnostics, and
`nlm_sdk_entry.py` rejects SDK-tree symlinks while propagating traversal timeouts.
Publishing only the pair child would omit required behavior.

`nlm_pair_budget.py` loads three adjacent modules by fixed SHA-256. All three
currently match the checked repository bytes:

| Module | SHA-256 |
|---|---|
| `nlm_contracts.py` | `d2cbeabdac0f3d91db9753fb649807e9ef3261d4d8dd782bdef2b5695a86c5ee` |
| `workflow.py` | `81a460c94b4537bad21a952989449081904083256e00b7c9e7d979aa8aedfa35` |
| `nlm_runtime.py` | `1fabeb8cda76fbb1d7571642bf993960fb7c878430aa36227c98a1332747bab7` |

These pins make the import intentionally sensitive to future runtime changes.
A future source update needs a reviewed dependency-and-pin update, not a removed
hash check. Importing `nlm_pair_budget` reads and executes these local source
modules; it does not itself construct a budget database or contact the service.
Synthetic tests must still pass explicit temporary budget roots. The inherited
runtime's optional default home-directory state is not appropriate for tests.

## Supported installation boundary

| Requirement | Consequence |
|---|---|
| Python 3.11+ for real SDK entry; `-BE`, without optimization | Repository-wide Python 3.10 offline compatibility does not imply pair runtime support on 3.10 |
| POSIX `fcntl`, `O_NOFOLLOW`, inherited `pass_fds`, process groups and `SIGALRM` | Native Windows execution is unsupported; tests needing these facilities must be skipped or restricted on Windows |
| Complete immutable `release/source/scripts` layout | The installed authority is located at `release/NLM-ROUTE-POLICY-PIN.json`; copying one script or using an arbitrary checkout is not an installed environment |
| Exact source, interpreter and external SDK manifests | A new location or changed bytes require a newly reviewed installation and new-task pins; old in-flight requests retain their original binding |
| Existing shared broker, resources, external locks and budget database | This controller neither installs nor authorizes these resources; `PairBudget` rejects a missing database |
| Existing approved two-query task allocation | Pair admission does not silently allocate a task budget or edit old allocations |
| Fixed US2 domain route and original route verifier | Source publication does not create route authority; the existing route documentation currently limits the live verifier to its macOS/Mihomo binding |
| `httpx` plus HTTP/2 dependencies and separately pinned SDK distributions | `requirements-test.txt` supplies test HTTP dependencies, not authenticated SDK/account setup |

Configuration examples should use visibly non-runnable placeholders and list
the above fields and required evidence. They must not ship an actual account
profile, a real route binding, a real authority file, a private SDK manifest or
an original receipt. Generating a real policy/registry is outside source
publication and remains the existing maintainer's task. In particular, a task
argument cannot replace the installation-owned authority file.

## Behavioral limits that consumers must read

1. The total cap is a fixed continuation contract: exactly three historical
   task IDs, exactly eight original query IDs, and exactly two new queries under
   the new pair task. FAILED and UNCERTAIN prior attempts count; no refunds are
   made. This is an aggregate task authorization cap, not a claim about the
   provider's quota or every unrelated task on the account.
2. Both new requests are booked in one `BEGIN IMMEDIATE` transaction. A partial
   failure rolls the transaction back. Original request identity, a separate
   logical identity check, existing account policy/reserve, pause state and
   explicit allocation remain enforced.
3. Fresh mode means an explicit null request conversation plus pinned source,
   notebook-creation, history and (when present) server-turn evidence. A missing,
   null, malformed or error RPC response is not equivalent to empty history.
   No history is deleted and no old request is resent to create freshness.
4. Both children inherit one parent's existing lock descriptors. Children close
   their duplicates without `LOCK_UN`, so closing one child does not release the
   sibling's open-description lock. Process cleanup and a remote terminal
   response are separate requirements.
5. HTTP measurement timestamps describe raw response-read lifetimes on one
   host's monotonic clock. They include inter-chunk waiting and do not prove
   simultaneous bytes, server computation overlap, or accepted answers.
6. The parent may return a receipt reference even when the aggregate result is
   FAILED or UNCERTAIN. A normal pair `run` CLI exit code of zero is therefore
   not answer acceptance. Consumers must read the returned artifact and the
   original `NETWORK-TERMINAL.json`, then distinguish `RETURN.json` from
   `RECOVERY-NEEDED.json`. A missing terminal stays with its original lease and
   request IDs; it does not authorize retry.
7. `prepare` is not an offline command: it includes the original credential-free
   CONNECT/TLS route check. Offline tests should exercise isolated pure seams
   with synthetic inputs and mocked transports, not call actual `prepare`,
   `run`, setup transport, or account/route discovery.

The pair child retains some ordinary-entry helper definitions for compatibility.
Its actual `transport_pair` path calls `nlm_pair_fresh.config_pair_checked`,
which calls `nlm_sdk_entry.sdk_preflight`. Consequently the reviewed scandir,
symlink-rejection and timeout-propagation update in the ordinary module is used
by the actual pair transport; the older unused helper copy in the child is not
evidence that this execution path bypasses that update.

## Acceptance boundary

This review found no need to weaken budget, identity, route, lock, EOF, cleanup
or original-attempt checks to make the source publishable. Publication still
requires the independent synthetic suite and repository checks. Those checks
should cover the original ten-query cap, replay/mismatched identity, explicit
fresh history, inherited lock ownership, and HTTP error/timeout/EOF behavior.
Passing them establishes offline behavior only. It does not establish a new
installation, current client loading, a new live query, a second parallel pair,
multi-account concurrency, or broad cross-platform support.
