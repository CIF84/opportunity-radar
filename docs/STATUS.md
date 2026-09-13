# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-018-candidate-direction-promotion-audit.md
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

Phases 1–3 are implemented. Phase 4 now has committed implementations for candidate
market access/routing, opportunity clustering/preferred variant, versioned decision
preferences, seniority guard, retrospective replay, residual market normalization,
prospective-validation preparation, semantic compute-allocation audit, completed
human compute-worthiness validation, source-portfolio/role-coverage audit, Wave A
source-contract preflight, bounded production onboarding, generic nested feeds with
Mews, and corrected partial-geography market semantics.

Frozen recent milestones:

- SPEC-013 source portfolio audit: `a4ebba825e80256ad55ed6bfcaf973a2df37d413`
- SPEC-014 Wave A preflight: `11e000825e339de8c772d5bd7a66e2567469f1b2`
- SPEC-015 production onboarding: `541685ce40e959a66d2ec443b6ef748190713bb1`
- SPEC-016 nested feeds + Mews: `556fd7aec5d77874f56d7a5b5137a06a75fbfbca`
- SPEC-017 partial-geography semantics: `1871a082874f27db606796fc06e348fbee71776c`

SPEC-018 returns to the separately deferred candidate-direction question. It audits
whether repeated explicit human evidence justifies a new versioned decision-
preference representation. It must not inflate capability, tune semantic-v1, or
autonomously learn preferences.

## SPEC-017 frozen result

The `phase4-current-candidate-market-v3` evaluator now correctly distinguishes
partial compatible-country evidence from explicit city incompatibility:

```text
Prague hybrid                  -> IN_SCOPE
explicit Brno hybrid           -> OUT_OF_SCOPE
Czechia hybrid, city absent    -> UNCERTAIN
explicit Germany hybrid        -> OUT_OF_SCOPE
```

Read-only replay over 4,002 ACTIVE usable details produced exactly 26 changes:

```text
OUT_OF_SCOPE -> UNCERTAIN  26
OUT_OF_SCOPE -> IN_SCOPE    0
```

Affected employers: Wrike 13, Mews 11, ČSOB 1, Schneider Electric 1.
All 15 truth-table cases and 10 frozen historical market regressions passed.
Candidate policy did not change. Semantic calls were zero.

Mews now contributes 11 `UNCERTAIN` routed clusters including two deterministic
target-family signals. No job became confirmed `IN_SCOPE`.

## Candidate direction under SPEC-018

The candidate has explicitly confirmed that business/data/decision-analytics is a
viable direction when business-facing and aligned with AI/transformation work.

Current capability representation is already strong:

- `business_analytics`: EXPERT / HIGH;
- `decision_support`: EXPERT / HIGH;
- `forecasting`: EXPERT / HIGH;
- `business_operations`: EXPERT / HIGH;
- `commercial_strategy`: EXPERT / HIGH;
- `transformation`: ADVANCED / HIGH.

The candidate also has developing SQL/Python/technical depth. Those gaps must not
be hidden by preference promotion.

Current Phase 4 decision preferences already include:

```text
ai_enabled_work                    STRONG_POSITIVE
transformation_execution           STRONG_POSITIVE
implementation_ownership           STRONG_POSITIVE
business_operations                POSITIVE
product_development                POSITIVE
continuous_learning                POSITIVE
customer_service_operations        NEGATIVE
advisory_without_implementation     NEGATIVE
orthopaedics                        NEGATIVE
legacy_agency_sector                NEGATIVE (CONVICTION)
social_influencer_operations        NEGATIVE
```

SPEC-018 must determine whether explicit `business_analytics` / `decision_support`
preference promotion adds decision information or merely double-counts what is
already represented.

The completed human review also repeatedly distinguished:

- attractive manageable stretches in AI transformation/AI-enabled work;
- attractive domains with obviously excessive specialist gaps;
- strong aversion to returning to account-management/account-executive work;
- no intended career direction toward technical support;
- no intended direction toward generic testing/QA;
- negative sentiment toward mundane/highly automatable administrative work;
- openness to domains such as pharma/healthcare or robotics when role fit exists.

