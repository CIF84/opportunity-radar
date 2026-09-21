# SPEC-022 — Shadow Credential Compatibility Separation and Stretch Replay

Status: `APPROVED_FOR_IMPLEMENTATION`

## Purpose

Implement the architectural boundary validated by SPEC-021 in **shadow mode only**:

> Generic academic credential absence is credential-compatibility evidence, not by itself evidence of capability distance.

SPEC-022 must separate credential compatibility from `StretchAssessment`, then replay the current corpus and frozen human evidence without changing production ranking, recommendation, filtering, semantic allocation, candidate state, or persisted operational state.

The central question is no longer whether degree absence matters. It is:

> After removing degree absence as a shortcut for capability stretch, which opportunities remain excessive for independently supported capability reasons, which become manageable/current-fit, and which correctly become unresolved?

## Evidence basis

SPEC-019 found 171 current-corpus `EXCESSIVE_STRETCH` results, 144 driven by `MANDATORY_CREDENTIAL_ABSENT`.

SPEC-021 completed 36/36 deliberately diverse human reviews and established:

- credential semantics, experiential substitution, and independent capability fit are distinct dimensions;
- independent capability gaps appeared in 34/36 reviewed cases;
- Architecture B — separate credential compatibility from capability stretch — best matched human reasoning;
- Architecture C — constitutive credentials only as a narrow hard boundary — remains a candidate for later validation, not an approved runtime rule;
- no runtime policy was promoted.

SPEC-022 operationalizes Architecture B as a shadow representation and diagnostic replay only.

## Governing architecture

Implement separate immutable/auditable objects:

```text
VACANCY REQUIREMENTS
        │
        ├───────────────┐
        ▼               ▼
CAPABILITY EVIDENCE   CREDENTIAL EVIDENCE
        │               │
        ▼               ▼
StretchAssessment     CredentialCompatibilityAssessment
        │               │
        └───────┬───────┘
                ▼
       future decision reasoning
```

SPEC-022 must not collapse these objects back into a single score.

## CredentialCompatibilityAssessment contract

Create a generic deterministic shadow contract containing at least:

- credential concept;
- captured credential semantics;
- evidence provenance/fingerprint;
- candidate credential state;
- substitution state;
- constitutive/non-substitutable state only when safely established;
- unresolved reasons;
- independent rules/input/assessment fingerprints.

Suggested controlled semantics:

### Credential semantics

- `HARD_CREDENTIAL`
- `DEGREE_OR_EQUIVALENT_EXPERIENCE`
- `PREFERRED_CREDENTIAL`
- `GENERIC_OR_NONDECISIVE_CREDENTIAL`
- `AMBIGUOUS_CREDENTIAL`

### Compatibility/substitution

- `SATISFIED`
- `EXPERIENCE_STRONGLY_SUBSTITUTES`
- `EXPERIENCE_PARTIALLY_SUBSTITUTES`
- `NO_CREDIBLE_EXPERIENTIAL_SUBSTITUTE`
- `CREDENTIAL_CONSTITUTIVE_OR_NON_SUBSTITUTABLE`
- `UNKNOWN`

Exact implementation names may differ if existing code conventions require it, but semantics must remain explicit and separately fingerprinted.

Do not infer `SATISFIED` merely from general years of experience.

## Capability stretch correction

Create a **shadow v2 stretch evaluator** derived from SPEC-019 with one fundamental correction:

```text
MANDATORY_CREDENTIAL_ABSENT
must not independently produce EXCESSIVE_STRETCH
```

Capability stretch may still become excessive when independent evidence establishes:

- core professional-function mismatch;
- specialist technical-skill gap;
- domain-expertise gap;
- explicit professional-depth/years gap;
- other already-approved SPEC-019 capability reasons.

A missing academic degree may coexist with those gaps but must not be their proxy.

Do not weaken genuine capability gaps simply because credential evidence moved out of stretch.

## Constitutive credentials

SPEC-021 supports a narrow distinction for credentials intrinsic to the profession or role, such as professional licence/admission or postdoctoral/clinical/professional qualification structures.

However, SPEC-022 must **not promote Architecture C into a runtime hard rule**.

In shadow diagnostics:

