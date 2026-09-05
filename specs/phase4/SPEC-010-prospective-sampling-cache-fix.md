# SPEC-010 — Prospective Sampling Cache Eligibility Correction

## Status

`APPROVED_FOR_IMPLEMENTATION`

## Purpose

Fix the prospective-preparation defect discovered by SPEC-009 before any
semantic budget is authorized or any prospective batch is created.

The refreshed operational state is valid and complete. The blocker is in the
prospective preparation layer: rank-based sampling currently admits only items
with a compatible semantic cache hit, which silently excludes current cache
misses from the eligible prospective population and creates cache-availability
selection bias.

This packet authorizes only the deterministic preparation corrections required
to obtain an honest zero-call prospective preflight and exact future semantic
budget.

Before implementation read:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING_MODEL.md`
- `experiments/phase4_prospective_validation_v1.yaml`
- SPEC-008 and SPEC-009
- current prospective preparation/sampling code
- current semantic cache/recomposition contracts

## Frozen facts from SPEC-009

Fresh completed state refresh:

- run ID `07c036f3-c512-4469-ada6-fe57bf9d337b`;
- 18/18 sources successful and complete;
- 16,490 inventory references;
- 3,949 selected details, all fetched successfully;
- 3,977 ACTIVE jobs;
- 3,935 ACTIVE jobs with usable semantic detail;
- 406 persisted semantic assessments;
- 3,870 active OpportunityClusters;
- 3,326 normal candidate clusters before historical exclusion;
- 3,315 after historical exclusion.

Fresh semantic-cache population:

- compatible hits: 264;
- misses: 3,606;
- 3,110 routed semantic calls would be required for the full current population.

The nominal frozen sampler produced 40 selected + 20 reserves with 60/60 cache
hits only because cache misses were filtered out before rank-based sampling.
That zero-call result is invalid as a prospective budget estimate.

## Objective

After this packet, prospective preparation must:

1. deterministically recompose current candidate decisions from reusable cached
   semantic payloads against current observations/policies;
2. retain semantically assessable cache misses in the eligible prospective
   population rather than excluding them;
3. rank/sample cache hits and misses under one unbiased frozen population model;
4. report selected/reserve cache hits and misses honestly without calling the
   semantic provider;
5. produce an exact prospective semantic-call count and estimated cost suitable
   for explicit human authorization;
6. decouple retrospective/residual tests from the mutable operational database
   by using frozen fixture/evidence inputs.

No prospective semantic calls or batch creation are authorized.

## Non-goals

Do NOT:

- call Luna/OpenAI/any semantic provider;
- change `gpt-5.6-luna`, `low`, or `phase3-semantic-v1`;
- change Phase 3 weights/recommendation thresholds;
- change candidate market policy, preference state/effects, clustering, or
  seniority policy;
- change SPEC-008 protocol, strata, seed, reserves, employer caps, gates, or
  stopping rules;
- rerun the 18-employer source refresh unless strictly required to verify a
  deterministic local implementation and explicitly reported first;
- create the actual prospective `batch.json`;
- collect human judgments;
- pre-assess the full 3,110-call routed population;
- broaden semantic eligibility to jobs lacking usable detail;
- mutate historical v1/Phase 4 replay evidence.

## A. Current-decision recomposition

A compatible semantic assessment is reusable semantic evidence, not necessarily
an up-to-date persisted final decision after a fresh observation/policy state.

Implement/reuse a pure deterministic recomposition path that takes:

- current JobObservation/normalized job evidence;
- current candidate profile and policy fingerprints;
- current market assessment;
- current hard eligibility;
- current cluster/preferred-variant evidence;
- compatible cached semantic-v1 assessment when present;
- current frozen preference policy;
- current seniority guard;

and derives the current Phase 4 decision/ranking evidence without a semantic
call or rewriting the cached semantic payload.

For compatible cache hits, preparation must use this recomposed current result
rather than requiring a stale persisted recommendation/tier field. This should
resolve the SPEC-009 observation that 21/40 nominal selected items lacked a
current recomputed recommendation/tier despite reusable semantics.

Do not overwrite semantic assessments merely to materialize recomposed decision
fields.

## B. Cache-miss prospective eligibility

A cache miss must remain eligible for prospective sampling when all
pre-semantic requirements are satisfied.

Separate at least conceptually:

```text
PRE_SEMANTIC_ELIGIBLE
SEMANTIC_CACHE_HIT
SEMANTIC_CACHE_MISS
UNASSESSABLE_PRE_SEMANTIC
```

Rank-based prospective sampling cannot simply discard `SEMANTIC_CACHE_MISS`.

For cache misses, derive whatever deterministic pre-semantic routing/cluster
information is available and preserve them in the eligible sampling frame.

Because the final semantic score is not yet known, do not invent one.

The frozen SPEC-008 protocol must be applied in a way that does not condition
selection on cache availability. Use the minimal deterministic design consistent
with the committed protocol. If the existing protocol assumes a fully semantic-
ranked population and cannot admit unknown semantic scores without altering the
sampling contract, stop and report a protocol-design conflict rather than
silently choosing a new sampling rule.

Preferred outcome: implement the already-intended two-stage deterministic
preparation in which rankable cache hits retain their actual frozen ranking and
cache misses remain in the appropriate eligible pool/reserve mechanics without
being removed because of cost/cache status. Document exact behavior and prove
that cache status is not a selection predicate.

## C. No cache-status selection bias

Add explicit diagnostics/tests proving:

- changing an otherwise identical item's cache status HIT -> MISS does not make
  it ineligible solely for that reason;
- cache state is recorded only as execution-budget evidence;
- historical-overlap exclusion, market routing, employer caps, strata logic,
  seed, and deterministic fallback remain independent of cache status;
- the prepared sample can contain misses;
- no hidden fallback replaces a selected miss with a cached item merely to
  reduce cost.

If the frozen stratum definition itself mathematically depends on semantic rank
and cannot classify a miss, report the exact conflict and propose the smallest
protocol amendment as a separate human decision. Do not amend SPEC-008 inside
this implementation without approval.

## D. Exact zero-call budget preflight

After correction, run a zero-call preview against the current refreshed SQLite
state from SPEC-009.

Report separately for:

### Selected 40

- total;
- cache hits;
- cache misses;
- exact semantic calls required before final batch decision evidence is
  complete;
- estimated cost;
- unassessable pre-semantic items.

### Reserves 20

- total;
- cache hits;
- cache misses;
- contingent calls/cost if reserve items are activated;
- unassessable pre-semantic items.

### Full eligible population

- pre-semantic eligible clusters;
- hit/miss counts;
- routed call count;
- excluded/unassessable reasons.

No actual semantic calls may occur.

## E. Cost estimate integrity

Use the committed estimator/model identity. Record:

- model `gpt-5.6-luna`;
- reasoning `low`;
- contract `phase3-semantic-v1`;
- estimator/version assumptions;
- selected required-call estimate;
- reserve contingent estimate;
- full-population diagnostic estimate only as context.

The human approval boundary concerns selected calls/cost (plus clearly labeled
reserve contingency), not the cost of assessing the entire population.

## F. Mutable-database test correction

Fix the failing residual diagnostic test
`test_corrected_replay_is_zero_call_read_only_and_bounded` so historical or
bounded replay expectations do not depend on the current mutable operational
SQLite population.

Use frozen fixture/evidence appropriate to the retrospective contract.

Requirements:

- do not weaken the assertion merely to accept 3,935;
- preserve the original intent: corrected replay is bounded, read-only, and
  zero-call;
- make the test deterministic across future normal state refreshes;
- do not copy sensitive/private detailed replay evidence into Git fixtures.

Prefer sanitized frozen fixture/aggregate inputs already allowed by the evidence
policy.

## G. Persistence and privacy

No SQLite migration expected.

Do not persist derived current recommendations solely to support preparation
unless an existing committed repository contract already requires it. Prefer
pure recomposition.

Detailed preview/sample identities remain private/local and Git-ignored.
Repository-safe output may contain only sanitized aggregate counts,
fingerprints, cost/call budgets, hashes, limitations, and conclusions.

Do not commit the operational SQLite database.

## H. Regression requirements

Tests must prove at least:

1. compatible cached semantic payload can be recomposed to a current Phase 4
   decision after a fresh observation without semantic reassessment;
2. recomposition preserves semantic assessment identity;
3. miss is not excluded solely because it is a miss;
4. changing hit/miss status alone does not alter pre-semantic eligibility;
5. selected sample is not guaranteed/all-forced to cache hits;
6. zero-call preview reports misses without executing them;
7. selected required-call count equals selected compatible misses that require
   semantics under the protocol;
8. reserve contingent count is separate;
9. frozen protocol fingerprint/seed/strata/caps remain unchanged;
10. no prospective batch is created;
11. retrospective bounded test uses frozen evidence rather than mutable DB size;
12. official historical evidence remains unchanged;
13. SQLite schema remains version 3;
14. external semantic transport call count is zero.

## I. Validation

Run:

```bash
.venv/bin/pytest -q
git diff --check
```

Then run the corrected prospective zero-call preview against the refreshed local
state.

Do not refresh live sources merely because implementation tests need data; use
the SPEC-009 refreshed local state for the operational preflight.

## J. Stop condition

Stop after producing an honest selected/reserve semantic budget.

Do not spend it.

The deliverable must end with an explicit approval request of the form:

```text
Selected prospective sample requires X Luna calls at estimated cost $Y.
Frozen reserves would require up to R additional calls at estimated contingent
cost $Z if replacements are activated.
Approve semantic execution: YES / NO.
```

If the frozen protocol cannot honestly sample cache misses because semantic rank
is required to define strata, stop instead with:

```text
PROTOCOL CONFLICT — HUMAN DECISION REQUIRED
```

and explain the smallest possible amendment. Do not make semantic calls.

## Deliverable

Return:

A. root cause confirmed/refined
B. files changed
C. recomposition contract
D. cache-miss eligibility behavior
E. proof cache state is not a selection predicate
F. frozen protocol compatibility or exact conflict
G. corrected selected 40 hit/miss/call/cost budget
H. corrected reserves 20 hit/miss/contingent budget
I. full eligible-population diagnostics
J. mutable-database test correction
K. privacy/persistence confirmation
L. full validation result
M. zero external-call proof
N. exact human semantic-spend approval required next
O. recommended commit message

Do not commit or push until explicit approval.
