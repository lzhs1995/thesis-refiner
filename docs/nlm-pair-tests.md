# Pair controller offline acceptance

Use Python 3.11+ on POSIX, with the repository's ordinary test dependencies:

```sh
python -m pip install -r requirements-test.txt
python -BE tests/run_pair_offline.py
```

The runner discovers only the four pair test modules. It denies network socket
operations and imports of hook modules. Its only permitted subprocess is the
exact synthetic lock child embedded in the test, using the current interpreter
and a temporary manifest; that child also denies network operations. No SDK
distribution, credential, installed configuration, authority, registry or
original receipt is needed. All budget and queue databases are temporary.
Optional `--report PATH` creates a new JSON result and refuses to overwrite it.

| Module | Behavior exercised |
|---|---|
| `test_nlm_pair_total_budget.py` | Original transaction required; all eight historical attempts count; fixed ten-query scope cannot expand; historical ID tampering rejected; competing atomic bookings yield one winner |
| `test_nlm_pair_budget_locks.py` | Actual pair admission under a synthetic original lease; two slots booked atomically; second-insert quota failure rolls both back; paused accounts, altered tickets, changed/expired authorities and wrong request identities rejected; FAILED/UNCERTAIN attempts are never refunded; inherited lock survives child/parent descriptor closure; separate descriptor and replaced inode rejected |
| `test_nlm_pair_fresh.py` | Exact history and explicit empty-turn grammars; unique successful RPC envelope; timestamp and UUID validation; pinned scope/source/prompt/round; truncated/duplicate HTTP evidence rejected; one persistent-ID readback; metadata failure never repeats the query or invents a persistent ID; original deadline remains fixed |
| `test_nlm_pair_http.py` | Mock HTTPX streams, raw-read interval and EOF evidence; distinct transport per operation; no second query send or retry after connection error; HTTP 429, truncated compression, idle timeout and expired total deadline retain their original failure evidence |

The Python 3.10 repository job skips these four modules because the pair entry
requires 3.11+. A dedicated Ubuntu CI job runs the strict runner on 3.11 and
3.12 and rejects skips. Native Windows is not supported by the pair controller.

The tests were adapted from prior synthetic tests. Personal SDK paths, frozen
machine manifests and original real-response fixtures were removed. Pure source
equality assertions were replaced with behavior checks. The RPC data and account,
notebook, source and ticket identifiers are synthetic. Fresh-history fixtures
use the reserved `example.invalid` domain. HTTP tests retain the public service
origin required by the transport's allowlist, with an injected mock transport
and network audit guard; they perform no DNS, TLS or service request.

This suite verifies offline controller behavior. It does not claim installation,
live route approval, real SDK authentication, a new NLM query, a second live
parallel pair, server execution overlap or multi-account support. Read
`nlm-pair-portability-review.md` for installation and completion boundaries.
