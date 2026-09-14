# SPEC-019 — Stretch Evidence Boundary Audit

Status: `IMPLEMENTED_LOCALLY_AWAITING_REVIEW`

## Purpose

Define and empirically test the evidence boundary between:

- `CURRENT_FIT`
- `MANAGEABLE_STRETCH`
- `EXCESSIVE_STRETCH`
- `UNRESOLVED`

without changing runtime ranking, recommendation, semantic-v1, or candidate capability facts.

The goal is to determine whether cheap, explicit evidence can safely identify obvious fit and obvious excessive stretch while preserving the ambiguous middle as the region where deeper semantic reasoning has highest decision value.

This packet is an **audit/representation experiment**, not a new rejection policy.

## Why this exists

The frozen 60-opportunity compute-worthiness experiment produced only three `WORTH_DEEP_ASSESSMENT` judgments. Qualitatively, those cases shared a useful pattern: the opportunity aligned strongly with desired trajectory, but qualification fit was uncertain enough that deeper reasoning could change the decision.

Many `NOT_WORTH_DEEP_ASSESSMENT` cases instead contained obvious professional/domain/seniority gaps requiring substantial requalification, or other decisive evidence.

SPEC-018 explicitly preserved the distinction between capability and preference. SPEC-019 must now test whether **stretch distance itself** can be represented from evidence without using career attraction as a proxy for capability.

## Governing principle

```text
CURRENT_FIT
core requirements are substantially supported by current candidate evidence

MANAGEABLE_STRETCH
material gaps exist, but transferable capability/experience makes candidacy plausibly bridgeable and deeper reasoning has decision value

EXCESSIVE_STRETCH
one or more core requirements establish a professional/specialist/seniority gap that is not plausibly bridged by current transferable evidence

UNRESOLVED
available evidence is insufficient or contradictory; do not guess
```

`MANAGEABLE_STRETCH` does not mean `APPLY`.
`EXCESSIVE_STRETCH` does not mean the career direction is unattractive.
`CURRENT_FIT` does not mean the opportunity is desirable.

Stretch is a capability-distance object only.

## Protected conceptual boundaries

Keep these independent:

- market/hard eligibility;
- candidate capability;
- career preference/direction;
- stretch distance;
- semantic compute worthiness;
- recommendation/action intent.

Examples:

- a US-only role may be market-ineligible regardless of stretch;
- an account-management role may be current-fit but unattractive;
- an AI-transformation role may be manageable stretch and attractive;
- a senior ML-engineer role may be excessive stretch even if highly attractive;
- a mundane HR-data role may be current-fit or manageable but still unattractive.

Do not collapse these into one score.

## Evidence authority

Stretch classification may use only explicit vacancy requirements and frozen candidate capability/experience evidence.

Candidate direction/preferences may be shown diagnostically but must not affect stretch classification.

Permitted vacancy evidence categories include:

- explicit profession/function;
- explicit required years of experience;
- explicit required specialist domain experience;
- explicit required technical skills/technology depth;
- explicit education/license/certification requirements;
- explicit people/technical leadership expectations;
- explicit seniority wording when role-relevant;
- explicit responsibility scope;
- bounded structured semantic requirement evidence already available from compatible cached assessments, if identity-compatible and used read-only.

Do not infer missing requirements as satisfied or unsatisfied.

## Candidate-side evidence

Use the existing versioned candidate profile and semantic capability representation without modification.

Candidate evidence may include:

- capability level/confidence;
- years/domain history;
- organizational context;
- leadership history;
- education facts;
- language/work-access facts only where they are actual qualification requirements rather than market routing;
- existing experience/domain depth;
- current developing technical capabilities.

Do not upgrade SQL/Python/software engineering/security/cloud/medical/legal/accounting or other skills merely because the candidate is interested in learning them.

## Core-requirement model

Define a deterministic/auditable representation such as `StretchRequirementAssessment` containing at least:

- requirement category;
- normalized requirement concept;
- vacancy evidence/provenance;
- requirement strength: `CORE`, `PREFERRED`, or `CONTEXTUAL`;
- candidate evidence/provenance;
- support state: `SUPPORTED`, `PARTIAL`, `UNSUPPORTED`, `UNKNOWN`;
- gap severity where applicable;
- controlled reason code.

Define a parent `StretchAssessment` containing:

- final class;
- decisive requirements/reasons;
- unresolved requirements;
- input/policy/rules fingerprints;
- no preference-derived inputs.

Exact names may differ if existing architecture suggests a cleaner generic contract.

## Conservative classification policy

The first proposal must prefer `UNRESOLVED` over false certainty.

A plausible starting policy to test, not blindly assume:

