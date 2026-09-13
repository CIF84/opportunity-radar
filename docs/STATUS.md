# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-019-stretch-evidence-boundary.md
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
Mews, corrected partial-geography market semantics, and bounded candidate-direction
promotion.

Frozen recent milestones:

- SPEC-013 source portfolio audit: `a4ebba825e80256ad55ed6bfcaf973a2df37d413`
- SPEC-014 Wave A preflight: `11e000825e339de8c772d5bd7a66e2567469f1b2`
- SPEC-015 production onboarding: `541685ce40e959a66d2ec443b6ef748190713bb1`
- SPEC-016 nested feeds + Mews: `556fd7aec5d77874f56d7a5b5137a06a75fbfbca`
- SPEC-017 partial-geography semantics: `1871a082874f27db606796fc06e348fbee71776c`
- SPEC-018 candidate direction: `34fdd1b601309a025ec72af6a4275f1dcfc72dde`

SPEC-019 is a zero-call diagnostic experiment defining the evidence boundary between
current fit, manageable stretch, excessive stretch, and unresolved capability
distance. It must not change runtime ranking/recommendation behavior.

## SPEC-018 frozen result

One narrowly supported preference was promoted:

```text
account_management_execution  PREFERENCE  NEGATIVE
```

Candidate profile is now version 4 and decision preferences version 2. Matching is
title-only and does not penalize sales/revenue operations, commercial strategy,
retention strategy, business development, or descriptions merely mentioning account
managers.

Counterfactual evidence before promotion:

```text
frozen 60-item sample          4 matches, all NOT_WORTH, 0 WORTH demotions
compatible cached population  1/20 affected, 1 score change, 0 recommendation changes
frozen Phase 4 retrospective  0/30 affected
semantic reassessments         0
```

Business analytics, decision intelligence, AI transformation, and implementation
ownership were already represented sufficiently. Broader automation-risk, QA/testing,
technical-support, and mundane-administration preferences were not promoted.

Two frozen SPEC-007 replay tests intentionally skip when the current decision-policy
identity differs from their historical frozen identity. They are explicit identity-
mismatch safeguards, not broken tests.

## Why SPEC-019 exists

The frozen 60-opportunity compute-worthiness experiment found only three human
`WORTH_DEEP_ASSESSMENT` cases. Their useful qualitative pattern was:

```text
desired trajectory is strong
+
qualification fit is uncertain but plausibly bridgeable
=
deep reasoning has decision value
```

Many NOT_WORTH cases instead had explicit core professional/domain/seniority gaps
requiring substantial requalification. Others were rejected only for preference or
market reasons and must not be mislabeled as excessive capability stretch.

SPEC-019 tests whether explicit evidence can safely separate:

```text
CURRENT_FIT
MANAGEABLE_STRETCH
EXCESSIVE_STRETCH
UNRESOLVED
```

without using preference as a proxy for capability.

## Stretch conceptual boundary

Stretch is a capability-distance object only.

Examples:

- an account-management role may be `CURRENT_FIT` but unattractive;
- an AI-transformation role may be `MANAGEABLE_STRETCH` and attractive;
- a senior ML-engineer role may be `EXCESSIVE_STRETCH` even if attractive;
- a US-only role may be market-ineligible independently of stretch;
- a mundane HR-data role may be current-fit/manageable but unattractive.

SPEC-019 must keep market eligibility, capability, preference, stretch, semantic
compute worthiness, and recommendation as independent objects.

## Candidate capability baseline

Current candidate capability evidence includes:

- `business_analytics`: EXPERT / HIGH;
- `decision_support`: EXPERT / HIGH;
- `forecasting`: EXPERT / HIGH;
- `business_operations`: EXPERT / HIGH;
- `commercial_strategy`: EXPERT / HIGH;
- `transformation`: ADVANCED / HIGH;
- `ai_strategy` / `ai_adoption`: INTERMEDIATE;
- SQL/Python/software architecture/product development: developing or intermediate as configured.

Interest in learning a skill must not upgrade capability evidence.

## SPEC-012 human evidence

Frozen labels:

```text
WORTH_DEEP_ASSESSMENT      3
NOT_WORTH_DEEP_ASSESSMENT 57
NEED_MORE_INFO             0
```

The audit must not treat all 57 NOT_WORTH items as excessive stretch. Human reasons
must be separated into stretch-related, preference-only, market-only, unavailable/
insufficient-evidence, and other categories.

All three WORTH cases are protected: a tested deterministic rule set that classifies
one as `EXCESSIVE_STRETCH` must stop for review rather than being broadened/tuned
around the example.

## SPEC-017 market semantics

Market policy remains independent and unchanged:

```text
Prague hybrid                  -> IN_SCOPE
explicit Brno hybrid           -> OUT_OF_SCOPE
Czechia hybrid, city absent    -> UNCERTAIN
explicit Germany hybrid        -> OUT_OF_SCOPE
```

Market incompatibility must not masquerade as capability stretch.

## Source portfolio state

Production sources include the original portfolio plus Keboola, Commerzbank, KPMG,
and Mews. No new source integration is authorized during SPEC-019.

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

> Execute SPEC-019 as a diagnostic zero-call stretch-evidence audit. Do not filter,
> rank, cap, reject, or promote opportunities differently based on stretch in this
> packet.

The key question is whether cheap explicit evidence can identify obvious outer
boundaries while preserving the interesting ambiguous middle for semantic reasoning.

## SPEC-019 protected boundaries

Do not change:

- candidate profile/capabilities/preferences;
- market policy/status semantics;
- source configuration/adapters;
- semantic-v1 model/prompt/reasoning/contract;
- Phase 3 scoring weights;
- decision-preference effect weights;
- clustering semantics;
- seniority guard;
- historical judgments;
- semantic assessments/cache;
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
STRETCH DISTANCE
        ↓
SEMANTIC COMPUTE ALLOCATION
        ↓
RANKED OPPORTUNITY FEED
```

A later deterministic rejection layer may combine independently validated negative
evidence, but SPEC-019 implements only the stretch audit contract.

## Direction after SPEC-019

Contingent on evidence:

1. review whether stretch classes are precise enough for a later runtime experiment;
2. if safe, combine only independently validated hard negatives in a separate deterministic-rejection packet;
3. compare resulting compute-allocation economics against SPEC-011/012;
4. preserve a control/exploration path before suppressing semantic reasoning broadly;
5. return to source expansion only as a separate portfolio decision;
6. keep semantic-v1 frozen until the upstream allocation architecture is validated.

## Known open decisions

- Whether stretch evidence can safely support a later runtime boundary.
- Deterministic rejection architecture after stretch validation.
- Exploration/control rate for any future compute-allocation gate.
- Semantic-call budget for later prospective ranking validation.
- Whether Erste or Zentiva receives a future source-contract repair packet.
- Durable private backup/retention for operational SQLite and detailed human evidence.

## Explicitly do not build/tune yet

- runtime stretch score/caps/recommendations;
- combined deterministic rejection;
- autonomous preference learning;
- semantic prompt/model/weight tuning;
- cheap secondary LLM routing;
- embeddings/vector search;
- learned ranking/ML infrastructure;
- broad fuzzy clustering;
- new source integrations;
- UI/feed/control panel;
- application automation;
- external actions inferred from `APPLY`.
