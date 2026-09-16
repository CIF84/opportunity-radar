# SPEC-021 — Frozen Credential Evidence Semantics Validation v2

Status: `APPROVED_FOR_IMPLEMENTATION`

## Purpose

Redesign credential-semantics validation so that source disappearance after a trustworthy observation does not destroy already captured evidence.

SPEC-020 was terminated at 20/50 reviews because 12/20 reviewed vacancies could no longer be verified live. The experiment nevertheless exposed a useful architectural hypothesis: formal degree wording, experiential substitutability, and independent capability gaps are distinct objects.

SPEC-021 validates that hypothesis using **immutable credential evidence objects** rather than requiring the external vacancy page to remain available at review time.

This packet is preparation only. Do not begin human review until the v2 evidence set and review protocol are implemented, reviewed, and committed.

## Core principle

```text
PUBLIC SOURCE AT OBSERVATION TIME
        ↓
exact credential wording
bounded qualification context
role requirements
source provenance + timestamp + hash
        ↓
IMMUTABLE EVIDENCE OBJECT
        ↓
human / AI reasoning later

source later disappears
        ≠
evidence automatically becomes invalid
```

A source becoming unavailable is provenance/currentness metadata. It invalidates the captured evidence only when the stored observation itself is incomplete, inconsistent, corrupted, or insufficient for the question being asked.

## Relationship to SPEC-020

SPEC-020 remains frozen and terminated as `TERMINATED_SOURCE_DECAY_CONFOUNDED`.

Do not modify, reopen, resample, supersede, or reinterpret its 20 judgments as completed validation.

SPEC-021 has a new experiment/protocol identity and must not reuse SPEC-020 human labels as selection inputs.

SPEC-020 exploratory observations may be cited only as motivation:

- 8/20 reviewed cases were substantively interpretable;
- all eight had hard-credential wording;
- six were judged experience-plausibly-substitutable;
- two were judged degree-gap-decisive;
- independent capability/domain gaps repeatedly appeared;
- preferred/equivalent/generic/ambiguous wording remained unvalidated.

These proportions are not population estimates and must not become v2 priors or gates.

## Governing conceptual model

Keep four objects separate:

### 1. Credential statement semantics

What does the employer's captured wording literally establish?

### 2. Credential substitutability

Does the source explicitly allow substitution, or does candidate evidence plausibly substitute for the credential's underlying capability signal?

### 3. Capability distance

What independent professional/domain/technical gaps remain after credential reasoning?

### 4. Application competitiveness

How much residual hiring friction does the credential gap plausibly create?

SPEC-021 validates the first two and captures evidence relevant to the third. It does not implement a competitiveness model.

## Frozen evidence object

Implement a generic immutable contract, e.g. `CredentialEvidenceSnapshot`, containing at least:

- stable source/job identity;
- employer and role title;
- source URL;
- source observation timestamp;
- source/detail observation identity where available;
- exact credential sentence(s);
- bounded surrounding qualification context;
- exact modal terms preserved;
- explicit years/professional requirements;
- explicit related domain/technical requirements;
- normalized credential concept;
- source-content fingerprint/hash;
- evidence completeness fields;
- source-currentness status recorded separately from evidence validity;
- snapshot fingerprint.

Do not store a human interpretation label inside the evidence snapshot.

If existing normalized observations can reconstruct exact qualification wording reliably, use them. If exact wording cannot be reconstructed faithfully, that case is not eligible for v2.

## Evidence validity

Define separate states such as:

- `VALID_FROZEN_EVIDENCE`
- `INSUFFICIENT_CAPTURE`
- `PROVEN_SOURCE_CONFLICT`
- `CORRUPT_OR_INCONSISTENT`

A dead URL alone must not produce `INVALID` when exact qualification evidence was already captured and hashed.

Current live availability may be recorded as:

- `SOURCE_CURRENTLY_AVAILABLE`
- `SOURCE_CURRENTLY_UNAVAILABLE`
- `SOURCE_CURRENTNESS_NOT_CHECKED`

but currentness must not alter human Question A/B labels.

## Semantic coverage objective

SPEC-021 is not intended to estimate prevalence across the operational population. It is intended to characterize the **credential-reasoning rule space**.

Therefore use semantic/wording coverage rather than representative sampling as the primary design objective.

Target evidence classes:

1. explicit hard degree requirement;
2. explicit `degree OR equivalent experience`;
3. explicit preferred/ideal/desirable degree;
4. mixed wording where mandatory and preferred language coexist;
5. generic/template/contextual degree mention;
6. ambiguous wording;
7. constitutive/regulated credential controls where available;
8. hard degree wording plus strong candidate experiential substitute;
9. hard degree wording plus weak/no experiential substitute;
10. degree wording where another independent capability/domain gap is clearly more important.