- identify high-confidence constitutive cases separately;
- preserve conservative `UNKNOWN` when lexical evidence is insufficient;
- do not equate every named certification, advanced degree, or professional qualification with constitutive status;
- do not use constitutive credential evidence to silently recreate `EXCESSIVE_STRETCH` inside the capability object.

If a constitutive role also has independent professional-function evidence, stretch may be excessive for that independent reason.

## Independent capability-gap evidence

Use only candidate/vacancy evidence already permitted by SPEC-019 and deterministic rules added under this packet.

Where the 144 degree-driven cases contain explicit requirements, attempt to identify the actual capability reason, for example:

- `TECHNICAL_SKILL_GAP`
- `DOMAIN_EXPERTISE_GAP`
- `PROFESSIONAL_FUNCTION_GAP`
- `SENIORITY_DEPTH_GAP`

Do not import SPEC-021 private human labels into production candidate facts or matching rules.

The 36 human judgments are validation evidence, not a lookup table.

## Primary replay population

Reconstruct the exact current/frozen-compatible population corresponding to the 144 SPEC-019 degree-driven excessive-stretch cases.

Report any state drift explicitly. Do not silently claim historical identity if the operational population changed.

For the verified replay population, produce the transition matrix:

| Old SPEC-019 class | Shadow v2 class | Count |
|---|---|---:|
| EXCESSIVE_STRETCH | EXCESSIVE_STRETCH | ? |
| EXCESSIVE_STRETCH | MANAGEABLE_STRETCH | ? |
| EXCESSIVE_STRETCH | CURRENT_FIT | ? |
| EXCESSIVE_STRETCH | UNRESOLVED | ? |

For cases remaining excessive, report sanitized reason distributions showing which **independent capability reasons** now support the result.

The most important diagnostic is whether `MANDATORY_CREDENTIAL_ABSENT` disappears as a capability-distance reason.

## Full-corpus shadow replay

Run the shadow evaluator read-only over the broader current corpus where evidence permits.

Report:

- old/new stretch-class distribution;
- transition matrix;
- reason distribution;
- credential-compatibility distribution;
- unresolved rate;
- employer/role-family concentration where repository-safe;
- overlap with market status;
- overlap with seniority guard;
- overlap with decision preferences;
- compatible semantic-cache availability.

No production object may be overwritten.

## Frozen human-evidence replay

Validate the shadow architecture against:

1. SPEC-021 completed 36-case evidence;
2. SPEC-020 terminated exploratory evidence, separately and with its limitations;
3. SPEC-019 frozen 60-item compute-worthiness evidence where identity-compatible.

Required checks:

- no known human WORTH case becomes newly excessive solely due to credential handling;
- constitutive/non-substitutable human cases remain representable as credential evidence;
- cases with independent technical/domain/function gaps can remain excessive for those actual gaps;
- cases with strong/partial substitution are not forced excessive merely because a degree is absent;
- preference-only or market-only evidence does not enter capability stretch.

Do not pool SPEC-020 and SPEC-021 proportions.

## Shadow credential reasoning

SPEC-022 may implement deterministic credential semantics where source wording is sufficiently explicit, including:

- explicit `or equivalent experience`;
- explicit preferred/ideal/desirable language;
- explicit hard wording;
- professional/licence wording where narrowly identifiable.

For experiential substitution, be conservative.

Do not create broad heuristics such as:

```text
20 years experience => degree substituted
```

If deterministic candidate evidence cannot establish substitution safely, use `UNKNOWN` and leave later reasoning to semantic compute.

## Semantic compute economics

Recalculate compute-allocation ceilings after the corrected shadow replay.

At minimum report:

- number of the 144 cases resolved excessive by independent deterministic capability evidence;
- number moved to current-fit/manageable;
- number moved to unresolved;
- number requiring potential deeper semantic reasoning;
- compatible cache hits versus misses;
- projected Luna calls and cost using the frozen cost basis;
- comparison with SPEC-011 baseline (~3,109 calls / ~$8.24) and the SPEC-021 conservative credential ceiling (~131 calls / ~$0.347).

These are diagnostics, not authorized spend.

No semantic calls are authorized.

## Key success criteria

SPEC-022 is successful if it demonstrates a coherent representation even if many cases become unresolved.

Required invariants:

