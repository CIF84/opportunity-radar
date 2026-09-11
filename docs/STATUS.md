# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-014-wave-a-source-contract-preflight.md
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
audit, completed human compute-worthiness validation, and source-portfolio/role-
coverage audit.

SPEC-013 is now frozen in commit `a4ebba825e80256ad55ed6bfcaf973a2df37d413`.
It established that the current 18-employer source portfolio has high raw vacancy
volume but low effective employer breadth, especially at the routed-cluster boundary.

The zero-detail Wave A source-contract preflight is implemented and awaiting
promotion review. No employer is authorized for production onboarding yet.

## SPEC-014 completed result

Run `wave-a-preflight-20260911-v4` completed all nine listing inventories in 36
bounded public requests, with zero detail calls, zero semantic calls, unchanged
production configuration, and byte-identical operational SQLite.

- configuration-ready: Keboola, Commerzbank, KPMG;
- reusable bounded adapter fix: Mews nested first-party feed;
- investigate before onboarding: Erste listing geography;
- generic contract correction before onboarding: Zentiva Workday identity and
  listing-location mapping;
- low current marginal target-role value: Productboard, ABB, MSD.

The detailed findings are in
`docs/wave_a_source_contract_preflight_report.md`; repository-safe evidence is
indexed by `EXP-WAVE-A-PREFLIGHT-001`.

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

Directional gates:

- DEFER safety: PASS at 100%;
- DEFER worth count: PASS at 0;
- PRIORITY precision: FAIL at 15% versus >=60%;
- information sufficiency: PASS;
- employer-specific catastrophic blind spot: none detected.

The current triage is therefore not promoted as a runtime semantic-compute gate.

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

SPEC-013 proposed the following employer portfolio:

### Wave A — configuration-first candidates

- Keboola
- Mews
- Productboard
- Commerzbank
- Erste Group
- ABB
- KPMG
- MSD
- Zentiva

### Wave B — higher-value source work

- Gen Digital
- Mastercard
- Visa
- Rossum
- Accenture
- Barclays
- Microsoft
- Sanofi
- Takeda
- AstraZeneca

### Watchlist

- BCG
- Deloitte
- Eaton
- McKinsey
- Novartis
- RBI
- Resistant AI
- Bosch
- Oracle
- PwC
- Bayer

## Why SPEC-014 exists

Technical reachability is not enough to justify onboarding a source.

For each Wave A employer the system must establish, before production configuration:

```text
Can we enumerate it reliably?
Can an existing adapter handle it?
Do listings expose useful geography/title evidence?
Does it add target-role-family breadth?
Does it add employer/business-model diversification?
What detail burden would onboarding create?
```

The result should recommend only the employers with the highest **marginal useful
market coverage**, not mechanically onboard all nine.

SPEC-014 is explicitly zero-detail: it may inspect public listing/index surfaces
and pagination/source contracts, but it may not retrieve job-detail pages or mutate
Phase 2 state.

## New human direction captured by SPEC-013

Business/data/decision-analytics is a viable career direction when business-facing
and aligned with broader AI/transformation work.

Existing candidate capability already includes strong evidence for:

- business analytics;
- decision support;
- forecasting/KPI decomposition;
- commercial analytics;
- business operations;
- turning messy data into clear business decisions.

Hard-skill gaps such as SQL/Python depth remain real. The target is not generic
reporting/data administration; it is analytics connected to decisions,
transformation, commercial/product outcomes, and AI-enabled work.

A future decision-preference update for `business_analytics` / `decision_support`
remains a separate approval. It is not part of SPEC-014.

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

## Frozen items during SPEC-014

Do not change:

- production `config/companies.yaml`;
- operational SQLite / Phase 2 state;
- Luna / low / `phase3-semantic-v1`;
- semantic assessments/cache;
- Phase 3 scoring weights;
- candidate profile/preferences;
- market-access policy and market-status rules;
- clustering contract;
- seniority guard;
- historical judgments and completed SPEC-012 evidence;
- SPEC-008 frozen prospective protocol;
- Phase 1/2 identity/lifecycle contracts.

SPEC-014 authorizes bounded public listing/index calls for the nine Wave A
candidates only. Detail retrieval and semantic calls remain prohibited.

## Current gate

> Review whether Keboola, Commerzbank, and KPMG should enter one bounded
> configuration-only production-onboarding experiment, while Mews is evaluated
> separately as the first reusable adapter-extension candidate.

A technically scrapeable source may still receive NO-GO if marginal useful market
coverage is weak.

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

## Next intended steps

1. Review the SPEC-014 scorecard and three-source configuration-only recommendation.
2. Only after explicit approval, create a bounded production-onboarding packet for Keboola, Commerzbank, and KPMG.
3. Review Mews as a separate generic nested-feed extension; do not combine it with configuration-only onboarding.
4. Keep Erste and Zentiva in source-contract investigation until their listing evidence is safe.
5. Separately decide whether to create a new decision-preference version for business analytics / decision support.
6. Preserve semantic-v1 while source breadth improves.
7. Revisit deterministic rejection/stretch-envelope and semantic compute allocation after intake evidence is more balanced.

## Known open decisions

- Whether to approve bounded configuration-only onboarding for Keboola, Commerzbank, and KPMG.
- Whether Mews should receive the next reusable adapter-extension packet.
- Whether business/data/decision-analytics receives an explicit decision-preference update.
- Deterministic rejection / stretch-envelope architecture after source coverage improves.
- Semantic-call budget for later prospective ranking validation.
- Durable private backup/retention for operational SQLite and detailed human evidence.
- Bounded semantic-call authority available to future agents.

## Explicitly do not build/tune yet

- production employer expansion before SPEC-014 review;
- new provider adapters for Wave B;
- semantic prompt/model/weight tuning;
- cheap secondary LLM routing;
- embeddings/vector search;
- learned ranking/ML infrastructure;
- autonomous preference learning;
- broad fuzzy clustering;
- UI/feed/control panel;
- application automation;
- external actions inferred from `APPLY`.
