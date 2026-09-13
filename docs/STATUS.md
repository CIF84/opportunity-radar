# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-017-partial-geography-semantics-audit.md
```

Status: `IMPLEMENTED_LOCALLY_AWAITING_REVIEW`.

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
source-contract preflight, bounded production onboarding for three sources, and a
generic nested-feed extension with Mews production onboarding.

Frozen milestones:

- SPEC-013 source portfolio audit: `a4ebba825e80256ad55ed6bfcaf973a2df37d413`
- SPEC-014 Wave A preflight: `11e000825e339de8c772d5bd7a66e2567469f1b2`
- SPEC-015 production onboarding: `541685ce40e959a66d2ec443b6ef748190713bb1`
- SPEC-016 nested feeds + Mews: `556fd7aec5d77874f56d7a5b5137a06a75fbfbca`

SPEC-017 completed its read-only audit and implemented the bounded generic
correction. Promotion awaits review. This is an evidence-semantics correction,
not a candidate-policy change.

## SPEC-017 completed result

The evaluator previously treated a recognized compatible country with the
required city absent as explicit location incompatibility. The corrected
`phase4-current-candidate-market-v3` evaluator returns `UNCERTAIN` for that
partial evidence while keeping explicit non-Prague Czech cities and foreign
onsite/hybrid locations `OUT_OF_SCOPE`.

Read-only replay over 4,002 ACTIVE usable details produced exactly 26 changes:

```text
OUT_OF_SCOPE -> UNCERTAIN  26
OUT_OF_SCOPE -> IN_SCOPE    0
```

The changes are bounded to Wrike 13, Mews 11, ČSOB 1, and Schneider Electric 1.
All 15 truth-table cases and 10 frozen historical market regressions passed.
Candidate-policy and semantic-profile fingerprints remain unchanged; SQLite was
byte-identical; semantic calls were zero.

Mews now contributes 11 `UNCERTAIN` market-routed clusters, including two
deterministic target-family signals. No job became `IN_SCOPE`. Assessing those
11 cache misses would directionally cost about `$0.0291`; no calls were made.

Impact: `BOUNDED_MULTI_SOURCE_CORRECTION`. Canonical report:
`docs/partial_geography_semantics_audit.md`.

## Last known operational health

- SQLite schema: version 3.
- ACTIVE jobs with usable detail assessed by SPEC-017: 4,002.
- Existing semantic assessments: 406, unchanged.
- Offline validation: 294 passed, 22 live tests deselected.
- External source calls during SPEC-017: 0.
- External semantic calls during SPEC-017: 0.
- Operational SQLite remains private/local and intentionally uncommitted.

## SPEC-016 frozen result

The current Mews `/api/careers` contract contains 29 unique jobs in nine parent
groups. The generic nested-feed implementation supports declarative flattening,
explicit parent-context inheritance, group-count validation, deterministic
ordering, duplicate rejection, and optional HTML detail selectors with no
Mews-specific branch.

Mews production ingestion:

```text
inventory                         29
selected / intentionally skipped 11 / 18
detail success / failure          11 / 0
network detail requests           11
usable clusters added             11
routed clusters added              0
target-family clusters added       2
semantic calls                     0
```

All 11 detailed Mews clusters currently evaluate `OUT_OF_SCOPE`: Czechia appears
among country alternatives and the postings are hybrid, but no Czech city proves
Prague. The source remains configured and the extension verdict is
`MODERATE_REUSABLE_SOURCE_VALUE`.

This result exposed a generic semantic question: when country is compatible but
city evidence is absent, does the evaluator correctly return `UNCERTAIN`, or does
it infer incompatibility from missing city evidence?

## Why SPEC-017 exists

Candidate policy remains unchanged:

> Normal onsite/hybrid work is acceptable in Prague only.

But policy and evidence are different objects.

The intended distinction is:

```text
Prague hybrid                  -> IN_SCOPE
explicit Brno hybrid           -> OUT_OF_SCOPE
Czechia hybrid, city absent    -> UNCERTAIN
explicit Germany hybrid        -> OUT_OF_SCOPE
```

SPEC-017 freezes this as an audit hypothesis, reconstructs current evaluator
behavior, replays any proposed generic correction over the whole active corpus,
and verifies historical explicit-market cases before changing runtime semantics.

The packet must not make missing evidence equivalent to positive compatibility;
partial Czech geography should normally move at most from `OUT_OF_SCOPE` to
`UNCERTAIN` unless explicit Prague evidence exists independently.

## SPEC-015 frozen result

Keboola, Commerzbank, and KPMG remain configured after a bounded production run:

- inventory: 56;
- details: 56/56 successful;
- new routed clusters: 51;
- semantic calls: 0;
- combined verdict: `MODEST_COVERAGE_IMPROVEMENT`.

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

## SPEC-012 completed compute-worthiness result

The frozen 60-opportunity human experiment produced:

```text
WORTH_DEEP_ASSESSMENT      3
NOT_WORTH_DEEP_ASSESSMENT 57
NEED_MORE_INFO             0
```

All three WORTH cases occurred in `SEMANTIC_PRIORITY`; PRIORITY precision was
15%, so the triage is not promoted. This evidence remains frozen during
SPEC-017.

## Candidate direction

Business/data/decision-analytics remains a viable career direction when business-facing
and aligned with broader AI/transformation work.

The candidate already has strong capability evidence for business analytics,
decision support, forecasting/KPI decomposition, commercial analytics, business
operations, and translating messy data into decisions.

A future explicit decision-preference update for `business_analytics` /
`decision_support` remains separate and is not authorized inside SPEC-017.

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

## Current gate

> Review SPEC-017's bounded generic evidence-semantics correction and decide
> whether to promote it. Do not interpret newly `UNCERTAIN` jobs as confirmed
> Prague-compatible opportunities.

No semantic calls are authorized.

## SPEC-017 protected boundaries

Do not change:

- candidate market policy itself;
- candidate preferences;
- source configuration;
- semantic model/prompt/contract/weights/cache;
- clustering semantics;
- seniority guard;
- Phase 1/2 identity/lifecycle semantics;
- historical evidence.

If semantics change, documentation must state clearly that **policy did not
change; interpretation of incomplete evidence changed**.

## Intended architecture

```text
SOURCE EVIDENCE
what the employer actually states
        ↓
