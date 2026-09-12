# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-015-bounded-production-source-onboarding.md
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
market access/routing, high-confidence opportunity clustering, preferred variant,
versioned decision preferences, seniority guard, retrospective replay, residual
market normalization, prospective-validation preparation, semantic compute-allocation
audit, completed human compute-worthiness validation, source-portfolio/role-
coverage audit, and Wave A source-contract preflight.

SPEC-013 is frozen in commit `a4ebba825e80256ad55ed6bfcaf973a2df37d413`.
SPEC-014 is frozen in commit `11e000825e339de8c772d5bd7a66e2567469f1b2`.

SPEC-015 has completed locally: Keboola, Commerzbank, and KPMG passed full
inventory/detail ingestion with zero failures and zero semantic calls. The
combined verdict is `MODEST_COVERAGE_IMPROVEMENT` and awaits promotion review.

## SPEC-014 frozen result

Run `wave-a-preflight-20260911-v4` completed all nine listing inventories in 36
bounded public requests, with zero detail calls, zero semantic calls, unchanged
production configuration, and byte-identical operational SQLite.

Configuration-ready and approved for SPEC-015 bounded onboarding:

- Keboola — 3 listings, all three listing-level in scope, one decision-support title signal;
- Commerzbank — 24 Czech listings, two product title signals;
- KPMG — 29 Czech listings, one analytics and one transformation title signal.

Not approved for SPEC-015:

- Mews — valuable first-party nested feed requiring a reusable declarative flattening extension;
- Erste Group — inventory works but listing geography is unavailable;
- Zentiva — Workday identity/location mapping must be corrected before onboarding;
- Productboard, ABB, MSD — low current marginal target-role value in the frozen preflight.

The detailed findings are in `docs/wave_a_source_contract_preflight_report.md`;
repository-safe evidence is indexed by `EXP-WAVE-A-PREFLIGHT-001`.

## SPEC-013 frozen result

Run `source-portfolio-audit-20260911-v2` found:

- complete inventory: 16,490 postings;
- routed-cluster effective breadth: 2.77 employers despite 18 configured employers;
- routed top-1/top-3 shares: 57.3% / 80.6%;
- EY routed contribution: 1,907 clusters / 57.3%;
- Schneider Electric: 456 / 13.7%;
- Johnson & Johnson: 318 / 9.6%;
- target-family union: 388 clusters;
- target-family title-supported evidence: 164 clusters;
- explicit decision-intelligence/support title matches: 0;
- target-family market status: 18 `IN_SCOPE`, 297 `UNCERTAIN`, 73 `OUT_OF_SCOPE`;
- candidate capability representation for business analytics/decision support is already strong;
- no production employer or preference change was made.

The durable intake principle is:

> Maximize marginal useful market coverage, not raw vacancy volume.

## SPEC-012 completed result

The frozen semantic compute-worthiness experiment reviewed 60/60 opportunity clusters:

```text
WORTH_DEEP_ASSESSMENT      3
NOT_WORTH_DEEP_ASSESSMENT 57
NEED_MORE_INFO             0
```

By frozen triage stratum:

```text
SEMANTIC_PRIORITY  3 worth / 17 not worth
SEMANTIC_OPTIONAL  0 worth / 20 not worth
SEMANTIC_DEFER     0 worth / 20 not worth
```

DEFER safety passed; PRIORITY precision failed at 15% versus the frozen 60% gate.
The current triage is not promoted as a runtime semantic-compute gate.

## New human direction captured by SPEC-013

Business/data/decision-analytics is a viable career direction when business-facing
and aligned with broader AI/transformation work.

Existing candidate capability already includes strong evidence for business
analytics, decision support, forecasting/KPI decomposition, commercial analytics,
business operations, and turning messy data into clear business decisions.

Hard-skill gaps such as SQL/Python depth remain real. The target is not generic
reporting/data administration; it is analytics connected to decisions,
transformation, commercial/product outcomes, and AI-enabled work.

A future decision-preference update for `business_analytics` / `decision_support`
remains a separate approval. It is not part of SPEC-015.

## Fresh operational state from SPEC-009

Run `07c036f3-c512-4469-ada6-fe57bf9d337b`:

- 18/18 sources successful and complete;
- inventory: 16,490;
- selected for detail: 3,949;
- active jobs after refresh: 3,977;
- closed jobs: 120;
- active jobs with usable semantic detail: 3,935;
- existing semantic assessments at refresh: 406.

Later audit evidence showed approximately 3,315 routed post-historical-exclusion
clusters and strong employer concentration.

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

> Review SPEC-015's keep recommendation for all three sources and decide whether
> Mews should receive the next reusable nested-feed adapter-extension packet.

The key result is not whether three sources can be scraped. It is whether the
observable opportunity universe becomes meaningfully broader and more relevant.

## SPEC-015 protected boundaries

Do not change:

- employers other than Keboola, Commerzbank, and KPMG;
- candidate profile/preferences;
- market policy;
- semantic model/prompt/contract/weights;
- existing semantic cache;
- clustering semantics;
- seniority guard;
- historical evidence;
- Phase 1/2 lifecycle and identity contracts.

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

Employer breadth and semantic-call minimization remain separate optimization
problems.

## Direction after SPEC-015

Contingent on evidence:

1. keep only production sources that meet existing invariants and add useful coverage;
2. compare their observed marginal value with the expected value of a small reusable Mews nested-feed extension;
3. keep Erste and Zentiva in source-contract investigation until evidence is safe;
4. separately decide whether to version business-analytics / decision-support preference;
5. then revisit deterministic rejection/stretch-envelope and semantic compute allocation;
6. preserve semantic-v1 until upstream market/intake architecture is better balanced.

## Known open decisions

- Per-employer keep/remove decision after SPEC-015 bounded production evidence.
- Whether Mews receives the next reusable adapter-extension packet.
- Whether business/data/decision-analytics receives an explicit decision-preference update.
- Deterministic rejection / stretch-envelope architecture after source coverage improves.
- Semantic-call budget for later prospective ranking validation.
- Durable private backup/retention for operational SQLite and detailed human evidence.

## Explicitly do not build/tune yet

- Mews adapter extension inside SPEC-015;
- Erste/Zentiva fixes inside SPEC-015;
- Wave B adapters/onboarding;
- semantic prompt/model/weight tuning;
- cheap secondary LLM routing;
- embeddings/vector search;
- learned ranking/ML infrastructure;
- autonomous preference learning;
- broad fuzzy clustering;
- UI/feed/control panel;
- application automation;
- external actions inferred from `APPLY`.
