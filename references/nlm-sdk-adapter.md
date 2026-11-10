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

The present candidate targets Jacob 0.16.1 and Teng 0.8.6. The official request
builders and parsers are used; the public CLI/MCP retry/auth/cache machinery is
not invoked. This scope must be reported accurately in validation. The Jacob
builder is intercepted before its buffered HTTP send. Teng uses its official
streaming request builder. Both use a single query POST, archived decoded raw
bytes, gzip/deflate negotiation, decoder-trailer checks, a 90-second idle limit
and a 240-second total limit. Unknown/multiple content encodings are rejected.
There is no POST replay, SDK fallback, browser login or automatic auth refresh.

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
