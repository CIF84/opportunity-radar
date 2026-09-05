# Opportunity Radar — Current Status

This is the authoritative repository handoff. It records current direction and
constraints; operational counts are derived by `opportunity-radar-status`.

## Current approved work packet

```text
specs/phase4/SPEC-002-market-routing-integration.md
```

Status: `APPROVED_FOR_IMPLEMENTATION`.

Implementation agents should follow this pointer rather than infer work from
filename recency. Before starting an approved packet, verify the local working
tree is clean and synchronize with `origin/main` when safe. If unexplained local
changes, divergence, or conflicts exist, stop and report them rather than
overwriting or improvising.

The development authority boundary is deliberately simple:

- agents may inspect, analyze, implement, and validate an approved work packet;
- initial implementation remains uncommitted while awaiting human/ChatGPT review;
- after explicit approval, the implementation agent may commit and push the
  approved working tree itself;
- humans approve decisions and promotion boundaries rather than performing Git
  plumbing manually.

## Mission

Monitor relevant public employer vacancies, maintain trustworthy lifecycle
state, and explain which active opportunities deserve a candidate's attention.

## Current phase

Phases 1–3 are implemented. Scope-aware ingestion and persisted detail reuse
have passed bounded validation. The first Live Decision Validation is complete.

Phase 4 Slices 1–2 are implemented: both candidate profiles carry a validated,
versioned, independently fingerprinted market-access policy, and a pure
post-detail evaluator can produce a structured `IN_SCOPE`, `UNCERTAIN`, or
`OUT_OF_SCOPE` assessment. The evaluator is not integrated into routing or
ranking. No recommendation cap, clustering, preference behavior, or other
Phase 4 product behavior is implemented.

## Last validated state

Live Decision Validation batch `batch-20260826T210045Z-6492b09a`:

- reviewed: 30/30;
- directional verdict: `NO_GO`;
- strict APPLY recall: 100%;
- shortlist APPLY recall: 100%;
- top attention acceptance: 35%;
- ranking agreement: 40%;
- disagreements: deterministic eligibility 11, unrepresented preference 7,
  semantic interpretation 2, benchmark/taxonomy 1, scoring/calibration 1.

Canonical aggregate evidence is
`output/live_validation/batch-20260826T210045Z-6492b09a/validation_report.md`.
The immutable batch is beside it. Raw judgments remain local under the data
policy in `OPERATING_MODEL.md`.

## What we learned

- The semantic hypothesis remains viable: only two reviewed disagreements were
  classified as semantic interpretation errors.
- The principal failure was inappropriate vacancies reaching ranking because
  current-candidate market suitability is not enforced at the ranking boundary.
- One human opportunity can have multiple source postings. Four Kiwi Inventory
  variants represented one intended application; two WPP Growth Consulting
  variants represented one apparent opportunity.
- Candidate preferences around execution authority, functional/domain
  attraction, employer/industry conviction, learning upside, and seniority are
  not represented strongly enough.
- Retrieval scope is a detail-cost policy. It is not candidate eligibility.

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
  -> deterministic composite / shortlist