## Sample design

Target approximately 30–40 human-reviewed evidence objects, not 50 by default.

The preparation should first enumerate all reconstructable evidence patterns and then propose the smallest frozen set that gives adequate coverage.

Rare classes should be deliberately oversampled. In particular:

- include all or most available explicit `degree OR equivalent experience` cases if the count is small;
- deliberately include preferred/mixed/generic/ambiguous examples;
- include enough hard-requirement controls to compare against SPEC-020's saturated branch;
- include constitutive credentials if trustworthy examples exist.

Employer representativeness is secondary to wording/reasoning diversity, but avoid one employer monopolizing a semantic class when alternatives exist.

Do not use candidate preference, recommendation, semantic score, cache status, stretch class, or historical human judgment to select examples.

## Candidate substitution evidence

For each review object, generate a bounded candidate-evidence projection relevant to substitution:

- completed degree fact;
- relevant years/domain history;
- directly matching capability evidence;
- adjacent/transferable capability evidence;
- explicit missing/developing capabilities where already represented in candidate facts;
- leadership/organizational experience where relevant.

This projection must be deterministic and provenance-backed.

Do not ask an LLM to invent missing candidate evidence.

Do not include career preference/attraction in the substitution projection.

## Human review questions

Retain the useful two-question separation but improve the semantics.

### Question A — captured credential semantics

Allowed labels:

- `HARD_CREDENTIAL`
- `DEGREE_OR_EQUIVALENT_EXPERIENCE`
- `PREFERRED_CREDENTIAL`
- `GENERIC_OR_NONDECISIVE_CREDENTIAL`
- `AMBIGUOUS_CREDENTIAL`
- `EVIDENCE_CAPTURE_INVALID`

The reviewer judges the frozen captured wording, not whether the live page still exists.

### Question B — experiential substitution

Allowed labels:

- `EXPERIENCE_STRONGLY_SUBSTITUTES`
- `EXPERIENCE_PARTIALLY_SUBSTITUTES`
- `NO_CREDIBLE_EXPERIENTIAL_SUBSTITUTE`
- `CREDENTIAL_CONSTITUTIVE_OR_NON_SUBSTITUTABLE`
- `NEED_MORE_INFORMATION`

This wording replaces the misleading SPEC-020 question about whether the degree gap itself makes candidacy unrealistic.

The reviewer should evaluate whether candidate experience substitutes for the capability signal represented by the credential, while recording independent capability gaps separately.

## Independent capability-gap capture

Allow the human to attach zero or more controlled, non-credential observations such as:

- `DOMAIN_EXPERTISE_GAP`
- `TECHNICAL_SKILL_GAP`
- `PROFESSIONAL_FUNCTION_GAP`
- `REGULATORY_OR_LICENSE_GAP`
- `SENIORITY_DEPTH_GAP`
- `LANGUAGE_GAP`
- `OTHER_CAPABILITY_GAP`

with private notes.

These observations are diagnostic and do not change runtime candidate capability automatically.

This is essential to distinguish:

```text
"degree missing"
from
"degree is substitutable, but SAP/healthcare/AI-cloud/insurance expertise is missing"
```

## AI-judgment hypothesis

SPEC-021 should prepare for eventual AI replication, but the human is not assumed to be infallible ground truth.

The experiment's purpose is **model discovery**:

- identify stable reasoning patterns;
- identify evidence needed for credential substitution;
- identify cases where human judgment itself is uncertain;
- derive a generic reasoning contract that an AI can later apply.

Do not train/tune a model in SPEC-021.

Do not add human-specific heuristics such as “ignore degree because candidate has 20 years experience.”

## Reasoning-saturation rule

Unlike SPEC-020, predeclare an explicit saturation checkpoint.

After every 10 completed substantive reviews, calculate a blind-safe pattern inventory that does not reveal hidden expected classes for future reviews.

Human review may stop early only after an explicit decision if:

1. all target semantic classes with available evidence have been reviewed at least once;
2. the last 10 substantive reviews introduced no new credential-reasoning pattern;
3. at least two distinct employers/role contexts support each major non-rare pattern where available;
4. no important unresolved class remains intentionally oversampled but unseen.

Stopping for saturation must create a controlled terminal status such as `COMPLETED_REASONING_SATURATION` distinct from full planned-count completion.

Do not silently stop or infer saturation from label repetition alone.

## Freshness strategy

Preparation may optionally perform a bounded currentness check of source URLs, but:

- it must not refresh the operational corpus;
- currentness must be recorded separately;
- unavailable pages remain reviewable if frozen evidence is valid;
- no replacement occurs solely because a source disappeared after capture.

Replacement is permitted only for invalid/incomplete evidence snapshots.

## Selection source

Prefer a broader source pool than only the 144 SPEC-019 degree-driven excessive cases if needed to obtain missing wording classes.

