---
name: census-source-trace
description: Retrieve and trace census or statistical-yearbook tables using existing authorized tools, reuse verified downloads, and record source coordinates, statistical definitions, and candidate-data decisions. Use for source acquisition or provenance checks, not model fitting.
---

# Census source trace

Produce a reusable source register and candidate observations from the user's requested census or statistical-yearbook tables. Use the host's existing browser, download adapter and format readers. This instruction package supplies no crawler, login implementation or database connector.

## Bind the task

Read the current project checkpoint and original acquisition receipts first. Identify the target source/book edition, statistical year, geographic level and boundary date, indicator, population/denominator, unit and intended use. Keep publication year separate. Use existing authorization, named sessions, request budgets and original task ownership; this skill creates none of them.

Use [examples/task.example.json](examples/task.example.json) to see the input fields. It is a synthetic, offline example, not a runnable connector configuration. Keep real project bindings, credentials, browser profiles and receipts in the user's private project outside this skill folder.

## Reuse before retrieval

Inventory only the task's known sources and checkpoint files. Match a saved source to its original request, receipt outcome, expected bytes and SHA-256. A matching filename or a receipt's mere existence is insufficient. Reuse a verified successful file and record that no new download occurred. A valid old file does not establish current login health.

Preserve unresolved requests, original failures and source holds. Before any retry, establish the original attempt's outcome; unknown download/click outcomes do not authorize replay. Use the existing adapter's recovery route. Do not recreate a missing ledger, switch source aliases to evade a hold, or migrate an in-flight task into this package. See [acquisition-and-resume](references/acquisition-and-resume.md) when retrieving or continuing work.

## Locate and read the source

Search with valid region aliases/codes, statistical year, book edition and table title/number. Use an existing catalogue or the publisher's contents to locate the source when useful. A catalogue hit, authenticated page and exported table are separate results. Record printed and platform page numbers independently when they differ.

Prefer an available native spreadsheet, official table export or HTML table. Read the actual format; preserve original bytes and separately identify any converted or decrypted derivative. For image-only pages, use the host's existing rendering/OCR tools on the required pages, retain page coordinates, and verify extracted candidates against the original image. Neither OCR nor a second rendering constitutes independent source corroboration.

Use existing authorized tools for any requested acquisition, with the project's bounded attempts and timeout policy. Confirm filters and business content, not just HTTP status or an institution label. A loading placeholder, masked value or login/error page is not zero observations. Stop that source on an unresolved access challenge or failed request according to its existing controls; continue unrelated authorized work. Do not bypass CAPTCHA/MFA.

## Register and decide

Read [record-contract](references/record-contract.md) before producing observations. Preserve book/edition, URL or database resource ID, table, page, sheet/cell or image coordinates, statistical and publication years, original values, units, footnotes, region boundary/membership and population/denominator definitions. Unknown fields stay null with a reason.

Keep measurement origin (`observed`, `derived`, `interpolated`, `substituted`, `unknown`) separate from review state (`candidate`, `accepted`, `conflict`, `needs_source`). A formula computed from observed parents remains `derived`. City/year alone cannot identify a record. Do not relabel substitutions or estimates as source observations.

Check file integrity, table identity/definitions, then numeric consistency. Use precision supported by the source. For aggregates, compare each numerator's and denominator's geographic members including multiplicity; matching grand totals do not establish identical geography. Recompute ratios from compatible summed counts rather than averaging regional ratios. An adjacent column's age threshold does not define the target mean or rate.

A candidate becomes an accepted observation only when required source, definition and geographic evidence passes the project's existing acceptance criteria. Record the decision and evidence. Technical acceptance does not change model inputs: formal research adoption remains a separate recorded decision within the user's authorized scope. This skill does not refit models or silently modify canonical data.

## Deliver

Save a source register, candidate records, conflicts/missing definitions and the receipt/cache references in a new project output or the established append-only workflow. Report requested versus acquired tables, verified versus unresolved observations, reuse/new-download counts and remaining blockers with clear denominators. Claim only checks actually performed.

The historical basis and remaining capability limits are in [validation-boundaries](references/validation-boundaries.md). Package checks, client loading, live acquisition and formal research adoption are distinct evidence levels.
