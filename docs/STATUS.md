# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-020-credential-semantics-human-validation.md
```

Status: `PREPARED_LOCALLY_AWAITING_REVIEW`.

Implementation/operations agents must follow this pointer rather than infer work
from file recency. Before starting, verify the local working tree is synchronized
with `origin/main` when safe. Intentionally retained local operational/private
evidence is not itself an error; unexplained code/config divergence is.

The development authority boundary remains:

- agents may inspect, analyze, implement, validate, and perform explicitly approved bounded internal operations;
- implementation changes remain uncommitted while awaiting human/ChatGPT review;
- after explicit approval, the implementation agent may commit and push;
- humans approve decisions and promotion boundaries rather than perform Git plumbing manually;
- repository-safe aggregate evidence may be tracked, while detailed candidate- and human-judgment-derived evidence remains private/local unless explicitly authorized for disclosure.

## Mission

Monitor relevant public employer vacancies, maintain trustworthy lifecycle state,
and explain which active opportunities deserve a candidate's attention.

## Current phase

Phases 1–3 are implemented. Phase 4 has validated market routing, clustering,
preferences, source breadth, semantic compute-worthiness, and a diagnostic stretch
evidence boundary. Runtime stretch/rejection remains intentionally unpromoted.

Frozen recent milestones:

- SPEC-013 source portfolio audit: `a4ebba825e80256ad55ed6bfcaf973a2df37d413`
- SPEC-014 Wave A preflight: `11e000825e339de8c772d5bd7a66e2567469f1b2`
- SPEC-015 production onboarding: `541685ce40e959a66d2ec443b6ef748190713bb1`
- SPEC-016 nested feeds + Mews: `556fd7aec5d77874f56d7a5b5137a06a75fbfbca`
- SPEC-017 partial-geography semantics: `1871a082874f27db606796fc06e348fbee71776c`
- SPEC-018 candidate direction: `34fdd1b601309a025ec72af6a4275f1dcfc72dde`

SPEC-019 is committed as `5591442` and remains diagnostic/unpromoted. Its result
motivated SPEC-020: degree/credential evidence is the dominant unresolved source
of excessive-stretch classifications. SPEC-020 tooling is implemented locally;
the authorized deterministic sample and reserves are frozen, but human review has
not started.

## SPEC-019 diagnostic result

Frozen 60-item sample:

```text
CURRENT_FIT          7
MANAGEABLE_STRETCH  24
EXCESSIVE_STRETCH    9
UNRESOLVED           20
```

Safety/validation result:

- human WORTH protection: 3/3;
- excessive-stretch directional precision: 100%;
- human-evident excessive coverage: 39.1%;
- market-only false excessive: 0;
- preference-only false excessive: 0.

Current-corpus diagnostic replay:

```text
clusters              3935
CURRENT_FIT            191
MANAGEABLE_STRETCH     281
EXCESSIVE_STRETCH      171
UNRESOLVED            3292
```

The critical finding is that 144 of 171 current-corpus excessive results are driven
by mandatory-degree evidence. This concentration is too large to promote runtime
stretch semantics without human validation of credential wording and substitutability.

SPEC-019 therefore remains diagnostic: no stretch filtering, ranking, recommendation,
or semantic allocation was introduced.

## Why SPEC-020 exists

A formal credential gap and a capability gap are not necessarily the same object.

SPEC-020 validates the distinction between:

```text
CAPABILITY DISTANCE
Can the candidate plausibly perform the work?

CREDENTIAL COMPATIBILITY
Does the employer explicitly require a formal credential the candidate lacks?

CREDENTIAL SUBSTITUTABILITY
Does equivalent professional experience satisfy or plausibly substitute?

