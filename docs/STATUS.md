# Opportunity Radar — Current Status

This is the authoritative repository handoff. It records current direction and
constraints; operational counts are derived by `opportunity-radar-status`.

## Current approved work packet

```text
specs/phase4/SPEC-004-decision-preferences.md
```

Status: `IMPLEMENTED_AWAITING_APPROVAL`.

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

Phase 4 market-access representation, current-candidate market assessment,
routing, high-confidence opportunity clustering, preferred-variant selection,
and the versioned decision-preference effect layer are implemented. The latest
slice is awaiting approval and is not yet committed. No retrospective Phase 4 replay, autonomous preference learning,
semantic-v2, or external-action behavior is implemented yet.

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
- Deterministic candidate-market routing now removes explicit incompatible
  opportunities without changing semantic-v1 or lifecycle state.
- One human opportunity can have multiple source postings. High-confidence
  clustering now collapses the known Kiwi Inventory variants and WPP Growth
  Consulting variants while preserving independent JobInstances.
- Candidate preferences around execution authority, functional/domain
  attraction, employer/industry conviction, and learning upside now have a
  versioned, taxonomy-backed, soft-effect representation. Retrospective evidence
  has not yet validated its ranking impact.
- Candidate preference is expected to change over time. Future interaction
  evidence may support preference hypotheses, but must not silently mutate
  authoritative preference state.
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

All stages through preference-aware decision effects and the existing Phase 3
semantic/base-decision contracts are implemented. Seniority-guard behavior and
retrospective replay remain later, separate work.

## Confirmed Phase 4 candidate policy

The candidate has explicitly confirmed the following policy. It is durable
Phase 4 configuration consumed by the market evaluator and deterministic
routing/recommendation-cap boundary:

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

`config/candidate.yaml` is profile version 3. Its `market_access_policy` and
`decision_preferences` are independent Phase 4 decision inputs and remain
excluded from semantic-v1 inputs.

## Confirmed preference-direction policy

The candidate has accepted an ordinal preference spectrum for ranking:

```text
STRONG_POSITIVE
POSITIVE
NEUTRAL
NEGATIVE
```

Preferences primarily modify ranking rather than act as binary eligibility.
They are time-varying/versioned decision policy, not immutable personality
facts. Preference state and the numeric preference-effect policy are separate.

The current approved experiment will freeze this initial deterministic mapping
before retrospective replay:

```text
STRONG_POSITIVE -> +0.4
POSITIVE        -> +0.2
NEUTRAL         ->  0.0
NEGATIVE        -> -0.3
aggregate cap   -> [-1.0, +1.0]
```

This mapping is an experimental ranking policy, not a claim about stable human
psychology. Future interactions may provide evidence for preference changes,
but evidence cannot silently promote a new authoritative preference version.

## Frozen items

Until the current gate is evaluated, do not change casually:

- model: `gpt-5.6-luna`;
- reasoning effort: `low`;
- semantic contract: `phase3-semantic-v1`;
- Phase 3 scoring weights;
- frozen historical benchmark and fixtures;
- recorded human judgments and batch membership;
- Phase 1 adapter discovery/detail contracts;
- Phase 2 lifecycle, completeness, and exact-identity semantics;
- existing semantic cache records;
- initial preference-effect mapping during the upcoming retrospective replay.

The next gate is not “tune Luna.”

## Current gate

> Test whether candidate-market routing, deterministic opportunity clustering,
> and preference representation materially improve precision while preserving
> recall and semantic-cache reuse.

## Next intended experiments

1. Approve and commit the bounded `SPEC-004` implementation.
2. Retrospectively replay the immutable batch using existing semantic
   assessments wherever semantic inputs are unchanged.
3. Run a new prospective validation batch.
4. Only then decide whether `phase3-semantic-v2` is justified.

## Known blockers and open decisions

- Decide whether manual opportunity-cluster overrides are needed only after the
  deterministic clustering results are adjudicated further.
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
  configuration is version 2 with separately fingerprinted Phase 4 market-access
  additions;
- latest routing preflight over 406 usable detailed active jobs produced 56
  `IN_SCOPE`, 265 `UNCERTAIN`, and 85 `OUT_OF_SCOPE`; all 321 semantically
  processable jobs were compatible cache hits, requiring zero external calls;
- repository-only cluster replay over the same 406 assessed postings produced
  394 clusters and a 315-cluster normal shortlist; it collapsed 12 duplicate
  postings, including the four Kiwi Inventory variants with Prague preferred,
  and kept the all-out-of-scope WPP Growth Consulting cluster out of the
  shortlist;
- two intentionally retained interrupted historical `RUNNING` rows;
- current worktree offline validation: 171 passed, 18 live tests deselected.

These counts are time-bound observations, not hand-maintained runtime truth.

## Explicitly do not change yet

- Do not tune the semantic prompt, model, reasoning effort, or Phase 3 weights.
- Do not rewrite Phase 1 adapters or Phase 2 lifecycle logic.
- Do not merge `JobInstance` records to solve opportunity identity.
- Do not invalidate or overwrite existing assessments/judgments.
- Do not broaden clustering into fuzzy/probabilistic matching yet.
- Do not add autonomous preference learning, Learning Intelligence, UI, alerts,
  scheduling, or application automation.
- Do not infer authority to apply from an `APPLY` recommendation.
