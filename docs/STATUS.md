# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-016-mews-nested-feed-extension.md
```

Status: `APPROVED_FOR_IMPLEMENTATION`.

Implementation/operations agents must follow this pointer rather than infer work
from file recency. Before starting, verify the local working tree is synchronized
with `origin/main` when safe. Intentionally retained local operational/private
evidence is not itself an error; unexplained code/config divergence is.

The development authority boundary remains:

- agents may inspect, analyze, implement, validate, and perform explicitly approved bounded internal operations;
- implementation changes remain uncommitted while awaiting human/ChatGPT review;
- after explicit approval, the implementation agent may commit and push;
- humans approve decisions and promotion boundaries rather than perform Git plumbing manually;
- repository-safe aggregate evidence may be tracked, while detailed candidate- and human-judgment-derived evidence remains private/local unless explicitly authorized for disclosure.

## Mission

Monitor relevant public employer vacancies, maintain trustworthy lifecycle state,
and explain which active opportunities deserve a candidate's attention.

## Current phase

Phases 1–3 are implemented. Phase 4 has committed implementations for candidate
market access/routing, opportunity clustering/preferred variant, versioned decision
preferences, seniority guard, retrospective replay, residual market normalization,
prospective-validation preparation, semantic compute-allocation audit, completed
human compute-worthiness validation, source-portfolio/role-coverage audit, Wave A
source-contract preflight, and bounded production onboarding for three sources.

Frozen milestones:

- SPEC-013 source portfolio audit: `a4ebba825e80256ad55ed6bfcaf973a2df37d413`
- SPEC-014 Wave A preflight: `11e000825e339de8c772d5bd7a66e2567469f1b2`
- SPEC-015 production onboarding: `541685ce40e959a66d2ec443b6ef748190713bb1`

SPEC-016 is now approved to test one generic nested first-party JSON-feed capability
and Mews as the first source using it. No semantic calls are authorized.

## SPEC-015 frozen result

Experiment `EXP-PRODUCTION-SOURCE-ONBOARDING-001` completed a bounded production
run for Keboola, Commerzbank, and KPMG:

- run status: `COMPLETED`;
- inventory: 56;
- details: 56/56 successful;
- failures/skips: 0;
- semantic calls: 0;
- existing employers refreshed: 0;
- semantic assessments unchanged at 406.

Per employer:

```text
Keboola       3 inventory / 3 clusters / 3 routed / 3 IN_SCOPE
Commerzbank  24 inventory / 22 clusters / 19 routed / 19 UNCERTAIN + 3 OUT_OF_SCOPE
KPMG         29 inventory / 29 clusters / 29 routed / 29 UNCERTAIN
```

Coverage delta:

```text
configured employers       18 -> 21
ACTIVE jobs              3977 -> 4033
usable ACTIVE details    3935 -> 3991
opportunity clusters     3870 -> 3924
routed clusters          3326 -> 3377
routed HHI            3617.01 -> 3509.65
effective employers     2.765 -> 2.849
target-family clusters    388 -> 391
title-supported target    164 -> 166
```

Combined verdict: `MODEST_COVERAGE_IMPROVEMENT`.

All three sources remain configured. The experiment improved employer breadth but
did not increase target-family `IN_SCOPE` supply. Most new Commerzbank/KPMG roles
remain market `UNCERTAIN`, largely because available normalized evidence does not
resolve work arrangement.

All 51 newly routed clusters lack compatible semantics. Assessing all would be
approximately $0.104 at the frozen directional cost estimate; no calls were made.

## Why SPEC-016 exists

SPEC-014 found Mews to be a potentially higher-density source than several
configuration-only candidates:

- current first-party `/api/careers` source;
- 28 listings at preflight;
- 11 listing-level `IN_SCOPE`, 17 foreign;
- operations/product title signals;
- source requires nested-feed flattening rather than simple configuration reuse.

SPEC-016 asks whether the smallest **generic declarative nested-feed extension** can
support Mews cleanly and whether Mews' observed marginal useful-market value
justifies that reusable engineering complexity.

This is not authorization for a Mews-specific scraper.

## SPEC-013 portfolio finding

The pre-expansion 18-employer portfolio had high raw volume but low effective
breadth at the routed boundary:

- routed top-1/top-3 shares: 57.3% / 80.6%;
- routed HHI: 3,617;
- effective employer breadth: 2.77;
- target-family union: 388 clusters;
- target-family `IN_SCOPE`: 18;
- explicit decision-intelligence/support title matches: 0.

The durable intake principle remains:

> Maximize marginal useful market coverage, not raw vacancy volume.

## Candidate direction

Business/data/decision-analytics remains a viable career direction when business-facing
and aligned with broader AI/transformation work.

The candidate already has strong capability evidence for business analytics,
decision support, forecasting/KPI decomposition, commercial analytics, business
operations, and translating messy data into decisions.

A future explicit decision-preference update for `business_analytics` /
`decision_support` remains separate from source onboarding and is not authorized
inside SPEC-016.

## Confirmed candidate market policy

- Normal onsite/hybrid work: Prague only.
- Remote work: acceptable from Czechia when Czech-based employment/engagement and reasonably European-compatible hours are confirmed.
- Missing remote employment access: `UNCERTAIN`.
- Explicit incompatible foreign restriction: `OUT_OF_SCOPE`.
- Relocation: exceptional, not normal shortlist policy.
- Czech work access: confirmed; foreign authorization must not be inferred.
- Czech and English: work-capable; Slovak comprehension supported; French not currently work-capable; Japanese `NONE`.
- Candidate-market `UNCERTAIN`: maximum recommendation `REVIEW`.
- Explicit junior/graduate evidence: candidate-configurable maximum `LOW_PRIORITY`.
- Domain/function/employer/product aversions are soft and tradeable.

## Frozen preference policy

```text
STRONG_POSITIVE -> +0.4
POSITIVE        -> +0.2
NEUTRAL         ->  0.0
NEGATIVE        -> -0.3
aggregate cap   -> [-1.0, +1.0]
```

## Current gate

> Execute SPEC-016 only: reconstruct the current Mews feed contract, implement
> the smallest source-generic nested-feed extension, prove flat-feed backwards
> compatibility, rerun a zero-detail Mews gate, and only if it passes onboard
> Mews through normal production ingestion with zero semantic calls.

The final decision must compare Mews' actual useful-market contribution with the
engineering cost/reusability of the new capability.

## SPEC-016 protected boundaries

Do not change:

- candidate profile/preferences;
- market policy;
- semantic model/prompt/contract/weights;
- existing semantic cache;
- clustering semantics;
- seniority guard;
- Phase 1/2 identity/lifecycle semantics;
- Erste/Zentiva contracts;
- Wave B/Watchlist sources;
- historical experiment evidence.

No semantic calls are authorized.

## Intended architecture

```text
SOURCE PORTFOLIO
maximize useful market coverage
        ↓
