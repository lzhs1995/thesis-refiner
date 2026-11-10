# Explicit SDK candidate transport

For new requests, use `nlm_sdk_adapter_v3.py`. It includes v2's pinned h2, hpack and
hyperframe imports before budget admission, and supplies the existing runtime's
citation map for Teng while preserving its full reference objects. The original
adapter remains intact for its original attempts. Pin/copy those three optional
HTTP/2 dependencies into the new isolated entry; SDK installation alone did not
include them. Missing dependencies must fail locally before network admission.
Version 3 serializes SDK Enum fields to their original values while retaining
all structured-document and reference fields. Actual Teng answers contained
BlockStyle enums that `dataclasses.asdict` alone could not serialize.

`scripts/nlm_sdk_adapter.py` supplies a narrow HTTP boundary for separately pinned
Jacob and Teng installations. It does not select/install an SDK, obtain a login,
allocate an account budget, release an UNKNOWN request, or change a controller.
The task runner must use the existing `nlm_runtime` and account resource broker.

Bind an absolute SDK directory and record its full source manifest, the Python
executable, adapter, task runner, input, prompt, account, notebook, source IDs,
client provider and actual executor. Do not select either same-name
`notebooklm-mcp` through PATH. Installing this candidate does not switch a running
MCP client or an in-flight request.

Every new SDK entry must also enforce the domain route gate in
[connection recovery](nlm-connection-recovery.md). A local proxy port, a node
label or a prior successful query does not prove the route used now. Bind the
approved machine-specific route privately; never copy node names, credentials
or proxy configuration into this public skill.

The present candidate targets Jacob 0.16.1 and Teng 0.8.6. The official request
builders and parsers are used; the public CLI/MCP retry/auth/cache machinery is
not invoked. This scope must be reported accurately in validation. The Jacob
builder is intercepted before its buffered HTTP send. Teng uses its official
streaming request builder. Both use a single query POST, archived decoded raw
bytes, gzip/deflate negotiation, decoder-trailer checks and a 90-second idle limit.
The new entry's parent bounds its entire admitted child to 240 seconds, including
startup checks, imports, HTTP, parsing and cleanup; the HTTP segment receives
only the remaining time. Unknown/multiple content encodings are rejected.
There is no POST replay, SDK fallback, browser login or automatic auth refresh.

Jacob interception temporarily replaces the conversation module's global
`_httpx` object and restores it in `finally`. It is **not thread-safe** and may
only run in a dedicated process handling one request. Do not embed it in a
threaded MCP server or share its process with another SDK query. The new task
entry below rejects an already threaded caller and uses one broker child per
request; this is a serial execution restriction, not a concurrency guarantee.

Preserve every parser-exposed reference field and the original full raw body.
Keep cited text, structured tables, source ranges, fragment ranges, answer
anchors and UTF-16 units separate. Raw preservation is not proof the SDK
exposes every future server field. A marked final answer outranks a longer
intermediate answer. Thinking text, empty answers and unterminated streams do
not establish COMPLETE.

The stream ID is not used as a persistent conversation ID. A fresh request is
allowed only in a newly created task-owned notebook; later requests must bind
the actual persistent conversation. For a fresh request, read it once with
`hPTbtc` in that exclusive notebook and require one unique ID. For subsequent
explicitly bound requests, reuse the pinned prior confirmation; another listing
is unnecessary and must not downgrade an already complete answer. That separately
named read-only RPC is not a
second query POST. An ambiguous/failed readback retains the parsed answer and
UNKNOWN; it does not authorize replay. Never use Teng `ask --new` to remove chat
history. Do not infer a fresh conversation just from `conversation_id=None`.

The candidate adds separately named `notebook_create` and `source_text_add`
response contracts. Existing `source_add` PDF validation and all old operations
remain unchanged. Creation binds a task-unique client namespace until a real
server notebook ID is returned. A successful text upload still needs a separate
fulltext check before a query. It makes no PDF visual/extraction guarantee.

Online acceptance requires actual query receipts and independent expected-answer
scores, in addition to offline transport tests. Two same-account SDK processes
do not demonstrate independent resources. Preserve the account lock and serial
budget admission; concurrent requests require a separately verified isolation
contract. A transport failure is distinct from a wrong semantic answer.

On UNKNOWN, retain the original request, receipt, budget usage and lease. Any
local abandonment must follow the original owner protocol and cannot claim
remote cancellation. A new SDK version or route never permits blind replay.

The six-query 2026-11-10 task observation used one dedicated synthetic notebook
and one explicitly confirmed persistent conversation, serially: three Jacob
requests followed by three Teng requests. Every query HTTP stream reached 200
and gzip EOF. Five passed source/semantic acceptance; one Teng answer was
factually correct but had no references and was rejected. This is evidence for
the bounded low-level SDK seam, not a complete CLI/MCP integration test, independent
model comparison, concurrency test, or a guarantee that future answers cite
sources. Keep transport, source validation and semantic acceptance separate.

## Prepare a new task

`scripts/nlm_sdk_entry.py` is the reusable opt-in entry. Copy
[`adapters/nlm-sdk-task.example.json`](../adapters/nlm-sdk-task.example.json),
[`adapters/nlm-sdk-source.example.json`](../adapters/nlm-sdk-source.example.json)
and [`adapters/nlm-sdk-query.example.json`](../adapters/nlm-sdk-query.example.json)
into the new task. Replace placeholders with the actual executor environment,
authorized task budget, account, notebook, source acceptance evidence and a prior
COMPLETE receipt confirming the persistent conversation. Never copy another
task's IDs or claim environment checks are native actor authentication. Notebook
creation, upload/fulltext acceptance and first conversation confirmation remain
the original separately bound workflow; this entry does not perform them.

