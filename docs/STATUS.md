# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-010-prospective-sampling-cache-fix.md
```

Status: `APPROVED_FOR_IMPLEMENTATION`.

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

SPEC-009 completed a fresh normal 18-employer operational refresh with all
sources successful and complete, then stopped at the prospective semantic-budget
boundary. The refresh itself is valid. It exposed a preparation defect: current
rank-based sampling filters to compatible semantic-cache hits, so the nominal
40+20 zero-call sample is cache-biased and cannot be used as a prospective cost
or validation sample. SPEC-010 corrects only that preparation layer and the
mutable-operational-state-coupled replay test before any semantic spend.

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

SPEC-007 fixed one bounded evaluator-composition defect: explicit incompatible
Texas/California geography is respected even when work mode is unspecified. The
corrected replay changed exactly one reviewed market status/decision, moved the
explicit-market gate to PASS, and left recall, top-attention acceptance, and
ranking agreement unchanged. Reviews 10 and 18 remain semantic-v1 controls;
reviews 13 and 17 remain preference/conviction residuals without a justified
generic matcher correction; review 23 remains appropriately uncertain market
access.

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

Predeclared gates remain:

- human APPLY attention recall: 100%;
- top-attention acceptance: >=60%;
- ranking agreement: >=60%;
- terminal APPLY acceptance: >=60%;
- market-status agreement: >=90%;
- preferred-variant agreement: >=80%;
- confirmed false merges: 0.

The old-snapshot SPEC-008 preview was not prospective evidence. SPEC-009 now
provides the fresh operational state needed for the real preflight.

## SPEC-009 fresh operational state

Fresh refresh run `07c036f3-c512-4469-ada6-fe57bf9d337b`:

- status `COMPLETED`;
- 18/18 configured sources `SUCCESS` and complete;
- inventory 16,490;
- selected details 3,949;
- intentional skips 12,541;
- details fetched 3,949;
- detail failures 0;
- network detail requests 3,064;
- reused details 0 because previous successful details were older than the
  configured 168-hour refresh interval;
- resulting state: 3,977 ACTIVE, 120 CLOSED;
- 3,935 ACTIVE jobs with usable semantic title/description;
- semantic assessments remained 406 because semantic calls were not authorized.

The refresh inferred 3,665 newly discovered jobs, 119 newly closed jobs, and 23
materially changed jobs. Lifecycle inference was valid because all source
inventories were complete.

Fresh clustering/preflight population:

- 3,870 active OpportunityClusters;
- 3,326 normal candidate clusters before historical exclusion;
- 3,315 normal candidates after exclusion;
- market distribution 144 `IN_SCOPE`, 3,182 `UNCERTAIN`, 544 `OUT_OF_SCOPE`;
- compatible semantic cache hits 264;
- cache misses 3,606;
- full current routed semantic workload diagnostic 3,110 calls, estimated
  approximately $8.24, but full-population spending is not authorized or needed
  for the prospective experiment.

## Current prospective blocker

The frozen sampler mechanically returned 40 selected + 20 reserves with all 60
as cache hits, but this was caused by preparation filtering cache misses out of
the rank-based eligible population. Roughly 3,109 post-historical-exclusion
normal-route misses were silently absent from rank-based selection. Cache
availability therefore became a selection predicate.

In addition, 21/40 nominal selected items lacked a current recomputed
recommendation/tier even though their semantic-v1 payload remained compatible.
Current deterministic Phase 4 decisions need to be recomposed from current
observations/policies plus reusable semantic payloads rather than relying on
stale persisted decision fields.

SPEC-010 must fix these issues without changing the frozen sampling protocol or
making semantic calls. If semantic rank is mathematically required to assign a
cache miss to a frozen stratum and the protocol cannot support unbiased
selection without amendment, implementation must stop with `PROTOCOL CONFLICT —
HUMAN DECISION REQUIRED` rather than silently altering SPEC-008.

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

These stages are implemented. Prospective preparation must distinguish semantic
cache/execution state from sampling eligibility.

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

## Frozen items during SPEC-010

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
- existing semantic cache payloads.

SPEC-010 authorizes no live-source refresh and no semantic-model calls. It may
use the refreshed local SQLite state from SPEC-009 for zero-call preflight.

## Current gate

> Produce an unbiased zero-call prospective preflight in which semantic cache
> status is budget evidence rather than a sampling predicate, then stop with the
> exact selected and reserve semantic-call/cost budget for explicit approval.

## Next intended steps

1. Execute SPEC-010 preparation correction and zero-call fresh preflight.
2. If the frozen protocol is compatible, review the exact selected semantic-call
   count/cost plus reserve contingency.
3. Explicitly approve or reject semantic execution.
4. Only after approval assess selected cache misses and create the immutable
   prospective batch.
5. Collect all 40 cluster-level judgments without early stopping.
6. Evaluate the predeclared gates.
7. Only then decide whether preference-policy revision or
   `phase3-semantic-v2` is justified.

## Known open decisions

- Exact semantic-call/cost budget for prospective execution, pending SPEC-010.
- Any protocol amendment only if SPEC-010 proves semantic rank makes cache-miss
  sampling impossible under the frozen design.
- Whether manual opportunity-cluster overrides are needed after prospective
  cluster adjudication.
- Durable private backup/retention for SQLite, raw judgments, and detailed
  review evidence.
- Bounded semantic-call authority available to future agents.

## Operational health snapshot

Current local operational evidence after SPEC-009:

- SQLite schema version 3;
- 3,977 ACTIVE and 120 CLOSED jobs;
- 3,935 ACTIVE jobs with usable semantic detail;
- 406 persisted semantic-v1 assessments;
- 3,870 active clusters;
- 264 compatible cache hits and 3,606 misses across the fresh population;
- zero semantic calls during SPEC-009;
- zero prospective batch/judgments created.

The full offline suite after the refresh reported 231 passed, one failed, and 18
live tests deselected. The one failure is a retrospective residual-diagnostic
test coupled to the old mutable operational population of 406 assessable ACTIVE
jobs. SPEC-010 must move that expectation to frozen fixture/evidence without
weakening the original bounded/read-only/zero-call assertion.

## Explicitly do not build/tune yet

- semantic prompt/model/weight tuning;
- retrospective preference-effect tuning;
- fuzzy/probabilistic clustering;
- autonomous preference learning;
- UI/feed/control panel;
- alerts/scheduling;
- application automation;
- external actions inferred from `APPLY`.