DETERMINISTIC MARKET / HARD NEGATIVE FILTERS
remove obvious non-opportunities cheaply
        ↓
SEMANTIC COMPUTE ALLOCATION
spend reasoning where decision value is high
        ↓
RANKED OPPORTUNITY FEED
```

Source integration complexity and semantic compute cost remain separate optimization
problems.

## Direction after SPEC-016

Contingent on evidence:

1. keep Mews only if it meets ingestion invariants and adds useful coverage;
2. decide whether the generic nested-feed capability has sufficient reusable source value;
3. keep Erste and Zentiva in bounded source-contract investigation until safe;
4. consider the separate business-analytics / decision-support preference version;
5. then return to deterministic rejection/stretch-envelope architecture and semantic allocation;
6. preserve semantic-v1 until upstream source/routing evidence is better balanced.

## Known open decisions

- Mews keep/remove and nested-feed capability promotion after SPEC-016.
- Whether Erste or Zentiva deserves the next source-contract repair experiment.
- Whether business/data/decision-analytics receives an explicit decision-preference update.
- Deterministic rejection / stretch-envelope architecture.
- Semantic-call budget for later prospective ranking validation.
- Durable private backup/retention for operational SQLite and detailed human evidence.

## Explicitly do not build/tune yet

- Mews-specific branches in shared adapters;
- Erste/Zentiva fixes inside SPEC-016;
- Wave B onboarding/adapters;
- semantic prompt/model/weight tuning;
- cheap secondary LLM routing;
- embeddings/vector search;
- learned ranking/ML infrastructure;
- autonomous preference learning;
- broad fuzzy clustering;
- UI/feed/control panel;
- application automation;
- external actions inferred from `APPLY`.
