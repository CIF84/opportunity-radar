# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-008-prospective-validation-design.md
```

Status: `APPROVED_FOR_IMPLEMENTATION`.

Implementation agents must follow this pointer rather than infer work from file
recency. Before starting, verify the local working tree is clean and synchronize
with `origin/main` when safe. If unexplained changes, divergence, or conflicts
exist, stop and report them rather than overwriting or improvising.

The development authority boundary remains:

- agents may inspect, analyze, implement, and validate an approved work packet;
- implementation remains uncommitted while awaiting human/ChatGPT review;
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

Phases 1–3 are implemented. Phase 4 has committed implementations for:

- versioned candidate market-access policy;
- post-detail `CurrentCandidateMarketStatus`;
- candidate-market routing and `UNCERTAIN -> REVIEW` cap;
- high-confidence employer-scoped opportunity clustering;
- candidate-dependent preferred variant;
- versioned taxonomy-backed decision preferences and bounded effects;
- explicit junior/graduate seniority guard;
- frozen offline retrospective replay tooling and sanitized experiment evidence;
- bounded Texas/California market-composition correction and residual diagnostics.

The original Live Decision Validation and subsequent retrospective experiments
remain immutable historical evidence. The current gate is a new prospective
validation design, not further retrospective tuning.

## Historical validation baseline

Live Decision Validation batch `batch-20260826T210045Z-6492b09a`:

- reviewed: 30/30;
- verdict: `NO_GO`;
- strict APPLY recall: 100%;
- shortlist APPLY recall: 100%;
- top-attention acceptance: 35%;
- ranking agreement: 40%.

Canonical aggregate evidence remains under
`output/live_validation/batch-20260826T210045Z-6492b09a/`.

## Frozen Phase 4 retrospective result

SPEC-006:

- 30/30 postings accounted for;
- 30/30 compatible semantic-v1 assessments reused;
- zero semantic calls and zero live-source calls;
- 30 postings collapsed to 26 opportunity units;
- 100% human-APPLY attention recall;
- 50% opportunity-level top-attention acceptance;
- 80.77% opportunity-level ranking agreement;
- 66.67% terminal APPLY acceptance;
- 100% preferred-variant agreement for adjudicated variants.

The predeclared 60% top-attention gate failed. Detailed replay evidence remains
private/local; only sanitized aggregate evidence and provenance are tracked.

## Corrected residual diagnostic

SPEC-007 corrected the Texas case through a bounded evaluator-composition fix:
explicit incompatible geography is now respected even when work mode is
unspecified. The corrected replay preserved 100% APPLY attention recall, 50%
top-attention acceptance, and 80.77% ranking agreement while changing exactly
one reviewed market status/decision. The explicit-market gate moved from FAIL
to PASS.

Residual diagnosis after that correction:

- review 27 — fixed deterministic normalization;
- reviews 13 and 17 — unrepresented preference/conviction or frozen effect
  calibration; no generic matcher correction justified;
- review 23 — correctly uncertain market access, with separate product
  conviction not represented;
- reviews 10 and 18 — semantic-v1 residual controls.

No frozen preference effect or semantic-v1 behavior was tuned to improve the
retrospective result.

## Architecture direction

```text
complete inventory
  -> retrieval scope
  -> detail state
  -> current-candidate market status
  -> hard eligibility
  -> opportunity clustering / preferred variant
  -> semantic assessment
  -> preference-aware decision policy
  -> seniority guard
  -> deterministic composite / shortlist
```

These stages are implemented. The next product-level validation is prospective
and cluster-sampled.

## Confirmed candidate policy

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

Preferences are time-varying decision state, not immutable personality facts.
Future interaction evidence may support hypotheses but must not silently mutate
authoritative preference state.

## Frozen items for prospective validation design

Do not change:

- model `gpt-5.6-luna`;
- reasoning effort `low`;
- semantic contract `phase3-semantic-v1`;
- Phase 3 scoring weights;
- committed market-access policy and market-status rules;
- candidate preference stances;
- preference matching/effect mapping;
- clustering contract;
- seniority guard policy;
- recommendation thresholds;
- historical judgments/batch membership;
- Phase 1 adapter contracts;
- Phase 2 lifecycle/exact-identity semantics;
- existing semantic cache records.

## Current gate

> Predeclare and implement the preparation layer for a new prospective,
> opportunity-cluster-sampled Phase 4 validation before any new human judgments
> or semantic calls are made.

The prospective protocol must separate attention from application intent, sample
40 opportunity clusters across top, boundary, low-control, and market-control
strata, constrain employer concentration, freeze reserve/stopping rules, and
report semantic cache misses/cost before any paid execution is authorized.

## Next intended steps

1. Implement and review SPEC-008 prospective validation design/preparation.
2. Freeze/commit the protocol before creating the actual prospective batch.
3. Review the expected semantic-call and cost budget; explicitly authorize or
   reject paid execution.
4. Create the fresh prospective batch and collect 40 cluster-level judgments
   without early stopping.
5. Evaluate the predeclared gates.
6. Only then decide whether preference-policy revision or
   `phase3-semantic-v2` is justified.

## Known open decisions

- Final approval of the SPEC-008 prepared sampling protocol after seeing only
  population/preflight diagnostics, not human outcomes.
- Semantic-call/cost budget for the later prospective execution.
- Whether manual opportunity-cluster overrides are needed after prospective
  cluster adjudication.
- Durable private backup/retention for SQLite, raw judgments, and detailed
  review evidence.
- Bounded semantic-call authority available to future agents.

## Operational health snapshot

Last recorded repository evidence includes:

- SQLite schema version 3;
- 431 active and 1 closed persisted job instances at the prior operational
  snapshot;
- 406 Luna/low/semantic-v1 assessments at that snapshot;
- broad routing diagnostic after SPEC-007: 56 `IN_SCOPE`, 253 `UNCERTAIN`, 97
  `OUT_OF_SCOPE`, with all 309 semantically processable jobs cache-compatible;
- clustering replay: 394 clusters from 406 assessed postings and a 315-cluster
  normal shortlist;
- SPEC-007 validated with 216 offline tests and 18 live tests deselected.

These are time-bound observations, not hand-maintained runtime truth.

## Explicitly do not build yet

- semantic prompt/model/weight tuning;
- retrospective preference-effect tuning;
- fuzzy/probabilistic clustering;
- autonomous preference learning;
- UI/feed/control panel;
- alerts/scheduling;
- application automation;
- external actions inferred from `APPLY`.