### CURRENT_FIT

Require no decisive unsupported CORE requirement and enough positive support to establish that the candidate already operates in the core profession/function at approximately the required level.

### EXCESSIVE_STRETCH

Require explicit high-confidence evidence of at least one decisive CORE gap such as:

- vacancy requires a core profession the candidate does not possess (e.g. lawyer, medical specialist, warehouse operator, Linux-kernel engineer);
- specialist technical/domain expertise is central and candidate evidence is explicitly absent/developing far below requirement;
- explicit seniority/experience requirement is materially beyond candidate evidence in the same profession;
- mandatory degree/license/certification is absent and genuinely required for the role;
- multiple independent core gaps jointly establish substantial requalification.

Do not classify excessive stretch merely because a title contains `Senior`, `Principal`, `Manager`, or `Engineer`.

### MANAGEABLE_STRETCH

This class requires more care. It should represent a bounded middle where:

- at least one material CORE/PREFERRED gap exists;
- no decisive excessive-stretch rule fires;
- substantial transferable evidence supports adjacent responsibilities/function;
- the remaining gap is plausibly one of depth, tooling, domain adjacency, or narrower experience rather than wholesale professional requalification.

If this cannot be established deterministically with acceptable precision, leave the case `UNRESOLVED` and recommend semantic reasoning rather than forcing `MANAGEABLE_STRETCH`.

## Human-evidence evaluation set

Use the frozen 60-item semantic compute-worthiness experiment as the primary human evidence set, without changing its labels.

The audit should derive a private adjudication view from explicit human reasons where available, separating:

1. stretch-related rejections;
2. preference-only rejections;
3. market-only rejections;
4. unavailable/insufficient-evidence cases;
5. WORTH cases where qualification uncertainty was part of the stated reason.

Do not treat all 57 NOT_WORTH items as `EXCESSIVE_STRETCH`.

At minimum, the three frozen WORTH cases must be protected from deterministic `EXCESSIVE_STRETCH` unless explicit human evidence itself clearly supports that classification; any such conflict is a stop condition for promotion.

## Calibration / validation discipline

Avoid fitting a rule independently to every reviewed example.

Predeclare a small controlled rule set based on generic requirement categories, then evaluate it against the frozen sample.

Report confusion-style metrics separately for:

- detecting human-evident excessive stretch;
- protecting WORTH/manageable-or-unresolved cases;
- current-fit precision where human evidence supports it;
- unresolved rate.

The audit must distinguish **coverage** from **precision**. A conservative classifier that resolves fewer cases safely may be preferable to a broad classifier with false excessive-stretch decisions.

## Required safety gates

Do not promote any runtime stretch behavior in SPEC-019.

For the architecture to qualify for a later runtime experiment, require at minimum:

1. zero frozen WORTH cases classified `EXCESSIVE_STRETCH`;
2. zero preference-only NOT_WORTH cases called excessive solely because they are disliked;
3. zero market-only NOT_WORTH cases called excessive solely because geography/access fails;
4. explicit profession mismatches are classified correctly where evidence is sufficient;
5. missing evidence yields `UNRESOLVED`, not unsupported by default;
6. candidate preferences are absent from the stretch fingerprint/input contract;
7. zero semantic calls and zero semantic-cache mutation;
8. deterministic replay.

Report directional precision/coverage rather than inventing a pass threshold unsupported by the small sample.

## Current-corpus replay

Run the proposed stretch classifier read-only over the current active/routed corpus where evidence is sufficient.

Report:

- counts by `CURRENT_FIT / MANAGEABLE_STRETCH / EXCESSIVE_STRETCH / UNRESOLVED`;
- counts by employer and broad role family where repository-safe;
- decisive reason distribution;
- evidence-coverage gaps;
- overlap with market status;
- overlap with current decision-preference effects;
- overlap with seniority guard;
- compatible semantic-cache availability;
- how many opportunities would remain candidates for deeper reasoning under hypothetical conservative boundaries.

This is diagnostic only. Do not filter/rank/recommend differently.

## Compute-allocation counterfactual

Using the frozen 60-item human evidence, calculate counterfactuals such as:

- semantic reasoning on `MANAGEABLE_STRETCH + UNRESOLVED` only;
- semantic reasoning on all except `EXCESSIVE_STRETCH`;
- optional preservation of a small exploration/control sample from excessive stretch.

Report human-WORTH recall and projected call reduction, but do not promote a compute policy.

Compare with the earlier SPEC-012/SPEC-011 findings where the existing PRIORITY triage achieved 3/3 observed WORTH recall but only 15% precision.

The key question is whether stretch evidence can remove obvious false-positive compute candidates without losing the interesting middle.

