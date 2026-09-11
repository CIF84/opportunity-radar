# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-013-source-portfolio-and-role-coverage-audit.md
```

Status: `IMPLEMENTED_LOCALLY_AWAITING_REVIEW`.

Implementation/operations agents must follow this pointer rather than infer work
from file recency. Before starting, verify the local working tree is synchronized
with `origin/main` when safe. Intentionally retained local operational/private
evidence is not itself an error; unexplained code/config divergence is.

The development authority boundary remains:

- agents may inspect, analyze, implement, validate, and perform explicitly
  approved bounded internal operations;
- implementation changes remain uncommitted while awaiting human/ChatGPT review;
- after explicit approval, the implementation agent may commit and push;
- humans approve decisions and promotion boundaries rather than perform Git
  plumbing manually;
- repository-safe aggregate evidence may be tracked, while detailed candidate-
  and human-judgment-derived evidence remains private/local unless explicitly
  authorized for disclosure.

## Mission

Monitor relevant public employer vacancies, maintain trustworthy lifecycle
state, and explain which active opportunities deserve a candidate's attention.

## Current phase

Phases 1–3 are implemented. Phase 4 has committed implementations for candidate
market access/routing, high-confidence opportunity clustering, preferred variant,
versioned decision preferences, seniority guard, retrospective replay, residual
market normalization, prospective-validation preparation, semantic compute-
allocation audit, and completed human compute-worthiness validation.

The latest completed human experiment is SPEC-012. Its repository-safe result was
committed in `e276541598131d7d9132789dbdd3cf88e4460ffe`.

SPEC-013 has now audited **source portfolio quality** locally. It found that the
current 18-employer intake is highly concentrated and that target analytics/
decision-support supply is both employer-concentrated and mostly market
`UNCERTAIN`. No production employer was added.

## SPEC-012 completed result

The frozen semantic compute-worthiness experiment reviewed 60/60 opportunity
clusters:

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

The current triage is therefore **not promoted** as a runtime semantic-compute
gate. The narrower hypothesis remains useful: all three observed human-valued
cases concentrated in PRIORITY, but PRIORITY is too noisy.

Projected current-population economics remain directional only:

```text
all routed            ~3,109 calls / ~$8.24
PRIORITY only            ~489 calls / ~$1.30
```

The 3/3 observed worth recall in PRIORITY is insufficient for production
promotion.

## New human direction captured for SPEC-013

The candidate explicitly confirmed that business/data/decision-analytics work is
a viable career direction when it is business-facing and aligned with broader
AI/transformation work.

The candidate already has deep historical capability in:

- business analytics;
- decision support;
- forecasting/KPI decomposition;
- commercial analytics;
- turning messy data into clear insights and business decisions.

Current hard-skill gaps such as SQL/Python depth remain real and should not be
hidden. The attractive direction is not generic reporting/data administration;
it is analytics connected to decisions, transformation, commercial/product
outcomes, and AI-enabled work.

The 60-item human review also made repeated employers highly visible, triggering
a separate concern: current intake may have adequate vacancy **volume** but
insufficient employer **breadth**.

## Fresh operational state from SPEC-009

Run `07c036f3-c512-4469-ada6-fe57bf9d337b`:

- 18/18 sources successful and complete;
- inventory: 16,490;
- selected for detail: 3,949;
- active jobs after refresh: 3,977;
- closed jobs: 120;
- active jobs with usable semantic detail: 3,935;
- existing semantic assessments at refresh: 406.

Later compute-allocation audit evidence showed approximately 3,315 routed
post-historical-exclusion clusters and substantial employer concentration; the
largest employer represented about 57% of that audit population.

High posting volume is therefore not proof of useful market coverage.

## Current source portfolio

The committed `config/companies.yaml` contains 18 employers across:

- Workday;
- Greenhouse;
- AlmaCareer/Jobs.cz;
- SuccessFactors;
- generic HTML;
- JSON feed;
- Phenom.

SPEC-013 must audit concentration and target-role coverage before adding sources.
The objective is not “more companies” by itself; it is **higher marginal useful
market coverage**.

## SPEC-013 local result

Run `source-portfolio-audit-20260911-v2` used the latest complete 18-employer
inventory and current ACTIVE detailed state without mutating SQLite:

- inventory top-1/top-3 share: 47.9% / 77.9%;
- usable-detail top-1/top-3 share: 48.9% / 78.1%;
- routed-cluster top-1/top-3 share: 57.3% / 80.6%;
- routed HHI: 3,617; effective breadth: 2.77 employers;
- 388 clusters had at least one target-family signal, of which 164 had
  title-supported evidence;
- target-family market status: 18 `IN_SCOPE`, 297 `UNCERTAIN`, 73
  `OUT_OF_SCOPE`;
- target-family top-1 share: 55.9%; effective breadth: 2.84 employers;
- explicit decision-intelligence/support title matches: 0;
- employer longlist: 30; proposed Wave A: 9; Wave B: 10; Watchlist: 11;
- external semantic calls: 0; new-employer ingestion calls: 0; SQLite writes: 0.

The candidate profile already represents business analytics and decision
support as expert capabilities. The audit proposes, but does not implement, a
future versioned decision-preference update for those concepts.

The repository-safe result is
`output/source_portfolio_audit/source-portfolio-audit-20260911-v2/aggregate_summary.json`;
the human-readable analysis is
`docs/source_portfolio_and_role_coverage_report.md`. Per-cluster role examples
remain private/local.

## Confirmed candidate market policy

- Normal onsite/hybrid work: Prague only.
- Remote work: acceptable from Czechia when Czech-based employment/engagement
  and reasonably European-compatible hours are confirmed.
- Missing remote employment access: `UNCERTAIN`.
- Explicit incompatible foreign restriction: `OUT_OF_SCOPE`.
- Relocation: exceptional, not normal shortlist policy.
- Czech work access: confirmed; foreign authorization must not be inferred.
- Czech and English: work-capable; Slovak comprehension supported; French not
  currently work-capable; Japanese `NONE`.
- Candidate-market `UNCERTAIN`: maximum recommendation `REVIEW`.
- Explicit junior/graduate evidence: candidate-configurable maximum
  `LOW_PRIORITY`.
- Domain/function/employer/product aversions are soft and tradeable.

## Frozen preference policy

```text
STRONG_POSITIVE -> +0.4
POSITIVE        -> +0.2
NEUTRAL         ->  0.0
NEGATIVE        -> -0.3
aggregate cap   -> [-1.0, +1.0]
```

## Frozen items during SPEC-013

Do not change:

- Luna / low / `phase3-semantic-v1`;
- Phase 3 scoring weights;
- current semantic assessments/cache;
- market-access policy and market-status rules;
- clustering contract;
- seniority guard;
- historical judgments and completed SPEC-012 evidence;
- SPEC-008 frozen prospective protocol;
- Phase 1/2 identity/lifecycle contracts.

SPEC-013 authorizes bounded public career-source discovery but no semantic calls,
no paid APIs, no new-employer full refresh, and no external actions.

## Current gate

> Review the SPEC-013 result before promoting any employer expansion or
> candidate-preference change. If accepted, the smallest next packet is a
> zero-detail source-contract preflight for the nine proposed Wave A employers.

The audit found that employer selection, role-family visibility, and incomplete
market evidence all contribute. Candidate capability representation is not the
cause. Production configuration must remain unchanged until the audit and a
bounded source-contract preflight are explicitly approved.

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

Employer breadth and semantic-call minimization are separate optimization
problems. Do not narrow intake merely to reduce compute cost.

## Next intended steps

1. Review the SPEC-013 aggregate and proposed Wave A / Wave B / Watchlist.
2. If accepted, specify a zero-detail source-contract preflight for Wave A that
   does not modify production `config/companies.yaml` or Phase 2 state.
3. Separately decide whether to create a new candidate decision-preference
   version for `business_analytics` and `decision_support`.
4. Preserve the frozen semantic compute-worthiness result while source breadth
   is improved; do not tune semantic-v1.
5. Revisit compute allocation and the frozen SPEC-008 prospective protocol only
   after intake/routing evidence is better balanced.

## Known open decisions

- Whether to accept the proposed nine-employer Wave A and authorize its
  zero-detail source-contract preflight.
- Whether business/data/decision-analytics needs a bounded explicit
  decision-preference update.
- Deterministic rejection / stretch-envelope architecture after source coverage
  is better understood.
- Semantic-call budget for the later prospective ranking experiment.
- Durable private backup/retention for operational SQLite and detailed human
  evidence.
- Bounded semantic-call authority available to future agents.

## Explicitly do not build/tune yet

- semantic prompt/model/weight tuning;
- cheap secondary LLM routing;
- embeddings/vector search;
- learned ranking/ML infrastructure;
- autonomous preference learning;
- broad fuzzy clustering;
- production employer expansion before the audit is reviewed;
- UI/feed/control panel;
- application automation;
- external actions inferred from `APPLY`.
