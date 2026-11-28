# Reproduction checks

## Units and spatial weights

- Identify each analysis population separately: administrative unit or grid cell, geographic definition/version, period, inclusion rule and missingness rule. Compare exact ID sets and exclusion reasons, not just row counts. For panels, require unique `(unit_id, time)` keys and report unmatched waves.
- Preserve IDs as strings where leading zeros matter. Check duplicate/missing IDs, one-to-one joins and row counts before/after every merge. Keep labels with embedded line breaks quoted in CSV exports and verify the parsed records.
- Save the ordered ID vector used by the model and by both axes of the weight matrix. Require exact equality. If reordering is needed, use an explicit ID permutation for data and both matrix axes, and save it; never infer order from row count or geographic names.
- Record CRS, coordinate source (centroid, seat or other), distance metric/units, threshold or neighbor rule, symmetry, diagonal, row standardization and island policy. Verify these against the executed object, not only comments. Similar labels across software do not establish equivalent weights.

## Estimands and formulas

1. For every reported column, record whether it is a local coefficient, effect point estimate, simulation mean, uncertainty summary or derived statistic. Preserve unrounded values and the original output accessor/locator.
2. In an SDM, distinguish the local coefficient `beta` from direct, indirect and total effects `D`, `I`, `T`. A ratio calculated from point estimates must use those estimates even if the displayed effect columns are simulation means. In general, `mean(D_draw/T_draw)` differs from `mean(D_draw)/mean(T_draw)` and from `D_point/T_point`.
3. Copy a custom expression literally from its authoritative script, with sign/absolute-value rules, scale and denominator-zero handling. Evaluate that expression from its designated inputs. Compare a conventional alternative only as a separately labeled definition; numeric disagreement between definitions is not evidence of an arithmetic error.
4. Use synthetic sign and zero cases to check formula interpretation without exposing project values. For example, compare the recorded formula's behavior when `D` and `beta` have the same/opposite signs; leave a zero denominator undefined unless the source specifies otherwise. Never silently replace a signed ratio with an absolute ratio.
5. Record a correction's source, date, scope and superseded claim. A later specific correction takes precedence within that scope; preserve the older evidence and unrelated unresolved interpretation.

## Tolerance and randomness

- Declare the comparison rule before evaluating results. One possible rule is `abs(observed-reference) <= atol + rtol*abs(reference)`; use the project's agreed rule and values, not automatic defaults. Compare missingness and infinities separately. Do not widen tolerance after observing a discrepancy.
- Compare published display cells at the recorded number of decimals and rounding convention; retain the full-precision comparison separately. Distinguish file SHA equality, parsed data equality, numeric tolerance and display agreement.
- For stochastic output record seed, RNG kind, simulation count, package/software versions and available environment lock. Unknown historical settings stay unknown. A new fixed seed supports repeatability of that new run, not recovery of the original seed.
- If only rounded historical breakpoints remain, do not treat reconstructed bins as exact historical membership. Compare saved assignments, cutpoints and counts where available; attribute a difference to randomness, version or geometry only with supporting evidence.

## Evidence grades

Grades describe evidence type; they are not a single ladder of scientific validity.

| Grade | Required evidence | Permitted claim |
|---|---|---|
| `historical_evidence` | Pinned old script/report/output with locator | What was saved or documented then; no current execution claim |
| `current_readback` | Current hash/content check of selected artifacts | Selected files still match; no runtime claim |
| `current_replay` | Actual bounded invocation, environment, terminal log and output pins | This execution completed; numeric agreement requires its own comparison |
| `comparison_verified` | Matching scope/estimand plus explicit comparison rules and results | Only the checked cells/objects agree under those rules |

Record client loading and UI observations separately, with client/version/action/result when actually observed. Partial scientific provenance, unresolved model warnings and unknown historical settings survive a successful replay or packaging check. A software exemption is `NOT_APPLICABLE` for replay, while its historical audit can still be complete.