These are evidence for audit, not automatic permanent profile facts.

## SPEC-012 compute-worthiness evidence

The frozen 60-opportunity human experiment produced:

```text
WORTH_DEEP_ASSESSMENT      3
NOT_WORTH_DEEP_ASSESSMENT 57
NEED_MORE_INFO             0
```

All three WORTH cases occurred in `SEMANTIC_PRIORITY`. They shared a useful
qualitative pattern: desired trajectory was strong while qualification fit was
uncertain enough that deeper reasoning had decision value.

Many NOT_WORTH cases were either obvious functional/domain/seniority mismatches,
explicitly unwanted role families, decisive market incompatibilities, or roles
whose perceived future value was low.

SPEC-018 may inspect this evidence read-only. It must not modify the frozen sample
or judgments.

## Source portfolio state

Production sources now include Keboola, Commerzbank, KPMG, and Mews in addition
to the earlier portfolio.

SPEC-015 produced a modest breadth improvement. SPEC-016 added a reusable nested-
feed capability. SPEC-017 corrected the routing interpretation of incomplete
Czech city evidence.

No new source integration is authorized during SPEC-018.

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

## Frozen preference effect policy

```text
STRONG_POSITIVE -> +0.4
POSITIVE        -> +0.2
NEUTRAL         ->  0.0
NEGATIVE        -> -0.3
aggregate cap   -> [-1.0, +1.0]
```

SPEC-018 may not tune these values.

## Current gate

> Execute SPEC-018 as a zero-call candidate-direction audit. Promote a new
> preference version only if repeated explicit human evidence, narrow concept
> boundaries, counterfactual replay, and fingerprint/cache invariants all pass.

The audit must keep capability, preference, stretch, conviction, and hard
eligibility as distinct objects.

## SPEC-018 protected boundaries

Do not change:

- semantic-v1 model/prompt/reasoning/contract;
- Phase 3 scoring weights;
- market-access policy or market-status rules;
- source configuration;
- clustering semantics;
- seniority guard;
- historical judgments;
- semantic cache records;
- Phase 1/2 lifecycle/identity contracts.

No external semantic or live-source calls are authorized.

## Intended architecture

```text
SOURCE EVIDENCE
        ↓
HARD / MARKET ELIGIBILITY
        ↓
CAPABILITY FIT
        ↓
CAREER DIRECTION + PREFERENCES
        ↓
STRETCH / DECISION VALUE
        ↓
SEMANTIC COMPUTE ALLOCATION
        ↓
RANKED OPPORTUNITY FEED
```

Preferences should steer attention without rewriting capability truth.

## Direction after SPEC-018

Contingent on evidence:

1. review any candidate-preference promotion separately from capability facts;
2. preserve a versioned/reversible representation of changing sentiment;
3. design stretch-envelope logic only after its evidence contract is explicit;
4. then revisit deterministic hard-negative rejection and semantic allocation;
5. return to source expansion (Erste/Zentiva/Wave B) only as a separate portfolio decision;
6. preserve semantic-v1 until upstream decision architecture is validated.

## Known open decisions

- Whether SPEC-018 evidence justifies a new decision-preference version.
- How to represent manageable vs excessive stretch without conflating capability and preference.
- Deterministic rejection architecture after candidate direction is explicit.
- Semantic-call budget for later prospective ranking validation.
- Whether Erste or Zentiva receives the next source-contract repair packet.
- Durable private backup/retention for operational SQLite and detailed human evidence.

## Explicitly do not build/tune yet

- autonomous preference learning;
- stretch score/recommendation changes inside SPEC-018;
- semantic prompt/model/weight tuning;
- cheap secondary LLM routing;
- embeddings/vector search;
- learned ranking/ML infrastructure;
- broad fuzzy clustering;
- new source integrations;
- UI/feed/control panel;
- application automation;
- external actions inferred from `APPLY`.
