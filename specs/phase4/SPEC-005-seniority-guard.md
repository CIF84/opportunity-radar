# SPEC-005 — Candidate-configurable Seniority Guard

## Status

`APPROVED_FOR_IMPLEMENTATION`

## Purpose

Implement the remaining deterministic Phase 4 correction before retrospective replay: a candidate-configurable seniority guard that caps explicitly junior/graduate opportunities at `LOW_PRIORITY` without making them universally ineligible.

This is intentionally a small slice. Before implementation, read:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING_MODEL.md`
- `docs/decisions.yaml`
- Phase 4 in `SPEC.md`
- prior Phase 4 work packets, especially market routing and decision preferences

Preserve all frozen Phase 1–3 invariants and implemented Phase 4 behavior.

## Accepted decision

DR-020 is authoritative:

> When explicit junior/graduate evidence matches the candidate's seniority-floor policy, cap recommendation at `LOW_PRIORITY` rather than mark the vacancy `INELIGIBLE`.

Important consequences:

- junior/graduate roles are not universally invalid;
- the rule is candidate configuration, not global Python policy;
- missing or ambiguous seniority evidence cannot activate the guard;
- a high semantic/base/preference-adjusted score cannot erase explicit down-leveling when the guard applies;
- the guard changes terminal decision policy only and must not invalidate semantic assessment.

## Scope

Implement only:

1. deterministic detection of explicit junior/graduate evidence;
2. candidate-configurable guard activation using the existing Phase 4 candidate policy representation where possible;
3. structured guard evidence/reasons;
4. recommendation precedence integration so an active guard caps the terminal recommendation at `LOW_PRIORITY`;
5. regression coverage for Live Validation review 25 / the DBG Cork junior role;
6. manifest/report evidence sufficient for the upcoming frozen retrospective replay.

Do not implement retrospective replay in this packet.

## Non-goals

Do NOT:

- make junior roles `INELIGIBLE` globally;
- lower semantic dimension scores;
- change Phase 3 scoring weights;
- change preference-effect weights;
- modify semantic-v1;
- infer seniority from salary alone;
- infer seniority from years-of-experience alone unless the existing Phase 4 specification explicitly requires it;
- build a general career-level ontology;
- add fuzzy title classification;
- add model-based seniority inference;
- change market status;
- change clustering membership;
- change preferred-variant selection except through normal downstream recommendation evidence;
- migrate SQLite;
- call external models or live sources.

## Responsibility boundary

The guard is a deterministic post-semantic decision-policy constraint.

Conceptually:

```text
preferred variant
  -> semantic/base composite
  -> decision preference effect
  -> adjusted score / base recommendation
  -> existing market/eligibility caps
  -> seniority guard
  -> final recommendation