1. generic academic credential absence never independently establishes capability `EXCESSIVE_STRETCH`;
2. credential compatibility and capability stretch have independent identities/fingerprints;
3. genuine independent capability gaps remain detectable;
4. constitutive credential evidence is preserved separately;
5. human strong/partial substitution evidence is representable without capability contradiction;
6. market access and preferences remain orthogonal;
7. no semantic reassessment is required;
8. zero operational SQLite writes;
9. deterministic replay.

Do not optimize for minimizing `UNRESOLVED`. Conservative uncertainty is preferable to false rejection.

## No runtime promotion

SPEC-022 is shadow-only.

Do not change:

- production recommendation;
- ranking;
- filtering;
- semantic allocation;
- candidate profile/capabilities/preferences;
- market policy/status;
- seniority guard;
- source configuration/adapters;
- semantic-v1;
- semantic cache;
- Phase 3 scoring;
- clustering/lifecycle behavior;
- historical judgments.

Do not migrate SQLite.

## Fingerprints

Introduce separate deterministic identities for:

- credential-compatibility rules;
- credential-compatibility inputs;
- credential-compatibility assessment;
- shadow stretch-v2 rules/inputs/assessment.

Prove that existing production fingerprints remain unchanged, including:

- semantic-profile identity;
- scoring identity;
- market-policy identity;
- decision-preference identity;
- current production stretch identity where applicable.

## Privacy

Private/local and Git-ignored:

- vacancy-level replay details;
- joins to SPEC-021 human judgments;
- candidate-specific detailed credential/capability evidence;
- detailed transition evidence.

Repository-safe aggregate may contain:

- counts;
- transition matrices;
- generic reason distributions;
- fingerprints;
- cost estimates;
- architecture conclusions;
- no vacancy titles/URLs/descriptions or human notes.

## Implementation shape

Prefer a clean reusable module boundary, for example:

- `credential_compatibility.py`
- shadow-v2 additions to or alongside `stretch_evidence.py`
- a dedicated replay/audit CLI;
- declarative rules/config where appropriate;
- frozen experiment configuration;
- repository-safe aggregate output.

Do not mutate SPEC-019 historical semantics in place. Preserve its evaluator identity for reproducibility.

## Tests

Add offline regression coverage proving at least:

- degree absence alone cannot produce shadow-v2 excessive stretch;
- independent technical/domain/function gaps can;
- preferred degree does not behave as hard credential;
- explicit equivalent-experience wording is represented correctly;
- constitutive credential evidence remains separate from capability stretch;
- credential and stretch fingerprints are independent;
- candidate preferences cannot affect credential compatibility or stretch;
- market status cannot affect capability stretch;
- human strong/partial substitution cases are not forced excessive by degree absence;
- frozen constitutive examples remain representable;
- SPEC-019 historical replay remains reproducible under its old identity;
- semantic-v1/cache remain untouched;
- deterministic replay;
- zero SQLite writes/external calls;
- repository-safe output excludes private evidence.

Run the full offline suite and `git diff --check`.

## Stop conditions

Stop for human review rather than improvising if:

- removing degree evidence makes independent capability requirements unreconstructable for a material share of the 144 cases;
- deterministic capability-gap rules require broad fuzzy inference;
- credential semantics cannot be separated from candidate preference;
- constitutive detection would require unsafe lexical generalization;
- frozen human WORTH evidence is newly classified excessive for an unsupported reason;
- implementation would require semantic-v1 changes, external model calls, or operational-state mutation;
- multiple plausible shadow representations produce materially different transition matrices.

## Documentation

Update as appropriate:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING_MODEL.md`
- `README.md`
- `docs/decisions.yaml`
- `experiments/registry.yaml`
- SPEC-022 status

Clearly mark Architecture B as shadow-implemented but not runtime-promoted.

## Deliverable

Return a structured report containing:

A. repository/state integrity;
B. CredentialCompatibilityAssessment contract;
C. shadow stretch-v2 contract;
D. reconstructed 144-case population identity;
E. 144-case transition matrix;
F. independent capability-reason distribution;
G. credential-compatibility distribution;
H. full-corpus shadow replay;
I. SPEC-021 human-evidence replay;
J. SPEC-020 compatibility;
K. SPEC-019 WORTH protection;
L. semantic-compute economics;
M. fingerprint/cache implications;
N. privacy/persistence/invariant checks;
O. tests/validation;
P. files changed;
Q. architecture conclusion;
R. recommended next packet;
S. recommended commit message.

No commit or push until normal review approval.