Eligible evidence may come from current or historical detailed observations already stored locally, provided:

- exact wording/provenance can be reconstructed;
- evidence identity is immutable;
- no live semantic call is needed;
- privacy boundaries are preserved.

If expanding beyond the 144 cases, document the source populations separately. This experiment is about semantic coverage, not prevalence.

## Preparation deliverable

Before human review, report:

- evidence populations searched;
- number with reconstructable exact wording;
- credential wording-pattern inventory;
- candidate substitution-evidence coverage;
- proposed sample size;
- selected counts by semantic evidence class and employer;
- reserve/replacement strategy for invalid captures only;
- source-currentness distribution if checked;
- evidence/snapshot fingerprints;
- blindness/privacy proof;
- zero-call/read-only proof;
- validation.

Do not present reviews until preparation is approved and committed.

## Human workflow

Implement `prepare`, `record`, `replace-invalid`, and `report` phases.

`record` must append Question A, Question B, optional controlled independent capability gaps, and private notes.

Support supersession/correction without deleting prior judgments.

`report` before completion/saturation must not expose hidden future-class distribution or expected-rule performance.

## Post-review analysis

Once completed by planned count or approved saturation, derive a credential reasoning contract and compare at least these architectures:

### Architecture A — degree inside stretch

Current SPEC-019-like approach.

### Architecture B — credential compatibility separate from capability stretch

```text
CAPABILITY FIT
      +
CREDENTIAL COMPATIBILITY
      ↓
APPLICATION COMPETITIVENESS / DECISION REASONING
```

### Architecture C — constitutive credentials only as hard stretch/eligibility

Generic degrees become compatibility evidence; regulated/licensed/constitutive credentials remain non-substitutable.

For each architecture, report qualitative and bounded quantitative implications. Do not promote runtime behavior in SPEC-021.

## Counterfactual replay

After human validation, replay candidate reasoning rules against:

- reviewed v2 evidence;
- frozen SPEC-020 exploratory evidence where compatible, reported separately;
- current SPEC-019 degree-driven corpus diagnostically.

Report projected movement out of degree-driven excessive stretch, but do not mutate runtime results.

## Privacy

Private/local and Git-ignored:

- evidence-object manifest with vacancy identities;
- blind review packet;
- human judgments/notes;
- detailed capability-gap observations;
- detailed final report linking judgments to vacancies.

Repository-safe aggregate may contain:

- experiment identity;
- evidence-class counts;
- fingerprints/hashes;
- source-currentness aggregate;
- final aggregate human-label distributions;
- saturation status;
- sanitized architecture conclusions;
- no vacancy titles/URLs/descriptions or human notes.

## Protected invariants

Do not change:

- SPEC-019 runtime status (diagnostic/unpromoted);
- SPEC-020 frozen terminated evidence;
- candidate profile/capabilities/preferences;
- market policy/status semantics;
- source configuration/adapters;
- semantic-v1 model/prompt/reasoning/contract;
- semantic cache;
- Phase 3 scoring;
- clustering/seniority/lifecycle behavior;
- ranking/recommendation/semantic allocation.

No external semantic calls are authorized.
Operational SQLite must remain read-only.

## Tests

Add offline coverage proving at least:

- dead URL does not invalidate valid frozen evidence;
- invalid/incomplete capture does;
- exact modal wording and bounded context are immutable and fingerprinted;
- currentness status is independent of evidence-validity status;
- selection is independent of hidden stretch/preference/recommendation/cache/human labels;
- rare semantic classes can be oversampled deterministically;
- candidate substitution projection excludes preferences;
- controlled independent capability-gap recording;
- append-only judgments/supersession;
- replacement only for invalid capture;
- blind-safe saturation checkpoints;
- no semantic calls or SQLite writes;
- repository-safe output excludes vacancy identities and private notes.

Run full offline suite and `git diff --check`.

## Stop conditions

Stop for human decision rather than improvising if:

- exact qualification wording cannot be reconstructed for enough semantic diversity;
- equivalent/preferred/generic/ambiguous classes cannot be sourced from stored observations;
- broader historical evidence requires unsafe provenance assumptions;
- candidate substitution projection cannot distinguish evidence from preference;
- preparation would require semantic calls or operational-state mutation;
- sample would again be dominated by one wording pattern with no meaningful semantic diversity.

## Deliverable

Return:

A. source evidence populations searched;
B. immutable evidence-object contract;
C. wording-pattern inventory;
D. candidate substitution projection;
E. proposed frozen sample and semantic coverage;
F. source-currentness handling;
G. saturation protocol;
H. privacy/integrity proof;
I. tests/validation;
J. files changed;
K. recommended preparation commit message.

Do not begin human review, commit, or push until normal review approval.
