# SPEC-016 — Mews Nested-Feed Extension Report

Status: `IMPLEMENTED_LOCALLY_AWAITING_REVIEW`

## Outcome

The Mews contract is representable without employer-specific adapter logic. The
generic JSON-feed adapter now supports explicit nested child traversal, validated
per-group counts, bounded parent-context projection, deterministic identity
ordering, duplicate rejection, and optional declarative HTML detail selectors.

Mews passed both the zero-detail gate and a Mews-only production ingestion. The
recommendation is `KEEP_CONFIGURED`; adapter-extension value is
`MODERATE_REUSABLE_SOURCE_VALUE`.

## Public source contract

The current `https://www.mews.com/api/careers` response is a single list of nine
department groups. Each group exposes `name`, `jobs`, and `jobCount`. Child jobs
expose `id`, `title`, `url`, `location`, `locations`, and `updatedAt`.

At observation time the source contained 29 jobs. Every per-group count matched,
all 29 IDs and URLs were unique, all update timestamps were present, and no
pagination marker was present. Descriptions are not embedded; public detail pages
provide a title at `h1` and content at `.job-content`.

The old Greenhouse research fingerprint is historical and stale. It was not
silently rewritten.

## Zero-detail gate

- two bounded listing requests;
- deterministic rerun equality;
- 29 complete identities and 29 unique URLs;
- 11 listing-level `SELECT_IN_SCOPE`, 18 explicitly foreign/skipped;
- zero detail calls;
- zero Phase 2 writes;
- byte-identical operational SQLite.

SPEC-014 observed 28 jobs with the same 11/17 split. The new 29th job was foreign,
so the current 11/18 result is an explainable source change rather than a contract
regression.

## Production operation

The final normal Mews-only run was
`4f04bb78-cca2-4234-bcf3-19a776f28bab`:

| Metric | Result |
|---|---:|
| Complete inventory | 29 |
| Selected / intentionally skipped | 11 / 18 |
| Detail success / failure | 11 / 0 |
| Network detail requests | 11 |
| Estimated total listing + detail requests | 12 |
| Elapsed | 3.5 s |
| Usable active details | 11 |
| Unrelated employers refreshed | 0 |
| Semantic calls | 0 |

An initial listing-only run exposed that Mews does not embed descriptions. The
generic declarative detail selector was then added and the 11 selected records
were refreshed. This produced expected description-change evidence without any
closure or identity anomaly.

## Useful-market result

Mews added 11 usable independent clusters, but none currently enters the normal
candidate shortlist. All 11 are `OUT_OF_SCOPE` after detail because the public
source lists Czechia among country alternatives and the pages describe hybrid
working, but no Czech city establishes Prague. The frozen candidate policy accepts
normal onsite/hybrid work only in Prague, so the experiment did not weaken market
routing to manufacture a positive result.

Two clusters add title-supported target-family evidence:

- one `BUSINESS_REVENUE_OPERATIONS`;
- one `PRODUCT_STRATEGY`.

Target-family clusters increased 391 → 393, but routed target-family clusters
remained 318. No semantic call is currently justified by routing.

## Portfolio delta

| Boundary | Before | After | Delta |
|---|---:|---:|---:|
| Configured employers | 21 | 22 | +1 |
| Active jobs with detail | 3,991 | 4,002 | +11 |
| Opportunity clusters | 3,924 | 3,935 | +11 |
| Routed clusters | 3,377 | 3,377 | 0 |
| Inventory HHI | 2,883.19 | 2,873.14 | -10.05 |
| Detail HHI | 2,819.60 | 2,804.19 | -15.41 |
| Routed HHI | 3,509.65 | 3,509.65 | 0 |

SPEC-015's configuration-only work added three employers, 56 jobs, 51 routed
clusters, and three target-family clusters. SPEC-016 required a small reusable
adapter extension and added one employer, 29 jobs, 11 usable details, zero routed
clusters, and two target-family clusters. Immediate routed value is therefore
lower, while the first-party source is cheap and has a materially denser set of
Czechia-inclusive and target-title vacancies.

## Decision

`KEEP_CONFIGURED` is recommended because the source adds current Czechia-inclusive
evidence and target-role breadth at a bounded operational cost, and because a
future posting may explicitly resolve Prague or remote access. This is not a
claim that the current 11 roles belong in the shortlist; the frozen market policy
correctly excludes them on current evidence.

The extension is `MODERATE_REUSABLE_SOURCE_VALUE`: its contract is generic and
fully fixture-tested, but live reuse has only been demonstrated with Mews.

Detailed vacancy evidence, state reports, and operational SQLite remain private.
The repository-safe receipt is
`output/mews_nested_feed/spec016-mews-20260912-v1/aggregate_summary.json`.
