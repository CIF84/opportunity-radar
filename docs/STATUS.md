# Opportunity Radar — Current Status

This is the authoritative repository handoff. Operational counts are derived by
`opportunity-radar-status`; this file records current direction, frozen policy,
and the next approved work packet.

## Current approved work packet

```text
specs/phase4/SPEC-021-frozen-credential-evidence-semantics-v2.md
```

Status: `COMPLETED_LOCALLY_AWAITING_OWNER_REVIEW`.

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
- SPEC-019 stretch evidence audit: `559144258608825bdbc746691c37da041bb2fc82`
- SPEC-020 terminated credential validation: `676647bb24a7f88b23c334d74e904cd8444f840c`

SPEC-021 is a distinct completed protocol identity. It redesigned credential
validation around immutable captured evidence so later source disappearance does
not automatically invalidate a trustworthy observation. Its 36-case human review
and diagnostic replay are complete locally; no runtime rule has been promoted.

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

The critical finding is that 144 of 171 current-corpus excessive results were driven
by mandatory-degree evidence. This concentration is too large to promote runtime
stretch semantics without better credential reasoning.

## SPEC-020 terminal result

SPEC-020 is permanently frozen as `TERMINATED_SOURCE_DECAY_CONFOUNDED` after
20/50 reviews.

```text
reviewed                          20
INVALID_OR_STALE_EVIDENCE        12
substantively interpretable       8
HARD_CREDENTIAL                   8
EXPERIENCE_PLAUSIBLY_SUBSTITUTES  6
DEGREE_GAP_DECISIVE               2
```

These are exploratory observations only, not population estimates or validated
rule precision. Preferred, equivalent-experience, generic, and ambiguous credential
semantics were not validated. Human notes repeatedly distinguished independent
capability/domain gaps from the formal degree gap.

SPEC-020's frozen sample/reserves, 20 private append-only judgments, and detailed
evidence remain unchanged. It must not be resumed or silently resampled.

## Core lesson motivating SPEC-021

A trustworthy observation should remain analyzable after the external source changes.

```text
PUBLIC SOURCE AT T0
        ↓
exact evidence + provenance + timestamp + hash
        ↓
IMMUTABLE EVIDENCE SNAPSHOT
        ↓
human / AI reasoning later

source disappears at T1
        ≠
evidence automatically invalid
```

Source currentness and evidence validity are separate objects.

## SPEC-021 objective

SPEC-021 validates the credential-reasoning **rule space**, not population prevalence.
It should deliberately cover semantic diversity rather than reproduce the employer-
balanced 50-case design that failed under source decay.

Target classes include:

- explicit hard degree requirements;
- degree-or-equivalent-experience wording;
- preferred/ideal/desirable degree wording;
- mixed mandatory/preferred context;
- generic/template credential mentions;
- ambiguous wording;
- constitutive/regulated credential controls where available;
- hard wording with strong experiential substitute;
- hard wording with weak/no experiential substitute;
- cases where an independent capability/domain gap is more consequential than the degree.

Rare semantic classes should be intentionally oversampled.

## SPEC-021 preparation result

The zero-call, read-only v2 preparation is frozen locally as:

```text
spec021-credential-evidence-preparation-20260916-v2
```

It searched 4,514 detailed observation rows covering 4,164 job identities and
4,206 distinct job/content versions, including 42 historical versions. It
reconstructed 1,762 valid immutable evidence snapshots. Current source
availability was deliberately not checked; all snapshots retain
`SOURCE_CURRENTNESS_NOT_CHECKED` independently of evidence validity.

The proposed review set has 36 cases plus 14 same-class invalid-capture
reserves:

```text
EXPLICIT_HARD                         6
DEGREE_OR_EQUIVALENT_EXPERIENCE       6
PREFERRED_OR_IDEAL                    5
MIXED_MANDATORY_PREFERRED             5
GENERIC_OR_TEMPLATE                   5
AMBIGUOUS                             5
CONSTITUTIVE_OR_REGULATED             4
```

Seventeen employers are represented. Constitutive/regulated evidence is rare
and concentrated: three selected controls come from EY and one from Johnson &
Johnson. That is an explicit semantic-coverage limitation, not a prevalence
claim. The private manifest, blind packet, append-only judgments, and detailed
result are Git-ignored. Only sanitized aggregate receipts are repository-safe.

## SPEC-021 completed diagnostic result

The deliberately class-oversampled review completed at 36/36. It produced 22
`HARD_CREDENTIAL`, 11 `DEGREE_OR_EQUIVALENT_EXPERIENCE`, and three
`PREFERRED_CREDENTIAL` interpretations. Experiential substitution was strong in
one case, partial in five, absent in 23, and constitutive/non-substitutable in
seven. Independent capability gaps were recorded in 34/36 cases.

