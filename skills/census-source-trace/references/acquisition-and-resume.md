# Retrieval and continuation through existing tools

## Source location

Use known local files first. For a missing source, follow the host's existing browser or public-data reader: library/database catalogue, exact book/edition, publisher contents, table, then the native export or original page. Record catalogue availability, access entitlement, preview content and export completion separately. Use a known relevant catalogue item to distinguish a non-working search from genuine zero results when the existing source permits it.

Prefer exact indicator, valid region aliases, statistical year and table number. Publication year and census year differ in many books. Record printed versus platform page numbering rather than silently choosing one. Inspect the resulting table to confirm that requested filters took effect.

## Exact reuse

Reuse the original adapter's resource/request identity and byte hashes. In an HTTP adapter that records them, full URL, method, relevant headers and exact body bytes distinguish requests. Do not collapse distinct headers, normalize a signed/query URL, reorder a form body or invent missing historical request fields. For browser downloads, use the original download receipt and terminal state; a changed download directory alone proves neither success nor failure.

Match the receipt to the original file's byte count/SHA-256, verify the business payload, then parse. If the verified cache covers the target, use it without triggering another download. Log actual new requests and actual cache reuses separately. A local cache parse is not a fresh online access test.

For XLS/BIFF, XLSX, HTML, PDF or embedded image tables, choose an existing reader that supports the actual format. Record conversions with their own hashes and parent source. A second reader is an independent processing check, not a second underlying data source.

## Bounded continuation

Use the project's original owner, task/attempt ID, ledger, locks, source aliases, authorization and request/timeout budget. This package does not prescribe a universal retry count or replace these controls. For a new project, establish a finite budget before initiating network work; the example's zero network budget intentionally permits only local inspection.

- Reconcile success, failure, ongoing and unknown outcomes before submitting another action. Do not replay an unknown click/download because its tool timed out.
- Preserve historical failures, source holds and unresolved intents. Moving the output directory does not release a hold or turn a request into a new identity.
- Distinguish loading placeholders, masked values, an authentication challenge, a permission denial and a true empty business result. HTTP 200 alone proves none of those meanings.
- Reuse an authorized authenticated session. Do not log it out to manufacture a relogin test. Use an existing permitted login route only if needed; retain any actual CAPTCHA/MFA requirement.
- Stop the affected source on unresolved access/transport/identity failure under its controls. Continue independent authorized local parsing or other sources where appropriate.
- Recover through the original adapter's supported path. Ledger identity repair, current authentication, successful table retrieval and correct statistical definitions require different evidence. Never recreate a ledger or clear holds to obtain a passing status.

Record the evidence supporting the continuation, the original attempt state, any new action, observed outcome and remaining gap. Preserve original source files and write derivatives separately.
