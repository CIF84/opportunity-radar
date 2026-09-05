# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-009-fresh-state-refresh-prospective-preflight.md
```

Status: `APPROVED_FOR_EXECUTION`.

Implementation/operations agents must follow this pointer rather than infer work
from file recency. Before starting, verify the local working tree is clean and
synchronize with `origin/main` when safe. If unexplained changes, divergence, or
conflicts exist, stop and report them rather than overwriting or improvising.

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

Phases 1–3 are implemented. Phase 4 has committed implementations for:

- versioned candidate market-access policy;
- post-detail `CurrentCandidateMarketStatus`;
- candidate-market routing and `UNCERTAIN -> REVIEW` cap;
- high-confidence employer-scoped opportunity clustering;
- candidate-dependent preferred variant;
- versioned taxonomy-backed decision preferences and bounded effects;
- explicit junior/graduate seniority guard;
- frozen offline retrospective replay tooling and sanitized experiment evidence;
- bounded Texas/California market-composition correction and residual diagnostics;
- frozen prospective validation protocol and deterministic preparation/preflight
  tooling.

The prospective protocol is committed at `e69d1fc`. No prospective batch or new
prospective judgments exist yet. The current packet authorizes a fresh normal
18-employer state refresh plus a zero-semantic-call prospective preflight only.

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

## Phase 4 retrospective evidence

SPEC-006 froze and replayed the 30 cases with zero semantic calls. It produced
100% human-APPLY attention recall, 50% opportunity-level top-attention
acceptance, 80.77% opportunity-level ranking agreement, 66.67% terminal APPLY
acceptance, and 100% preferred-variant agreement for adjudicated variants.

SPEC-007 then fixed one bounded evaluator-composition defect: explicit
incompatible Texas/California geography is respected even when work mode is
unspecified. The corrected replay changed exactly one reviewed market
status/decision, moved the explicit-market gate to PASS, and left recall,
top-attention acceptance, and ranking agreement unchanged. Reviews 10 and 18
remain semantic-v1 controls; reviews 13 and 17 remain preference/conviction
residuals without a justified generic matcher correction; review 23 remains
appropriately uncertain market access.

Detailed replay evidence remains private/local; repository evidence is sanitized
aggregate/provenance only.

## Prospective validation protocol

SPEC-008 froze the prospective design before any new human outcomes:

- 40 OpportunityClusters;
- strata: 15 top attention / 10 decision boundary / 10 low controls / 5 market
  controls;
- five frozen reserves per stratum;
- maximum four normal items per employer;
- maximum one market control per employer;
- deterministic seed, fallback order, blind review order, and reserve policy;
- historical reviewed-member overlap excluded;
- no human labels influence selection;
- `NEED_MORE_INFO` remains distinct;
- no early stopping;
- unavailable items use same-stratum frozen reserves.

Predeclared gates:

- human APPLY attention recall: 100%;
- top-attention acceptance: >=60%;
- ranking agreement: >=60%;
- terminal APPLY acceptance: >=60%;
- market-status agreement: >=90%;
- preferred-variant agreement: >=80%;
- confirmed false merges: 0.

The old-snapshot diagnostic preview filled all 40 selections and 20 reserves
with zero employer-cap relaxations and projected 40/40 + 20/20 compatible
semantic cache hits. That preview is not prospective evidence. The current
packet refreshes market state and recomputes this preflight before any semantic
budget is authorized.

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

## Frozen items during SPEC-009

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
- SPEC-008 prospective protocol, seed, strata, reserves, employer caps, gates,
  and stopping rules;
- historical judgments/batch membership;
- Phase 1 adapter contracts;
- Phase 2 lifecycle/exact-identity semantics;
- existing semantic cache records.

SPEC-009 authorizes public employer source retrieval and normal state mutation
through the committed state runner. It does not authorize semantic calls,
prospective batch creation, or judgments.

## Current gate

> Refresh the complete 18-employer operational state, rerun the frozen
> prospective preflight, and stop with an exact semantic-call/cost budget for
> explicit human authorization.

## Next intended steps

1. Execute SPEC-009 fresh state refresh and prospective preflight.
2. Review source completeness and the fresh selected/reserve sample composition.
3. Explicitly approve or reject the reported semantic call count and estimated
   cost.
4. Only after approval assess required cache misses and create the immutable
   prospective batch.
5. Collect all 40 cluster-level judgments without early stopping.
6. Evaluate the predeclared gates.
7. Only then decide whether preference-policy revision or
   `phase3-semantic-v2` is justified.

## Known open decisions

- Semantic-call/cost budget for prospective execution, pending fresh preflight.
- Whether manual opportunity-cluster overrides are needed after prospective
  cluster adjudication.
- Durable private backup/retention for SQLite, raw judgments, and detailed
  review evidence.
- Bounded semantic-call authority available to future agents.

## Operational health snapshot

Last committed/preparation evidence before the fresh refresh includes:

- SQLite schema version 3;
- 431 active and 1 closed persisted job instances at the prior snapshot;
- 406 Luna/low/semantic-v1 assessments at that snapshot;
- broad routing diagnostic after SPEC-007: 56 `IN_SCOPE`, 253 `UNCERTAIN`, 97
  `OUT_OF_SCOPE`, with all 309 semantically processable jobs cache-compatible;
- clustering replay: 394 clusters from 406 assessed postings and a 315-cluster
  normal shortlist;
- SPEC-008 old-snapshot preview: 394 active detailed clusters, 26 historical
  overlap exclusions, 40/40 selected and 20/20 reserves filled, zero employer
  cap relaxations, zero projected semantic calls/cost;
- SPEC-008 preparation validated with 232 offline tests and 18 live tests
  deselected.

These are time-bound observations, not hand-maintained runtime truth.

## Explicitly do not build/tune yet

- semantic prompt/model/weight tuning;
- retrospective preference-effect tuning;
- fuzzy/probabilistic clustering;
- autonomous preference learning;
- UI/feed/control panel;
- alerts/scheduling;
- application automation;
- external actions inferred from `APPLY`.
