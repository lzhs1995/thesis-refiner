# Source and observation record contract

Map these fields onto an existing project register. Do not replace a working ledger merely to adopt these names. [The synthetic observation](../examples/observation.example.json) illustrates a candidate with unresolved evidence.

## Identities

| Layer | Identity and evidence |
| --- | --- |
| Acquisition | Original database/resource/edition/table and exact request identity from the existing adapter; retain original attempt and receipt IDs |
| Source bytes | Byte count and SHA-256 of the original artifact; derivatives have separate hashes and conversion provenance |
| Observation | Region and boundary version, statistical year, indicator definition, population/age, denominator, unit and source coordinates |

Search terms may be varied for discovery, but an existing request's URL/method/headers/body must not be rewritten and then called the same cached request. Two platforms serving the same book are not automatically two independent sources.

## Minimum record groups

| Group | Fields to preserve |
| --- | --- |
| Provenance | Database/publisher, stable URL or resource ID, book title/edition, publication year, statistical year, table title/number, printed page, platform page, sheet and cell or image bounding box, retrieval time, original bytes/SHA-256, reader/version, footnote text |
| Semantics | Source and standardized indicator names, region code/name and valid aliases, boundary date/version, population, age threshold, census/sample scope, residence/household registration/urban-rural scope, original unit, numerator and denominator definitions |
| Lineage | Original displayed value/type, parsed value, original precision, conversion factor, formula and parent record IDs/coordinates/hashes; measurement origin |
| Review | Review state and reasons, file/table/numeric checks, unresolved fields, geographic member evidence, decision evidence, intended use and formal-adoption status |

A page-only source need not invent a sheet or cell; use the locator appropriate to that source. Unknown metadata is null plus a reason, never a guessed date or fabricated HTTP status. Preserve textual numbers and displayed rounding separately from parsed values.

## Three distinct checks

1. **File:** actual format/magic bytes, parseability and completeness; exclude login/error pages. Record both original and converted files. A values-only workbook does not preserve formulas or original formatting.
2. **Table:** confirm filters, region, year, table header hierarchy, unit and footnotes. Establish the target column's population, age and denominator directly; nearby headings do not automatically apply.
3. **Numeric:** detect duplicate observation keys, magnitude/unit issues, incompatible numerator/denominator, formula errors and inconsistent components. Tolerances follow source precision. Do not back-calculate a replacement just to make a check pass.

For region aggregates, record every member and its count for every numerator component and denominator. Verify overlap, completeness and boundary date. A matching province total, city name or code does not prove identical region membership. Keep unavailable boundary evidence unresolved.

## States and adoption

- `candidate`: extracted or transcribed but not fully accepted.
- `accepted`: required evidence and project acceptance criteria pass; record the decision.
- `conflict`: evidence contradicts the requested definition, location, value or scope.
- `needs_source`: required source or semantic evidence is absent.

Separately use `observed`, `derived`, `interpolated`, `substituted` or `unknown` for measurement origin. An accepted derived measure is still derived. Published counts converted into a ratio retain all parent records and unit conversions.

`formal_adoption` records whether the research project actually adopted a record and its decision reference. Source acceptance alone does not insert the value into canonical data or authorize model refitting. An existing documented adoption rule may supply the authority; the skill does not require a new confirmation for every record.

Report table coverage and observation coverage with their own denominators; downloading a book is not complete city-year coverage. Retain conflicts and excluded records alongside the accepted view.