CANDIDATE MARKET POLICY
what is acceptable
        ↓
MARKET ASSESSMENT
IN_SCOPE / UNCERTAIN / OUT_OF_SCOPE
```

Missing evidence must not silently become an asserted negative fact.

## Direction after SPEC-017

Contingent on evidence:

1. review and, if accepted, promote the SPEC-017 evaluator correction;
2. decide separately whether newly uncertain jobs warrant semantic assessment;
3. continue source expansion only after the routing boundary is trustworthy;
4. keep Erste/Zentiva source-contract issues separate;
5. separately decide whether to version business-analytics / decision-support preference;
6. return to deterministic rejection/stretch-envelope and semantic allocation after upstream evidence is better balanced.

## Known open decisions

- Promotion of the proven SPEC-017 generic market-evidence correction.
- Whether any newly uncertain Mews opportunities justify semantic assessment.
- Whether Erste or Zentiva deserves the next source-contract repair experiment.
- Whether business/data/decision-analytics receives an explicit decision-preference update.
- Deterministic rejection / stretch-envelope architecture.
- Semantic-call budget for later prospective ranking validation.
- Durable private backup/retention for operational SQLite and detailed human evidence.

## Explicitly do not build/tune yet

- candidate policy relaxation;
- employer-specific market-routing logic;
- new source integrations during SPEC-017;
- semantic prompt/model/weight tuning;
- cheap secondary LLM routing;
- embeddings/vector search;
- learned ranking/ML infrastructure;
- autonomous preference learning;
- broad fuzzy clustering;
- UI/feed/control panel;
- application automation;
- external actions inferred from `APPLY`.