## Relationship to deterministic rejection

SPEC-019 should produce an architecture recommendation for a later deterministic-rejection layer.

A future rejection layer may combine independently proven high-confidence negatives such as:

```text
explicit market incompatibility
explicit hard eligibility failure
explicit excessive stretch
explicit strong role-family aversion
stale/unavailable opportunity
```

But SPEC-019 may implement only the stretch evidence/audit contract. It must not build the combined rejection layer.

## Fingerprints and persistence

Stretch rules/configuration must have their own deterministic fingerprint if implemented as code/config.

They must not alter:

- semantic-profile fingerprint;
- Phase 3 scoring fingerprint;
- market-policy fingerprint;
- decision-preference fingerprint;
- semantic cache identity;
- cluster identity;
- lifecycle state.

No SQLite migration is authorized. Store experiment results in immutable local/private artifacts plus repository-safe aggregate evidence.

## Privacy

Private human reasons and per-vacancy stretch evidence remain local/ignored.

Repository-safe output may include:

- aggregate class counts;
- generic reason counts;
- fingerprints;
- sanitized validation metrics;
- architecture conclusions;
- no raw human notes or judgment-linked vacancy identities.

## Protected invariants

Do not change:

- candidate profile/capabilities/preferences;
- market policy/status semantics;
- source configuration/adapters;
- semantic-v1 model/prompt/reasoning/contract;
- Phase 3 scoring weights;
- decision-preference effect weights;
- clustering semantics;
- seniority guard;
- historical judgments;
- Phase 1/2 lifecycle/identity contracts;
- semantic assessments/cache.

No live-source or external semantic calls are authorized.

## Documentation

Update as appropriate:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `README.md`
- `experiments/registry.yaml`
- SPEC-019 implementation status

Clearly mark stretch as diagnostic/unpromoted.

## Tests

Add offline coverage proving at least:

- preferences cannot affect stretch class/fingerprint;
- market status cannot masquerade as capability stretch;
- explicit profession mismatch can produce excessive stretch;
- title seniority alone cannot;
- mandatory qualification absence is distinguished from preferred qualification absence;
- developing adjacent capability can remain manageable/unresolved rather than automatically excessive;
- missing candidate or vacancy evidence yields unresolved;
- all three frozen WORTH cases are protected from excessive stretch under the tested rules;
- deterministic replay/fingerprints;
- zero semantic calls/cache writes;
- no lifecycle/source/cluster/recommendation changes;
- repository-safe aggregate excludes private evidence.

Run full offline suite and `git diff --check`.

## Stop conditions

Stop for human review rather than broadening rules if:

- any frozen WORTH case becomes `EXCESSIVE_STRETCH`;
- manageable-stretch classification requires preference evidence;
- core requirements cannot be extracted with bounded/auditable rules;
- profession/domain taxonomy boundaries are ambiguous enough to require fuzzy matching;
- candidate capability evidence is insufficient to distinguish current fit from excessive stretch for important classes;
- implementing the audit would require semantic-v1 changes or external model calls.

## Deliverable

Return a structured report containing:

A. evidence inspected;
B. stretch contract and fingerprints;
C. controlled rule set;
D. frozen human-sample adjudication categories;
E. frozen-sample stretch results;
F. WORTH protection and excessive-stretch detection metrics;
G. current-corpus class distribution;
H. evidence-coverage limitations;
I. compute-allocation counterfactuals;
J. interaction with market/preference/seniority boundaries;
K. privacy/persistence/invariant checks;
L. architecture conclusion;
M. whether a later runtime experiment is justified;
N. tests/validation;
O. files changed;
P. recommended next packet;
Q. recommended commit message.

No commit or push until normal review approval.

## Implementation result

The immutable local run `spec019-stretch-evidence-20260913-v3` implemented the
diagnostic contract without runtime integration. All eight safety gates passed:
all three frozen human-WORTH cases were protected, no market-only or
preference-only case became excessive stretch, omitted evidence remained
unresolved, replay was deterministic, and external/source/SQLite/cache writes
were zero.

Frozen-sample classes were 7 current fit, 24 manageable stretch, 9 excessive
stretch, and 20 unresolved. The nine excessive predictions had 100% directional
precision against the conservative private adjudication but covered only 39.1%
of its 23 human-evident excessive cases. The current 3,935-cluster corpus was
83.7% unresolved. Mandatory-degree evidence produced 144 of 171 current-corpus
excessive classifications, so direct runtime promotion is not authorized.

The detailed result remains private/local. The sanitized receipt and full
analysis are indexed by `experiments/registry.yaml` and documented in
`docs/stretch_evidence_boundary_audit.md`.