APPLICATION COMPETITIVENESS
How likely is the employer to accept the gap?
```

The candidate has no completed bachelor's degree but approximately 20 years of
senior technology/business experience. The experiment must not assume either that
experience always substitutes or that a degree phrase is always decisive.

## SPEC-020 human-validation design

Primary source population: current SPEC-019 degree-driven `EXCESSIVE_STRETCH`
cases, historically reported as 144. Preparation must verify the actual reproducible
population and snapshot identity before sampling.

Target human sample: 50 cases, deterministically stratified across employer,
role/profession family, credential wording pattern, seniority/years context, and
whether degree evidence is the sole or one of multiple stretch reasons.

Human review asks two independent questions.

Question A — source credential semantics:

```text
HARD_CREDENTIAL
DEGREE_OR_EQUIVALENT_EXPERIENCE
PREFERRED_CREDENTIAL
GENERIC_OR_NONDECISIVE_CREDENTIAL
AMBIGUOUS_CREDENTIAL
INVALID_OR_STALE_EVIDENCE
```

Question B — practical consequence of the missing bachelor's degree:

```text
DEGREE_GAP_DECISIVE
EXPERIENCE_PLAUSIBLY_SUBSTITUTES
DEGREE_GAP_NOT_DECISIVE
NEED_MORE_INFORMATION
```

The packet must preserve exact modal wording such as `must`, `required`, `preferred`,
`or equivalent experience`, and `ideally` rather than paraphrasing it away.

## SPEC-020 preparation result

The current operational snapshot reproduces exactly 144 degree-driven cases across
only three employers: 116 EY, 22 Johnson & Johnson, and 6 Schneider Electric. A
50-item sample could contain at most 15 items under the requested employer cap of
five. The mathematically smallest cap that can fill 50 cases is 22.

The material relaxation was explicitly approved: retain the target of 50, use cap
22, and preserve the 22 EY / 22 Johnson & Johnson / 6 Schneider Electric design.
Preparation `spec020-credential-preparation-20260914-v3` froze that sample, a
deterministic blind order, five direct-mandatory reserves, and five
qualified/substitutable reserves. External semantic calls, live-source calls,
SQLite writes, and human judgments remain zero.

Final reporting must keep unweighted/stratified sample results separate from
employer-population-weighted estimates over the verified 144-case population.
Balanced sample proportions are not population prevalence; Schneider Electric's
six selected cases are complete coverage of its current degree-driven population.

## Blindness and privacy

Before completion, human reviewers must not see:

- current `EXCESSIVE_STRETCH` classification;
- hidden rule expectation;
- semantic score/recommendation;
- cache/triage state;
- interim aggregate performance that could bias later judgments.

Vacancy-level evidence, sample manifest, human labels/notes, and detailed final
results remain private/local and Git-ignored. Only sanitized aggregate evidence is
repository-safe.

## Candidate capability baseline

Current candidate facts remain unchanged:

- no completed bachelor's degree;
- approximately 20 years technology/business experience;
- expert business analytics/decision support/business operations/commercial strategy;
- advanced transformation and leadership evidence;
- intermediate AI strategy/adoption;
- developing SQL/Python/software architecture/product-development depth.

Interest in a role or field must not upgrade capability evidence.

## Candidate direction/preferences

Candidate profile version 4 / decision preference version 2 includes the narrow
negative `account_management_execution` preference from SPEC-018. Preferences must
not influence SPEC-020 sample selection or credential semantics.

## Market/source state

Market policy remains Prague-only for normal onsite/hybrid work, with incomplete
compatible-country city evidence correctly treated as `UNCERTAIN` under SPEC-017.

Production sources include the earlier portfolio plus Keboola, Commerzbank, KPMG,
and Mews. No new source integration is authorized during SPEC-020.

## Current gate

> Review and commit the frozen SPEC-020 preparation packet and repository-safe
> receipt. Begin human review only after explicit approval.

Do not present reviews or create judgments until the frozen packet is reviewed,
committed, and the human phase is explicitly authorized.

## Protected boundaries

Do not change:

- SPEC-019 stretch semantics/source evidence;
- candidate profile/capabilities/preferences;
- market policy/status semantics;
- hard eligibility;
- source configuration/adapters;
- semantic-v1 model/prompt/reasoning/contract;
- Phase 3 scoring weights;
- clustering/seniority/lifecycle semantics;
- historical judgments;
- semantic assessments/cache;
- runtime ranking/recommendation/allocation behavior.

No external semantic calls are authorized. Operational SQLite must remain read-only.

## Intended architecture under investigation

```text
CAPABILITY FIT
        ↓
CREDENTIAL COMPATIBILITY
        ↓
APPLICATION COMPETITIVENESS
```

This is a hypothesis to test, not a pre-approved runtime architecture.

## Direction after SPEC-020

Contingent on completed human evidence:

1. determine whether credentials belong inside stretch or a separate compatibility object;
2. correct degree semantics only in a separately approved packet;
3. rerun stretch replay after any correction;
4. only then design the combined deterministic rejection layer;
5. compare compute-allocation economics against SPEC-011/012;
6. preserve an exploration/control path before broad semantic suppression;
7. keep semantic-v1 frozen until upstream allocation architecture is validated.

## Known blockers and open decisions

- Credential semantics and degree substitutability.
- Whether SPEC-019 stretch can later support runtime boundaries.
- Deterministic rejection architecture after credential validation.
- Exploration/control rate for future compute allocation.
- Semantic-call budget for later prospective ranking validation.
- Future source-contract work for Erste/Zentiva/Wave B.
- Durable private backup/retention for operational SQLite and detailed human evidence.

## Last known operational health

- SPEC-020 verified population: 144, matching the SPEC-019 historical count.
- SPEC-020 cap 22 / target 50 / 22-22-6 design: frozen locally with 10 reserves.
- Frozen selection / blind-order fingerprints:
  `400c050ba3091012d0707b534f06ac5a6740c4e174d1c1005f61b686f3d19359` /
  `307e85f4ddabc5df51ed0eac258d05320296fd2c1aa30b54e2feac7391a8df78`.
- SPEC-020 external semantic calls, live-source calls, SQLite writes, and judgments: zero.
- Operational SQLite SHA-256 remained
  `a07d53002dc22e07ba33946a1dfc172365d182e37133f6221f4ef48e2154ff23`.
- Latest full offline validation: 322 passed, 2 expected private-evidence skips,
  and 22 live tests deselected; `git diff --check` passed.

## Explicitly do not build/tune yet

- runtime stretch filtering/rejection;
- combined deterministic rejection;
- degree-policy correction before human validation;
- autonomous preference learning;
- semantic prompt/model/weight tuning;
- cheap secondary LLM routing;
- embeddings/vector search;
- learned ranking/ML infrastructure;
- broad fuzzy clustering;
- new source integrations;
- UI/feed/control panel;
- application automation;
- external actions inferred from `APPLY`.