```

If the implemented precedence architecture already centralizes caps in another deterministic order, integrate there rather than duplicate policy. The invariant is that the most restrictive applicable terminal cap wins.

The guard must not become part of:

- Phase 2 lifecycle;
- `CurrentCandidateMarketStatus`;
- semantic assessment identity;
- opportunity-cluster identity;
- preference matching/effect policy.

## Candidate configuration

Use the existing versioned candidate configuration introduced in Phase 4 Slice 1 if it already represents the junior/graduate cap losslessly.

If the representation is present, consume it rather than adding duplicate configuration.

If the current schema is insufficient, make the smallest generic schema extension necessary and preserve these fingerprint boundaries:

- semantic-profile fingerprint unchanged for guard-only changes;
- scoring-preference fingerprint unchanged unless the existing specification explicitly places the seniority guard there;
- market-policy fingerprint changes only if the guard is intentionally already part of that policy contract;
- decision-preference fingerprint remains independent from the seniority guard unless current architecture/specification explicitly says otherwise.

Do not add candidate-specific Python branches.

## Explicit evidence only

The guard activates only on explicit, high-confidence evidence that the vacancy itself is junior/graduate level.

Acceptable evidence may include normalized title or structured source/detail fields with controlled patterns such as conceptually:

- `junior`
- `graduate`
- `entry level`
- an equivalent clearly explicit source seniority label already normalized by the repository

Do not treat ambiguous terms as explicit evidence merely to improve retrospective metrics.

Examples that must NOT automatically trigger the guard without explicit policy evidence:

- `assistant director`
- `associate` when employer semantics are unknown
- `analyst`
- low salary alone
- low semantic seniority-alignment score alone
- fewer years of required experience alone

A semantic `seniority_alignment=1` may be diagnostic evidence, but it must not by itself activate the deterministic guard because that would make semantic output own the hard cap.

## Structured result

Add a small pure result contract, using repository naming conventions, conceptually:

```text
SeniorityGuardAssessment
- active: bool
- terminal_cap: LOW_PRIORITY | null
- reason_code
- evidence
- policy_fingerprint / input fingerprint where useful
```

Prefer a controlled reason vocabulary such as:

```text
EXPLICIT_JUNIOR_ROLE
EXPLICIT_GRADUATE_ROLE
NO_EXPLICIT_DOWNLEVEL_EVIDENCE
POLICY_DISABLED
```

Do not encode only prose.

## Recommendation precedence

Required behavior:

- active guard → final recommendation is at most `LOW_PRIORITY`;
- inactive guard → recommendation unchanged;
- guard never promotes a recommendation;
- `INELIGIBLE` remains `INELIGIBLE`;
- market `UNCERTAIN` remains at most `REVIEW`, but if junior guard also applies, the more restrictive `LOW_PRIORITY` cap wins;
- `OUT_OF_SCOPE` remains excluded from normal shortlist before this guard matters;
- missing semantic dimensions / other existing caps keep their established behavior.

Use existing recommendation ordering rather than inventing a parallel numeric ranking system.

## Live Validation v1 regression

Primary regression case:

### Review 25 — Deutsche Börse Group, Cork junior role

Historical human judgment:

- `DONT_APPLY`;
- disagreement categories included deterministic eligibility and scoring/calibration;
- explicit concern: Ireland-based and explicitly junior, materially below appropriate career seniority.

Phase 4 market routing should already treat incomplete Cork multi-location evidence as `UNCERTAIN` under the preserved regression case.

Required Phase 4 decision behavior for the explicit junior evidence:

```text
market status: UNCERTAIN
base/adjusted recommendation may otherwise be higher
junior guard: active
final recommendation: LOW_PRIORITY
```

Do not rewrite the historical judgment or v1 assessment.

If the preserved repository evidence does not actually contain explicit junior/graduate text for this case, report that evidence limitation rather than fabricating a trigger. In that situation, add a faithful synthetic explicit-junior regression and leave the historical case marked non-adjudicable for this deterministic guard.

## Tests

Add focused tests for at least:

### Activation

- explicit `junior` role + enabled candidate policy → cap `LOW_PRIORITY`;
- explicit `graduate` role + enabled candidate policy → cap `LOW_PRIORITY`;
- explicit entry-level equivalent supported by declared rules → cap if included;
- candidate policy disabled/different portability profile → no cap where appropriate.

### Non-activation

- ambiguous `analyst` → no guard;
- `assistant director` → no guard;
- `associate` without governed meaning → no guard;
- low salary only → no guard;
- semantic `seniority_alignment=1` only → no guard;
- missing seniority evidence → no guard.

### Precedence

- APPLY + active guard → LOW_PRIORITY;
- REVIEW + active guard → LOW_PRIORITY;
- LOW_PRIORITY + active guard → LOW_PRIORITY;
- INELIGIBLE + active guard → INELIGIBLE;
- market `UNCERTAIN` + active guard → LOW_PRIORITY;
- market `OUT_OF_SCOPE` remains excluded;
- inactive guard preserves the existing preference-adjusted recommendation exactly.

### Cache/lifecycle/clustering

- guard-only policy/evidence evaluation makes zero semantic calls;
- existing semantic assessment ID remains reusable;
- semantic-profile fingerprint unchanged;
- cluster identity/fingerprint unchanged;
- preferred-variant membership logic unchanged;
- market status unchanged;
- Phase 2 state/events unchanged;
- SQLite schema remains v3.

### Portability

- both candidate profiles use one generic guard implementation;
- different candidate policy can produce different guard results without Python branching.

## Manifest / replay evidence

Extend newly generated validation/routing manifests only as needed to preserve:

- guard active/inactive;
- reason/evidence;
- recommendation before guard;
- final recommendation after guard;
- relevant policy fingerprint.

Do not alter historical v1 artifacts.

No persistence migration is required for this experiment unless repository evidence proves otherwise. If a migration appears necessary, stop and report why.

## Documentation

Update only enough to preserve current truth after implementation:

- `docs/STATUS.md`;
- `docs/ARCHITECTURE.md` if the implemented boundary needs to be shown;
- Phase 4 implementation markers in `SPEC.md`;
- this work packet status/result notes if repository convention uses them.

Do not claim retrospective Phase 4 validation has occurred.

## Validation

Run:

```bash
.venv/bin/pytest -q
git diff --check
```

No live-source calls.
No external semantic calls.
No commit/push until explicit approval.

## Deliverable

Return:

A. files changed
B. guard contract
C. explicit evidence rules
D. recommendation precedence
E. DBG Cork regression result/evidence limitation
F. portability behavior
G. cache/lifecycle/clustering guarantees
H. manifest changes
I. full offline validation result
J. ambiguities discovered
K. recommended SPEC-006 retrospective replay packet
L. recommended commit message

Do not commit or push until explicit approval.
