# SPEC-015 bounded production source onboarding

Run `spec015-onboarding-20260911-v1` onboarded only Keboola, Commerzbank, and
KPMG through the normal Phase 1/2 pipeline. State run
`1e5f4685-563d-40d5-8463-c364b6d34834` completed all three sources in 39.5s:
56 identities, 56 selected details, 56 successful details, zero failures, zero
skips, and zero semantic calls. Existing sources were not refreshed.

| Source | Inventory/details | Market status | Clusters/routed | Estimated logical requests | Keep? |
|---|---:|---|---:|---:|---|
| Keboola | 3/3 | 3 `IN_SCOPE` | 3/3 | 4 | Yes |
| Commerzbank | 24/24 | 19 `UNCERTAIN`, 3 `OUT_OF_SCOPE` across 22 clusters | 22/19 | 34 | Yes |
| KPMG | 29/29 | 29 `UNCERTAIN` | 29/29 | 39 | Yes |

The combined result is `MODEST_COVERAGE_IMPROVEMENT`: routed clusters increased
3,326 → 3,377; routed HHI improved 3,617.01 → 3,509.65; effective routed
employers improved 2.765 → 2.849. Active usable details increased 56 and all
three employers contribute routed clusters. Target-family coverage increased by
three clusters (two title-supported, one description-only), but target-family
`IN_SCOPE` supply did not increase; the three additions were `UNCERTAIN`.

The source contracts are operationally sound and should remain configured.
Keboola adds the strongest immediately actionable evidence. Commerzbank and KPMG
add employer breadth, but their Alma details omit work-mode evidence used by
candidate-market routing, limiting current precision. This is a downstream
normalization limitation, not an ingestion/lifecycle failure.

All 51 newly routed clusters are semantic cache misses by construction. At the
frozen Luna projection of $0.00204/job, assessing all would cost approximately
$0.104; this packet authorizes no calls. Mews remains the preferred next bounded
adapter-extension candidate because SPEC-014 showed five target-title signals
and 11 listing-level in-scope vacancies in one request.

Detailed vacancy evidence and operational SQLite remain private/local. The
repository-safe receipt is
`output/production_source_onboarding/spec015-onboarding-20260911-v1/aggregate_summary.json`.
Listing-request totals are reconstructed from the validated source contract plus
the state runner's exact detail-request count because Phase 2 currently persists
detail counts, not every HTTP listing/configuration request.