Every file reference is its absolute resolved `path`, exact `bytes` and SHA-256.
Bind Python 3.11+ and run with `-BE`, without optimization. `sdk_manifest` uses
schema `nlm-sdk-environment-v1`: `import_roots` in precedence order, `files` for
every file in those roots, `versions` for the selected distributions,
and `sources` containing each distribution's version, official upstream URL and
pinned METADATA. An installed tree hash identifies the actual local bytes; it
does not claim a wheel download hash or signature that was not recorded. Include
both isolated SDK roots and exact h2/hpack/hyperframe dependencies. Missing,
changed or extra files fail before budget admission. Any `.pyc`, `.pyo` or
`__pycache__` directory is refused, not deleted: `-B` alone does not prevent
reading bytecode. A checked-source import loader also compiles the pinned Python
source directly, so a cache added after preflight cannot replace it. Newly added
sourceless bytecode and unpinned modules in these roots are rejected. These external SDK trees
remain explicit dependencies; the skill installer does not bundle or install them.

From the complete release's source directory (replace absolute task paths):

```bash
rtk proxy /opt/homebrew/bin/python3.14 -BE scripts/nlm_sdk_entry.py prepare --config /absolute/new-task/task-input.json --output-dir /absolute/new-task/prepared
rtk proxy /opt/homebrew/bin/python3.14 -BE scripts/nlm_sdk_entry.py run --config /absolute/new-task/prepared/CONFIG.json --request /absolute/new-task/query.json
```

`prepare` performs local identity, source, dependency and existing account-policy
checks with a 30-second local preflight timer; it freezes code/config pins without
query, origin HTTP or budget writes. The required private `route_binding` uses
`nlm-fixed-proxy-route-v1`: exact proxy URL and two NotebookLM hosts, pinned local
proxy configuration, listener object, process PID/birth/command, control socket
identity, and the fixed terminal/dialer nodes with hashes of their private
configuration objects. `scope_acceptance` explicitly records the evidence
boundary when the core lacks an independent listener-mapping API. This binding
contains no credential values; the pinned private proxy configuration remains
in its original location.

The gate checks the actual TCP listener and Unix control socket belong to the
same unchanged process, its command selects the pinned configuration, and its
runtime proxy chain has no selector. One bounded credential-free CONNECT/TLS
observation then matches the live local connection by source port, destination
host and inbound port, requiring the approved terminal node in its actual
`chains`. Fixed dialers from runtime node checks are reported separately if the
connection API omits them. It sends zero origin HTTP and zero query POSTs and
closes immediately. This proves a short observation window, not a permanent
route or Google's acceptance of the exit region. Missing or mismatched evidence
fails before sending; no route, selector or service is altered.
This implementation supports a macOS local HTTP listener and a Mihomo Unix
control socket with a fixed proxy/dialer chain. Other platforms, shared selectors
or missing control evidence require a separately reviewed binding; there is no
silent port-only fallback.

`prepare`, pre-admission and immediately pre-send repeat this same route gate.
The TLS segment has a 15-second ceiling; existing 30-second preflight and
240-second admitted-child deadlines still apply. A changed process or route
requires a new named binding, never editing an old attempt's pins. `run`
admits through the original account broker, existing external locks and explicit
task budget. Its dedicated parent replaces only the broker's child-wait method
for this process; queue, grant, budget, receipt and release rules are unchanged.
The parent deadline is 240 seconds from broker-run entry through child exit,
including prelaunch and all child phases. Child preflight has a 30-second timer;
close, auth-file readback and receipt cleanup have a 5-second timer inside the
same parent deadline. At the hard deadline, only this newly created process group
receives TERM, then KILL after up to 5 seconds, followed by at most 5 seconds of
drain observation. If drain cannot be proven, retain UNKNOWN; the parent does not
wait forever or claim remote cancellation. A timeout returns non-success even
if the child previously printed a plausible answer. The original budget remains
charged and the lease stays with its original owner for reconciliation.
On a parent deadline or child phase timeout, `SDK-DEADLINE-OUTPUT.json` in the original receipt directory
preserves captured stdout/stderr bytes as base64 with hashes and the original
ticket binding (a partial prefix is labelled when drain is unproven). This local
evidence write has its own 5-second timer. Only a fixed UNKNOWN signal reaches
the legacy classifier: quota, 429 or auth words in timed-out output cannot become
remote-terminal proof. Normal non-timeout quota handling remains unchanged.
The dedicated child uses one POST and a 90-second idle limit,
disables auth refresh/retry and reuses the confirmed conversation without
an extra listing. An unchanged request remains deduplicated by the runtime.
Do not edit prepared pins to recover or upgrade an old attempt. A changed SDK or
scope requires a named new task binding after original settlement. Failed source
validation preserves `PARSED-ANSWER.json`; local settlement still requires the
original owner's established protocol and never implies remote cancellation.

This reusable wrapper has offline guard/recorded-stream validation. The six live
observations above exercised the same adapters via the original task controller,
not this wrapper's complete live lifecycle or the public CLI/MCP facade. Keep
that remaining validation boundary visible when choosing a new task entry.
