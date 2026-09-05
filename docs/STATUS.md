# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-012-semantic-compute-worthiness-human-validation.md
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

Phases 1–3 are implemented. Phase 4 has committed implementations for candidate
market access/routing, high-confidence opportunity clustering, preferred variant,
versioned decision preferences, seniority guard, retrospective replay, residual
market normalization, frozen prospective validation preparation, and semantic
compute-allocation audit tooling.

SPEC-009 executed the first unrestricted fresh 18-employer state refresh.
SPEC-010 correctly stopped when the frozen rank-based prospective protocol was
found to require semantic assessment before unbiased sampling. SPEC-011 then
audited whether cheap deterministic evidence could solve that allocation problem.
It could not do so safely enough to promote a runtime policy.

The current packet prepares a new, bounded human experiment: label whether deep
semantic reasoning is **worth spending** on 60 cache-blind opportunity clusters.
It does not call Luna and does not modify the frozen SPEC-008 prospective
protocol.

## SPEC-011 audit result

Run `semantic-allocation-audit-20260905-v3`:

- routed post-historical-exclusion clusters: 3,315;
- compatible cache hits: 206;
- semantic cache misses: 3,109;
- full semantic completion projection: ~$8.2367;
- conservative obvious-role-family deferral: 3,086 calls / ~$8.1757 while
  preserving 5/5 historical human-APPLY units;
- title-positive priority: 489 calls / ~$1.2955 but only 3/5 historical APPLY
  units retained;
- description-assisted lexical positive evidence: 2,701 calls / ~$7.1558 and
  only 4/5 historical APPLY units retained;
- title priority plus 10% deterministic exploration: 754 calls / ~$1.9976 and
  only 3/5 historical APPLY units retained.

No audited interpretable policy reached <=1,000, <=500, <=250, or <=100 calls
while retaining all known historical human-APPLY opportunity units. Therefore
no compute-allocation policy was promoted.

The unpromoted audit triage distribution was:

```text
SEMANTIC_PRIORITY  512
SEMANTIC_OPTIONAL  2,776
SEMANTIC_DEFER     27
```

Cache status is not an input to this triage.

SPEC-011 also proved that compatible cached semantic payloads can be recomposed
against current market/preference/seniority/scoring policy with zero external
calls and without rewriting semantic evidence.

## Why SPEC-012 exists

The next uncertainty is no longer “can we invent more keywords?” It is whether
the cheap triage categories correspond to the human judgment that matters for
compute allocation:

> Would deeper AI reasoning on this opportunity be worth the compute before
> deciding whether it deserves attention?

SPEC-012 freezes a 60-opportunity human labeling experiment across PRIORITY,
OPTIONAL, and DEFER. This evidence can tell us whether deterministic triage is
worth further development, whether a cheap learned/model-based screen is
justified, or whether full Luna assessment is simpler and safer at current
scale/cost.

These labels are experiment evidence, not APPLY/DONT_APPLY judgments and not
automatic preference updates.

## Fresh operational state from SPEC-009

Run `07c036f3-c512-4469-ada6-fe57bf9d337b`:

- status: `COMPLETED`;
- 18/18 sources successful and complete;
- inventory: 16,490;
- selected for detail: 3,949;
- active jobs after refresh: 3,977;
- closed jobs: 120;
- active jobs with usable semantic detail: 3,935;
- existing semantic assessments: 406.

The routed prospective population after historical exclusion contains 3,315
clusters, of which approximately 3,109 lack compatible semantic-v1 assessment.

## Historical validation baseline

Live Decision Validation v1 remains immutable:

- 30/30 reviewed;
- verdict `NO_GO`;
- strict/shortlist APPLY recall 100%;
- top-attention acceptance 35%;
- ranking agreement 40%.

Phase 4 retrospective replay improved opportunity-level ranking agreement to
80.77% and top-attention acceptance to 50% while preserving 100% APPLY attention
recall. The later bounded market correction changed exactly one reviewed market
decision and moved the explicit-market gate to PASS without tuning semantic-v1.

## Prospective validation protocol

SPEC-008 v1 remains frozen and unchanged:

- 40 OpportunityClusters;
- strata 15 top / 10 boundary / 10 low / 5 market controls;
- five reserves per stratum;
- employer caps;
- deterministic seed/fallback/blind order;
- historical overlap exclusion;
- no early stopping.

It remains blocked by the semantic-population/sampling circularity. SPEC-012 is a
separate experiment and does not silently replace it.

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

## Frozen items during SPEC-012

Do not change:

- Luna / low / `phase3-semantic-v1`;
- Phase 3 scoring weights;
- market-access policy and market-status rules;
- candidate preferences or effect mapping;
- clustering contract;
- seniority guard;
- recommendation thresholds;
- SPEC-008 prospective protocol v1;
- SPEC-011 triage definition while sampling/labeling;
- historical judgments/batch membership;
- Phase 1/2 contracts;
- existing semantic cache records.

No semantic calls or live source calls are authorized.

## Current gate

> Prepare and then human-label a cache-blind, employer-balanced 60-opportunity
> sample to test whether `SEMANTIC_PRIORITY / OPTIONAL / DEFER` predicts where
> deep semantic reasoning is worth spending.

Preparation itself must be reviewed and committed before human labels are
collected.

Directional evidence gates after labeling include:

- DEFER safety >=90% NOT_WORTH among adjudicated DEFER;
- no more than 2 WORTH items in DEFER;
- PRIORITY worthiness precision >=60%;
- NEED_MORE_INFO <=20%;
- no catastrophic employer-specific blind spot in reviewed evidence.

Passing these gates is necessary but not sufficient for runtime promotion.

## Next intended steps

1. Execute SPEC-012 preparation with zero external calls.
2. Review sample construction/privacy and commit the frozen human-labeling
   protocol before collecting labels.
3. Human reviews all 60 items without seeing triage/cache/semantic score.
4. Evaluate compute-worthiness gates and counterfactual economics.
5. Decide whether to:
   - test deterministic triage further;
   - design a cheap learned/model-based screening experiment;
   - or conclude full semantic assessment is the simpler tradeoff.
6. Only after that decision revisit SPEC-008 prospective ranking validation.

## Known open decisions

- Compute-allocation architecture after the 60-item human experiment.
- Semantic-call budget after an unbiased allocation policy/frame exists.
- Whether manual opportunity-cluster overrides are needed after future
  prospective cluster adjudication.
- Durable private backup/retention for SQLite, raw judgments, and detailed
  review evidence.
- Bounded semantic-call authority available to future agents.

## Operational/test note

The historical 406-job residual expectation now lives in frozen sanitized test
evidence rather than depending on mutable operational database size. Current
operational diagnostics remain read-only.

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
