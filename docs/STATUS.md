# Opportunity Radar — Current Status

This is the authoritative repository handoff. It records current direction and
constraints; operational counts are derived by `opportunity-radar-status`.

## Mission

Monitor relevant public employer vacancies, maintain trustworthy lifecycle
state, and explain which active opportunities deserve a candidate's attention.

## Current phase

Phases 1–3 are implemented. Scope-aware ingestion and persisted detail reuse
have passed bounded validation. The first Live Decision Validation is complete.

Phase 4 is in **experiment design / pre-implementation**. No Phase 4 product
behavior is implemented.

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
candidate-market, clustering, preferred-variant, and preference-policy stages
are planned only.

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

1. Implement and replay a conservative current-candidate market status.
2. Demonstrate high-confidence employer-scoped opportunity clustering without
   merging `JobInstance` records.
3. Add a versioned preference-aware decision policy without one-off dislikes.
4. Retrospectively replay the immutable batch using existing semantic
   assessments wherever semantic inputs are unchanged.
5. Run a new prospective validation batch.
6. Only then decide whether `phase3-semantic-v2` is justified.

## Known blockers and open decisions

- Define candidate-acceptable onsite/hybrid countries and cities.
- Confirm remote employment regions, work authorization, and relocation facts.
- Decide whether `UNCERTAIN` caps recommendation at `REVIEW`.
- Decide how explicit junior roles affect recommendation for this candidate.
- Decide whether manual opportunity-cluster overrides are allowed.
- Choose future validation unit: posting attention, opportunity attention, or
  application intent.
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
- current candidate `roman_christov` version 1 matching its persisted
  fingerprints;
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