These are reasoning-coverage proportions, not population-prevalence estimates.
The result supports separating credential compatibility from capability stretch
(Architecture B), with constitutive-only hard treatment (Architecture C) as the
narrowest candidate for any future deterministic rule. Neither architecture is
promoted. The deterministic SPEC-019 replay preserves the verified 144-case
identity and reports only bounded diagnostic movement and call ceilings.

Repository-safe result:

```text
output/credential_evidence_validation/
  spec021-credential-evidence-preparation-20260916-v2/aggregate_result.json
```

## Improved human questions

Question A — captured credential semantics:

```text
HARD_CREDENTIAL
DEGREE_OR_EQUIVALENT_EXPERIENCE
PREFERRED_CREDENTIAL
GENERIC_OR_NONDECISIVE_CREDENTIAL
AMBIGUOUS_CREDENTIAL
EVIDENCE_CAPTURE_INVALID
```

Question B — experiential substitution:

```text
EXPERIENCE_STRONGLY_SUBSTITUTES
EXPERIENCE_PARTIALLY_SUBSTITUTES
NO_CREDIBLE_EXPERIENTIAL_SUBSTITUTE
CREDENTIAL_CONSTITUTIVE_OR_NON_SUBSTITUTABLE
NEED_MORE_INFORMATION
```

Independent capability gaps are recorded separately rather than being attributed
to the missing degree.

## Candidate capability baseline

Current candidate facts remain unchanged:

- no completed bachelor's degree;
- approximately 20 years technology/business experience;
- expert business analytics/decision support/business operations/commercial strategy;
- advanced transformation and leadership evidence;
- intermediate AI strategy/adoption;
- developing SQL/Python/software architecture/product-development depth.

Candidate preferences/direction must not affect credential substitution evidence.

## Reasoning-saturation design

SPEC-021 targets approximately 30–40 reviews, but planned count is not itself the
scientific objective.

After each 10 substantive reviews, a blind-safe pattern inventory may support an
explicit human decision to stop for `COMPLETED_REASONING_SATURATION` only when:

- all available target semantic classes have been observed;
- the last 10 substantive reviews add no new reasoning pattern;
- major patterns have cross-context support where available;
- no intentionally targeted rare class remains unseen.

No silent early stopping is allowed.

## Current gate

> Review the completed SPEC-021 evidence and architecture comparison. Decide
> whether to authorize a separate implementation specification; do not promote
> runtime credential/stretch behavior directly from this diagnostic experiment.

No runtime credential/stretch policy change is authorized.

## Protected boundaries

Do not change:

- SPEC-019 diagnostic stretch behavior;
- SPEC-020 frozen termination evidence;
- candidate profile/capabilities/preferences;
- market policy/status semantics;
- hard eligibility;
- source configuration/adapters;
- semantic-v1 model/prompt/reasoning/contract;
- semantic cache;
- Phase 3 scoring;
- clustering/seniority/lifecycle behavior;
- ranking/recommendation/semantic allocation.

No external semantic calls are authorized. Operational SQLite must remain read-only.

## Architecture under investigation

```text
CAPABILITY FIT
      +
CREDENTIAL COMPATIBILITY
      ↓
APPLICATION COMPETITIVENESS / DECISION REASONING
```

Constitutive credentials may ultimately require separate non-substitutable treatment,
but this is a hypothesis for validation, not a runtime rule.

## Direction after SPEC-021

1. owner-review Architecture B as the representation boundary and Architecture C
   as a possible narrow deterministic hard boundary;
2. if accepted, write a separate implementation specification rather than
   mutating SPEC-019 in place;
3. preserve conservative unresolved handling and independent capability gaps;
4. validate any implementation prospectively before suppressing semantic work;
5. preserve exploration/control before broad compute suppression;
6. keep semantic-v1 frozen until upstream allocation architecture is validated.

## Known open decisions

- Credential semantic/substitution architecture.
- Whether SPEC-019 stretch can later support runtime boundaries after credential correction.
- Deterministic rejection architecture.
- Exploration/control rate for future compute allocation.
- Semantic-call budget for later prospective ranking validation.
- Future source-contract work for Erste/Zentiva/Wave B.
- Durable private backup/retention for operational SQLite and detailed human evidence.

## Explicitly do not build/tune yet

- runtime stretch filtering/rejection;
- combined deterministic rejection;
- credential-policy correction before v2 validation;
- AI imitation/training from human labels;
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
