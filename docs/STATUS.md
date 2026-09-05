# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-011-semantic-compute-allocation-audit.md
```

Status: `IMPLEMENTED_LOCALLY_AWAITING_REVIEW`.

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

Phases 1–3 are implemented. Phase 4 has committed implementations for candidate
market access/routing, high-confidence opportunity clustering, preferred variant,
versioned decision preferences, seniority guard, retrospective replay, residual
market normalization, and the frozen prospective validation protocol.

SPEC-009 then executed the first unrestricted fresh 18-employer state refresh.
The refreshed operational state is complete and valid, but it exposed a product
architecture issue before prospective semantic spending: the current fresh
market contains thousands of routed semantic cache misses, while the frozen
rank-based sampler cannot rank those misses without first assessing them.

SPEC-010 correctly stopped with `PROTOCOL CONFLICT — HUMAN DECISION REQUIRED`
rather than silently biasing the sample toward cached jobs or changing the
frozen protocol.

SPEC-011 has now been implemented locally as a read-only semantic
compute-allocation audit. No Luna spend was authorized or used.

## SPEC-011 audit result

Run `semantic-allocation-audit-20260905-v3` evaluated the 3,315 routed,
post-historical-exclusion clusters against five simple cache-blind allocation
scenarios and the five frozen human-APPLY opportunity units.

- Baseline: 3,109 projected Luna calls, approximately `$8.2367`.
- Deterministic routing removes no additional clusters because it is already
  reflected in the routed baseline.
- Conservative obvious-role-family deferral retains all 5/5 historical APPLY
  units but removes only 27 clusters: 3,086 projected calls, `$8.1757`.
- Title-positive priority reduces the frame to 512 clusters / 489 projected
  calls, but retains only 3/5 historical APPLY units.
- Description-assisted positive evidence covers 85.1% of the population, still
  misses one historical APPLY unit, and leaves 2,701 projected calls.
- A 10% deterministic exploration scenario around title priority retains only
  3/5 historical APPLY units in this frozen draw.
- No audited policy reaches 1,000, 500, 250, or 100 calls while preserving all
  historical human-APPLY opportunities.

The audit therefore does **not** justify promoting a compute-allocation policy
or silently replacing prospective protocol v1. It supports a further bounded,
cache-blind human compute-worthiness labeling experiment before protocol v2.
Full protocol-v1 population completion remains an explicit alternative if the
human prioritizes immediate prospective validation over allocation learning.

The audit also recomposed all 247 post-exclusion compatible cached semantic
payloads into current deterministic Phase 4 decisions without rewriting cache
evidence or making external calls. The formerly mutable 406-job residual-test
expectation now lives in a frozen sanitized fixture.

## Fresh operational state from SPEC-009

Run `07c036f3-c512-4469-ada6-fe57bf9d337b`:

- status: `COMPLETED`;
- 18/18 sources successful and complete;
- inventory: 16,490;
- selected for detail: 3,949;
- intentionally skipped: 12,541;
- details fetched successfully: 3,949;
- detail failures: 0;
- network detail requests: 3,064;
- active jobs after refresh: 3,977;
- closed jobs: 120;
- active jobs with usable semantic detail: 3,935;
- existing semantic assessments remain 406;
- 23 previously known jobs materially changed and therefore no longer have a
  compatible semantic cache for current content.

All previously successful details were older than the 168-hour refresh interval,
so no selected details were reused during this refresh. JSON-feed and Phenom
sources retained their zero-network-detail advantage.

## Fresh prospective preflight finding

The fresh state contains:

- 3,870 active opportunity clusters;
- 3,326 normal candidate clusters before historical exclusion;
- 3,315 normal candidates after historical exclusion;
- market distribution: 144 `IN_SCOPE`, 3,182 `UNCERTAIN`, 544 `OUT_OF_SCOPE`;
- semantic cache: 264 compatible hits, 3,606 misses across the active cluster
  population;
- approximately 3,109 routed post-historical-exclusion cache misses relevant to
  the normal prospective population.

The frozen SPEC-008 sampler mechanically produced 40 selected + 20 reserves and
reported zero calls only because its rank-based candidate preparation admitted
semantic cache hits before sampling. This is cache-availability selection bias
and is not a valid prospective call budget.

Removing the cache-hit filter alone cannot solve the problem because the frozen
TOP/REVIEW/LOW strata require semantic score/recommendation values that cache
misses do not yet have. Full protocol-v1 population completion would require
approximately 3,109 Luna calls at an estimated cost around $8.24.

## Why the full semantic spend is deferred

The ~$8 bootstrap cost is financially modest but exposes a more important
product question. Opportunity Radar should not assume that every plausible
vacancy deserves the same expensive reasoning merely so a small attention set
can be ranked.

The desired architecture is closer to:

```text
complete market observation
  -> cheap deterministic scope/triage
  -> bounded plausible/uncertain opportunity set
  -> expensive semantic reasoning where decision value justifies it
  -> ranked human attention
