# SPEC-017 — Partial Geography Semantics Audit

Status: `COMPLETED_AWAITING_PROMOTION_REVIEW`

## Decision

Promote the generic evidence-semantics correction. The audit found a bounded
multi-source defect: the evaluator treated a recognized compatible country with
the required city absent as if a non-accepted city had been explicitly observed.

Candidate policy did not change. Prague remains the only normally accepted
onsite/hybrid city. The corrected distinction is:

```text
Prague, Czechia + onsite/hybrid          -> IN_SCOPE
Brno, Czechia + onsite/hybrid            -> OUT_OF_SCOPE
Czechia + city absent + onsite/hybrid    -> UNCERTAIN
foreign country + onsite/hybrid          -> OUT_OF_SCOPE
```

`UNCERTAIN` does not establish Prague compatibility and remains capped at
`REVIEW` by the existing routing policy.

## Root cause

The previous onsite/hybrid branch used this effective test:

```text
recognized country + no accepted-location match -> outside accepted location
```

That collapsed two different facts:

- an explicit incompatible country/city;
- an accepted country for which the required city was not supplied.

The promoted evaluator version is `phase4-current-candidate-market-v3`. It adds
the generic reason `ACCEPTED_COUNTRY_CITY_UNKNOWN` and changes only the second
case to uncertainty. It contains no employer-specific branch.

## Whole-corpus replay

The read-only replay evaluated 4,002 ACTIVE jobs with usable detail:

| Status | Before | After | Delta |
|---|---:|---:|---:|
| `IN_SCOPE` | 147 | 147 | 0 |
| `UNCERTAIN` | 3,280 | 3,306 | +26 |
| `OUT_OF_SCOPE` | 575 | 549 | -26 |

The only changed transition was:

```text
OUT_OF_SCOPE -> UNCERTAIN: 26
OUT_OF_SCOPE -> IN_SCOPE:   0
```

Changed cases were bounded to four employers: Wrike 13, Mews 11, ČSOB 1, and
Schneider Electric 1. Twenty-four had effective hybrid evidence and two had
onsite evidence. Every change had an accepted-country signal and absent city;
no explicit compatibility was invented.

The frozen SPEC-013 classifier found four target-family matches among changed
postings: three `PRODUCT_STRATEGY` and one `BUSINESS_REVENUE_OPERATIONS`. These
are lexical diagnostics, not semantic fit.

Impact classification: `BOUNDED_MULTI_SOURCE_CORRECTION`.

## Mews re-evaluation

All 11 usable Mews jobs shared the material structure:

- raw geography includes Czechia among country alternatives;
- structured city is absent;
- stored work mode is `unspecified`;
- current detail text supplies generic hybrid wording, producing effective
  `hybrid` evidence;
- no independent authorization, language, or working-hours incompatibility
  determines the result.

Mews therefore moves from 11 `OUT_OF_SCOPE` to 11 `UNCERTAIN`; none becomes
`IN_SCOPE`. The market-routed count moves from 0 to 11 and the deterministic
target-family routed count from 0 to 2.

No Mews job has a compatible semantic cache entry. Assessing all 11 would require
11 calls and is directionally estimated at `$0.0291423` using the frozen observed
Luna cost basis. No semantic call was made.

## Regression and integrity

All 15 truth-table cases passed, including explicit Prague, Brno, Ostrava,
Germany, United States, US-only remote, missing geography, Mews country
alternatives, and an independent Japanese-language incompatibility.

All 10 frozen historical market regressions passed, including US-only,
US-authorization, Santa Clara, Chicago/New York, Tokyo/Japanese, Mexico City,
Düsseldorf, Cork incomplete multi-location, and unresolved remote access.

The candidate market-access fingerprint remains
`86c00d7cfb8b40b02c141b955ce482575464396a3097065fd435e64d11411bdb`.
The semantic-profile fingerprint remains
`6579b21e2bc22fef927ca17bdf6083b7e9a099bd5810b49528f589c83793819b`.
The audit made zero SQLite writes and zero semantic calls; the database hash was
byte-identical before and after, and the 406 semantic-assessment rows were not
modified.

## Evidence boundary

The repository-safe receipt is
`output/partial_geography_semantics/spec017-partial-geography-20260912-v1/aggregate_summary.json`.
Per-job identities, titles, locations, and detailed reasons remain in the local
ignored `audit.json`. Operational SQLite remains private/local.

## Limitations and next gate

- The replay reflects the current local ACTIVE corpus, not an unbiased market
  sample.
- Geography normalization remains deliberately bounded rather than worldwide.
- Mews work mode is inferred from generic detail wording, not a structured source
  field.
- Moving to `UNCERTAIN` exposes jobs for verification; it does not establish
  Prague suitability.

The next gate is human review of this bounded correction. If promoted, decide in
a separate packet whether any newly uncertain opportunities justify semantic
assessment or whether source expansion, candidate-direction preference work, or
deterministic allocation should take priority.
