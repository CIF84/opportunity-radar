# SPEC-021 Frozen Credential Evidence Preparation

Status: `PREPARED_AWAITING_HUMAN_REVIEW_APPROVAL`

This is the repository-safe preparation report for
`EXP-CREDENTIAL-EVIDENCE-SEMANTICS-002`. It contains aggregate evidence only.
The immutable evidence manifest and blind review packet remain private/local and
Git-ignored.

## Boundary

SPEC-021 is a new protocol identity. It does not reopen or reinterpret the
terminated SPEC-020 experiment. Preparation made no source or semantic-model
calls, wrote no operational SQLite state, created no human judgment, and changed
no credential, stretch, candidate, ranking, or recommendation behavior.

Evidence validity is based on captured wording, context, provenance,
completeness, and hashes. Source currentness is a separate field. No currentness
check was performed, so every prepared snapshot records
`SOURCE_CURRENTNESS_NOT_CHECKED`.

## Evidence populations searched

The read-only scan covered:

- 4,514 persisted detailed observation rows;
- 4,164 distinct `JobInstance` identities;
- 4,206 unique job/content versions after repeated identical observations were
  collapsed;
- 4,164 latest observation identities;
- 42 distinct historical content versions;
- 1,762 reconstructable, complete credential evidence snapshots.

This is broader than SPEC-020's 144 degree-driven excessive-stretch cases. The
expanded set exists to cover semantic rule space, not estimate operational
prevalence.

## Immutable evidence contract

Each private `CredentialEvidenceSnapshot` preserves stable job/source identity,
observation identity and timestamp, employer/title/URL, exact credential
statements, bounded source context, exact relevant modal terms, explicit years
and related requirements, normalized credential concept, source content hash,
completeness, validity, currentness, deterministic candidate substitution
evidence, and a snapshot fingerprint. Human interpretation is not part of the
snapshot.

The candidate projection includes degree fact, career/domain history, direct
capabilities, taxonomy-related transferable capabilities, explicit
none/developing capabilities, leadership, and role history. It excludes both
candidate preference layers. Omitted capability remains `UNKNOWN_NOT_NONE`.

## Semantic inventory

```text
EXPLICIT_HARD                       659
MIXED_MANDATORY_PREFERRED           216
DEGREE_OR_EQUIVALENT_EXPERIENCE     118
PREFERRED_OR_IDEAL                  153
GENERIC_OR_TEMPLATE                 354
AMBIGUOUS                           250
CONSTITUTIVE_OR_REGULATED            12
TOTAL                              1762
```

These deterministic classes are selection strata only. They are neither human
labels nor expected outcomes.

## Proposed frozen set

The smallest configured diverse set contains 36 cases:

```text
EXPLICIT_HARD                         6
DEGREE_OR_EQUIVALENT_EXPERIENCE       6
PREFERRED_OR_IDEAL                    5
MIXED_MANDATORY_PREFERRED             5
GENERIC_OR_TEMPLATE                   5
AMBIGUOUS                             5
CONSTITUTIVE_OR_REGULATED             4
```

Fourteen reserves are frozen: two per semantic class, usable only when a capture
is proven insufficient, conflicting, corrupt, or inconsistent. Later source
unavailability is not a replacement reason.

Seventeen employers are represented. No employer contributes more than five
selected cases. Constitutive/regulated controls are rare: the selected four are
necessarily concentrated in EY (three) and Johnson & Johnson (one). This is an
explicit limitation, not a prevalence estimate.

Candidate substitution signals in the proposed set are:

```text
DIRECT_MATCH_PRESENT                21
ADJACENT_TRANSFERABLE_PRESENT        6
DEVELOPING_OR_NONE_ONLY              3
NO_ASSERTED_MATCH                    6
```

## Integrity and privacy

Preparation identity:
`spec021-credential-evidence-preparation-20260916-v2`

```text
protocol fingerprint             b0d9b7946a7bf13c29e049920c2667a29ca5b04a6b56ce9570067cbbb4aacf26
evidence population fingerprint  1846d5c7115b09b3dfd68c986fb2d320476062d79cdbcd6c873790044e57e56a
selection fingerprint            599c54c428cb5491264c69d8f36130557b386749f3dd677dc43f4c9c99339ac2
sample/reserve fingerprint       cd791d527b594082bca39ada36780da80bea703464dc34fd39ee198e365a3550
private manifest SHA-256         bdac32b745b96c5d42533b246ea605f644481c014d9415fb08a77c90e3495e83
private blind packet SHA-256     2d3e1223b1595bf91cb25383b627e1bce0fd27a24021fc7cb4b2d23a34d642af
operational SQLite SHA-256       a07d53002dc22e07ba33946a1dfc172365d182e37133f6221f4ef48e2154ff23
```

Selection is deterministic and excludes candidate preferences, recommendation,
semantic score, cache status, stretch class, and historical human labels. The
blind packet omits deterministic strata and all runtime/previous human labels.
No v2 judgment or replacement log exists.

## Saturation protocol

After each ten substantive judgments, reporting may expose only an observed
reasoning-pattern inventory and blind-safe completion booleans. It never stops
automatically. `COMPLETED_REASONING_SATURATION` requires an explicit human
decision plus all predeclared coverage and no-new-pattern conditions.

## Gate

Review and commit this preparation before presenting Review 1. Runtime
credential/stretch behavior remains unchanged regardless of preparation
success.