```

The first three stages and Phase 3 assessment/decision contracts exist. The
candidate market-access representation and pure assessment function exist,
but candidate-market routing, clustering, preferred-variant, and
preference-policy stages are planned only.

## Confirmed Phase 4 candidate policy

The candidate has explicitly confirmed the following policy. It is durable
Phase 4 configuration consumed by the pure market evaluator; its effects on
routing and recommendation remain unimplemented:

- Normal onsite/hybrid work is acceptable in Prague, Czechia. Other Czech
  cities and foreign locations are not automatically acceptable.
- Remote work is acceptable while resident in Czechia when Czech-based
  employment/engagement is confirmed and working hours are reasonably
  European-compatible. Missing practical eligibility evidence is uncertain;
  an explicitly foreign-restricted arrangement is out of scope.
- Relocation is exceptional rather than part of the normal shortlist. It may
  be explored later only as an explicit override for exceptional upside.
- Czech work access is confirmed. Foreign work authorization must not be
  inferred, and the system must not purport to decide international employment
  or tax law.
- Czech and English are work-capable; Slovak comprehension must not itself
  disqualify a role; French is not currently work-capable; Japanese is `NONE`.
- Candidate-market `UNCERTAIN` can produce at most `REVIEW`.
- Explicit junior/graduate roles are capped at `LOW_PRIORITY` when the
  candidate-configured seniority guard applies; they are not universally
  ineligible.
- Domain, function, employer, and product aversions remain soft and tradeable.
  Strong AI, automation, transformation, learning, or strategic upside may
  outweigh them.

The accepted decisions and rationale are recorded in `docs/decisions.yaml`.
The runtime representation and validation contract are specified in Phase 4
of `SPEC.md`. Declarative, deliberately bounded normalization used by the pure
evaluator lives in `config/market_status_rules.yaml`.

`config/candidate.yaml` is now profile version 2. Its new
`market_access_policy` is the Phase 4 authority for these facts and policies.
The older `facts` fields remain unchanged solely to preserve the exact
`phase3-semantic-v1` input projection and semantic cache identity. The policy
is represented and consumed by the pure evaluator, but is not yet consumed by
runtime routing.

## Frozen items

Until the current gate is evaluated, do not change casually:

- model: `gpt-5.6-luna`;
- reasoning effort: `low`;
- semantic contract: `phase3-semantic-v1`;
- scoring weights;
- frozen historical benchmark and fixtures;
- recorded human judgments and batch membership;
- Phase 1 adapter discovery/detail contracts;
- Phase 2 lifecycle, completeness, and exact-identity semantics;
- existing semantic cache records.

The next gate is not “tune Luna.”

## Current gate

> Test whether candidate-market routing, deterministic opportunity clustering,
> and preference representation materially improve precision while preserving
> recall and semantic-cache reuse.

## Next intended experiments

1. Integrate current-candidate market status at the Phase 3 candidate-routing
   boundary, including the `UNCERTAIN` recommendation cap, without changing
   lifecycle or semantic-cache identity.
2. Demonstrate high-confidence employer-scoped opportunity clustering without
   merging `JobInstance` records.
3. Add a versioned preference-aware decision policy without one-off dislikes.
4. Retrospectively replay the immutable batch using existing semantic
   assessments wherever semantic inputs are unchanged.
5. Run a new prospective validation batch.
6. Only then decide whether `phase3-semantic-v2` is justified.

## Known blockers and open decisions

- Decide whether manual opportunity-cluster overrides are allowed.
- Predeclare the initial bounded numeric/ordinal effect mapping for soft
  decision preferences before retrospective replay.
- Choose the prospective Phase 4 batch size and stopping rule.
- Confirm repository privacy before tracking raw candidate judgment notes.
- Choose a durable private backup/retention policy for operational SQLite and
  local judgment evidence.
- Define the bounded semantic-call authority available to future agents.

## Last known operational health

Repository inspection on 2026-09-04 found:

- SQLite schema version 3;
- latest ingestion run `0a4af82b-0e40-4e20-8cef-0528ce4fa1d2`, status
  `PARTIAL`, with all 18 source observations `SUCCESS`;
- 431 active and 1 closed persisted job instances;
- 406 Luna / low / semantic-v1 assessments;
- operational SQLite contains candidate `roman_christov` version 1; repository
  configuration is now version 2 with only separately fingerprinted Phase 4
  market-access additions, so it is intentionally not yet persisted by a
  normal run;
- two intentionally retained interrupted historical `RUNNING` rows;
- offline tests passing; see the optional test receipt/status output for the
  exact most recent command and count.

These counts are time-bound observations, not hand-maintained runtime truth.

## Explicitly do not change yet

- Do not tune the semantic prompt, model, reasoning effort, or weights.
- Do not rewrite Phase 1 adapters or Phase 2 lifecycle logic.
- Do not merge `JobInstance` records to solve opportunity identity.
- Do not invalidate or overwrite existing assessments/judgments.
- Do not add fuzzy clustering, probabilistic deduplication, Learning
  Intelligence, UI, alerts, scheduling, or application automation.
- Do not infer authority to apply from an `APPLY` recommendation.