```

The current packet tests how far pre-semantic evidence can reduce the ~3,109
routed cache misses without losing known human-APPLY opportunities. It must not
use cache availability as a relevance feature and must not call an external
model.

## Historical validation baseline

Live Decision Validation batch `batch-20260826T210045Z-6492b09a` remains
immutable historical evidence:

- 30/30 reviewed;
- verdict `NO_GO`;
- strict/shortlist APPLY recall 100%;
- top-attention acceptance 35%;
- ranking agreement 40%.

Phase 4 retrospective replay with frozen semantic-v1 improved opportunity-level
ranking agreement to 80.77% and top-attention acceptance to 50% while preserving
100% APPLY attention recall. SPEC-007 fixed the explicit Texas market defect
without changing those metrics. Reviews 10 and 18 remain semantic-v1 controls;
reviews 13/17 are preference/conviction residuals; review 23 remains appropriate
market uncertainty.

## Prospective validation protocol

SPEC-008 v1 remains frozen historical protocol evidence:

- 40 OpportunityClusters;
- strata 15 top / 10 boundary / 10 low / 5 market controls;
- five reserves per stratum;
- employer caps;
- deterministic seed/fallback/blind order;
- historical overlap exclusion;
- no early stopping.

Its predeclared gates remain unchanged. The protocol is **not** being silently
modified during SPEC-011. The audit will recommend whether to pay for full v1
population completion, create a separately versioned v2 compute-allocation
protocol, or run another bounded experiment first.

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

## Frozen items during SPEC-011

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
- SPEC-008 prospective protocol v1;
- historical judgments/batch membership;
- Phase 1 adapter contracts;
- Phase 2 lifecycle/exact-identity semantics;
- existing semantic cache records.

No semantic calls or live refresh are authorized in SPEC-011.

## Current gate

> Decide whether to freeze a bounded cache-blind human labeling experiment for
> semantic compute-worthiness, or explicitly fund full protocol-v1 population
> completion despite the unresolved long-term allocation architecture.

Historical APPLY recall is a necessary but insufficient condition because the
review corpus is small and biased. No compute-allocation policy is promoted from
this audit alone.

## Next intended steps

1. Review the SPEC-011 aggregate receipt and implementation.
2. Decide whether to:
   - complete semantic population under prospective protocol v1;
   - freeze a bounded cache-blind human compute-worthiness labeling experiment;
   - or design a separately versioned protocol v2 only after stronger evidence.
3. Only then authorize semantic spend or a new validation packet.
4. Prospective human validation remains the evidence needed before semantic-v1
   or preference-policy tuning.

## Known open decisions

- Whether to run the recommended bounded human-labeling experiment or fund full
  v1 semantic completion.
- Compute-allocation architecture and prospective protocol version after that
  decision.
- Semantic-call/cost budget after an unbiased bounded frame exists.
- Whether manual opportunity-cluster overrides are needed after prospective
  cluster adjudication.
- Durable private backup/retention for SQLite, raw judgments, and detailed
  review evidence.
- Bounded semantic-call authority available to future agents.

## Operational/test note

The historical 406-job residual-diagnostic expectation is preserved in a
sanitized frozen test fixture. Current operational-corpus diagnostics continue
to use the mutable read-only database without treating its size as historical
truth.

## Explicitly do not build/tune yet

- semantic prompt/model/weight tuning;
- retrospective preference-effect tuning;
- cheap secondary LLM routing;
- embeddings/vector search;
- learned ranking/ML infrastructure;
- fuzzy/probabilistic clustering;
- autonomous preference learning;
- UI/feed/control panel;
- alerts/scheduling;
- application automation;
- external actions inferred from `APPLY`.
