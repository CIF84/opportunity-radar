# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-007-residual-diagnostics-market-normalization.md
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

Phases 1–3 are implemented. Phase 4 now has committed implementations for:

- versioned candidate market-access policy;
- post-detail `CurrentCandidateMarketStatus`;
- candidate-market routing and `UNCERTAIN -> REVIEW` cap;
- high-confidence employer-scoped opportunity clustering;
- candidate-dependent preferred variant;
- versioned taxonomy-backed decision preferences and bounded effects;
- explicit junior/graduate seniority guard;
- frozen offline retrospective replay tooling and sanitized experiment evidence.

The original Live Decision Validation remains historical evidence and is not
rewritten by Phase 4.

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

The committed SPEC-006 replay:

- accounted for all 30 postings;
- reused all 30 compatible semantic-v1 assessments;
- made zero semantic calls and zero live-source calls;
- collapsed 30 postings to 26 opportunity units;
- preserved 100% human-APPLY attention recall;
- produced 50% opportunity-level top-attention acceptance;
- produced 80.77% opportunity-level ranking agreement;
- produced 66.67% terminal APPLY acceptance;
- achieved 100% preferred-variant agreement for adjudicated variants;
- left five residual opportunity-level disagreements.

The 60% retrospective top-attention gate failed. The explicit-market gate also
failed because review 27, a Texas vacancy, remained `UNCERTAIN`; eight other
labeled foreign mismatches became `OUT_OF_SCOPE`.

Detailed replay rows and human-readable per-opportunity reports are private
local evidence and excluded from Git. The repository contains only sanitized
aggregate evidence, hashes, fingerprints, limitations, and conclusions.

## Residual cases to diagnose

Current work focuses on:

- review 27 — Texas market normalization defect;
- review 13 — advisory/execution preference residual;
- review 17 — orthopaedics preference residual;
- review 23 — Klaxoon market uncertainty + preference residual;
- review 10 — GoodData semantic-v1 control residual;
- review 18 — EY FP&A semantic-v1 control residual.

The goal is to distinguish deterministic normalization, generic matching,
appropriate uncertainty, unrepresented preference/conviction, and genuine
semantic-v1 residuals without tuning frozen policy.

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

These stages are implemented. The next product-level validation must be a new
prospective batch, not another relabeling of the frozen 30-case benchmark.

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

Ordinal preference state:

```text
STRONG_POSITIVE
POSITIVE
NEUTRAL
NEGATIVE
```

Frozen experimental effect mapping:

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

## Frozen items

During SPEC-007 do not change:

- model `gpt-5.6-luna`;
- reasoning effort `low`;
- semantic contract `phase3-semantic-v1`;
- Phase 3 scoring weights;
- candidate preference stances;
- preference effect mapping;
- clustering contract;
- seniority guard policy;
- historical judgments/batch membership;
- Phase 1 adapter contracts;
- Phase 2 lifecycle/exact-identity semantics;
- existing semantic cache records.

SPEC-007 may implement only a bounded evidence-supported market-normalization
correction and, if proven, a generic preference-matching correction that maps
existing job evidence to an already-approved preference concept. It must not add
new candidate preferences or convictions.

## Current gate

> Determine whether the remaining non-semantic replay disagreements are caused
> by bounded deterministic evidence/matching gaps or by genuinely unresolved
> policy, then decide whether the architecture is ready for a new prospective
> Phase 4 validation batch with semantic-v1 still frozen.

## Next intended steps

1. Execute SPEC-007 and rerun a clearly labeled corrected retrospective offline.
2. Review residual classification without retuning the result.
3. If ready, predeclare a prospective validation design and stopping rule.
4. Run a new prospective validation batch.
5. Only then decide whether `phase3-semantic-v2` is justified.

## Known open decisions

- Whether manual opportunity-cluster overrides are needed.
- Prospective Phase 4 batch size and stopping rule.
- Durable private backup/retention for SQLite, raw judgments, and detailed replay
  evidence.
- Bounded semantic-call authority available to future agents.

## Operational health snapshot

Last recorded repository evidence includes:

- SQLite schema version 3;
- 431 active and 1 closed persisted job instances at the prior operational
  snapshot;
- 406 Luna/low/semantic-v1 assessments at that snapshot;
- latest broad routing preflight: 56 `IN_SCOPE`, 265 `UNCERTAIN`, 85
  `OUT_OF_SCOPE`, with all 321 semantically processable jobs cache-compatible;
- clustering replay: 394 clusters from 406 assessed postings and a 315-cluster
  normal shortlist;
- SPEC-006 implementation validated with 199 offline tests and 18 live tests
  deselected before promotion.

These are time-bound observations, not hand-maintained runtime truth.

## Explicitly do not build yet

- semantic prompt/model/weight tuning;
- fuzzy/probabilistic clustering;
- autonomous preference learning;
- UI/feed/control panel;
- alerts/scheduling;
- application automation;
- external actions inferred from `APPLY`.
