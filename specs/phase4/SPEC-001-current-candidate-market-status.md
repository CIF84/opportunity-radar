# SPEC-001 — Current Candidate Market Status

Implementation status: implemented as a pure evaluator; routing and
recommendation integration remain out of scope for this packet.

## Purpose

Implement Phase 4 Slice 2 only: a pure post-detail, candidate-dependent `CurrentCandidateMarketStatus` evaluator.

This work follows the accepted Phase 4 specification, current architecture, project status, and decisions in the repository. Before implementation, read:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/decisions.yaml`
- `SPEC.md`

Confirm the implementation preserves all frozen Phase 1–3 invariants.

## Scope

Build a pure evaluator that takes:

- current normalized job evidence;
- `CandidateProfile.market_access_policy` implemented in Phase 4 Slice 1;

and returns a structured market assessment:

```text
CurrentCandidateMarketAssessment
- status: IN_SCOPE | UNCERTAIN | OUT_OF_SCOPE
- reasons: structured deterministic reasons
- evidence: structured source/job evidence used by those reasons
```

Use repository naming conventions if a slightly different type name is more consistent. Do not introduce persistence merely to preserve this conceptual name.

## Responsibility boundary

### Retrieval scope

Existing `DetailSelectionPolicy` remains:

- candidate-independent;
- pre-detail;
- concerned only with whether detail retrieval is worthwhile;
- conservative under missing evidence;
- irrelevant to `JobInstance` lifecycle closure except that complete inventory remains lifecycle evidence.

It does **not** determine candidate suitability.

### CurrentCandidateMarketStatus

The new evaluator is:

- post-detail;
- candidate-dependent;
- deterministic;
- concerned with geographic practicality, remote-employment access, explicit work-authorization/residency requirements, and required-language practicality;
- independent from semantic fit;
- independent from Phase 2 lifecycle;
- independent from recommendation/ranking in this slice.

It must not:

- close or deactivate jobs;
- mutate `JobInstance`;
- write Phase 2 state;
- modify semantic inputs;
- invalidate semantic cache merely because market policy changes;
- make international tax/employment-law determinations;
- contain employer-specific branches.

### Hard eligibility

Existing hard eligibility remains separate for non-market hard constraints. Do not redesign or merge it in this slice.

## Status semantics

### `IN_SCOPE`

Use only when current evidence affirmatively establishes compatibility with the candidate's configured normal market access.

Examples include:

- onsite/hybrid in Prague under the current primary-candidate policy;
- remote work explicitly permitting Czech-based employment;
- other explicitly compatible remote arrangements represented by the configured policy.

### `OUT_OF_SCOPE`

Use only when current evidence explicitly establishes incompatibility.

Examples include:

- foreign onsite/hybrid role under a Prague-only normal onsite/hybrid policy;
- remote role explicitly restricted to an incompatible country/residency;
- explicit work-authorization requirement the candidate policy marks `INCOMPATIBLE`;
- required language explicitly represented as `NONE` when no suitable alternative language is permitted.

`OUT_OF_SCOPE` is a candidate decision-state result, not lifecycle state.

### `UNCERTAIN`

Use when material evidence is incomplete or ambiguous.

Examples include:

- remote employment geography unspecified;
- authorization is material but not established;
- incomplete multi-location evidence;
- ambiguous relocation/working-time requirement;
- location evidence cannot be normalized confidently.

Missing evidence must not silently become explicit incompatibility.

## Confirmed primary-candidate policy

Use the version-2 candidate configuration already implemented in Slice 1. Do not duplicate these facts as Python constants.

The accepted policy is:

- normal onsite/hybrid: Prague only;
- foreign onsite/hybrid: normally out of normal shortlist scope;
- relocation: exceptional, not normal market access;
- remote: acceptable from Czechia when Czech-based employment is explicitly permitted or otherwise confirmed compatible, with European-compatible working time;
- foreign country-specific work authorization: do not infer it;
- Czech work access: confirmed;
- Czech: native/professional;
- English: professional;
- Slovak: comprehension-only but must not be rejected solely for language;
- French: not professionally usable;
- Japanese: `NONE`;
- unresolved market practicality remains `UNCERTAIN`.

Do not encode spouse/family rationale into evaluator logic. Runtime policy should consume only the configured market-access representation.

## Minimum normalization/evidence rules

Implement only reusable normalization required to evaluate the observed Phase 4 regression cases.

Support, where evidence is present in normalized detail:

- explicit country names/codes;
- Prague/Czech evidence;
- common city/state/country evidence required by the regression fixtures;
- explicit remote geography;
- incomplete/multi-location markers;
- explicit authorization/residency requirements;
- explicit required languages.

Prefer declarative/shared normalization.

Do not attempt comprehensive world-geography resolution.

Do not parse employer-specific URL structures to infer candidate market status.

Do not treat arbitrary two-letter substrings as country codes.

Preserve raw evidence in assessment reasons/evidence where useful for auditability.

## Required behavior cases

Add deterministic tests for at least:

1. Prague onsite/hybrid → `IN_SCOPE`.
2. Foreign onsite/hybrid → `OUT_OF_SCOPE` for the current primary policy.
3. Czech-compatible remote explicitly permitted → `IN_SCOPE`.
4. Remote explicitly restricted to another incompatible country → `OUT_OF_SCOPE`.
5. Remote geography/employment eligibility unknown → `UNCERTAIN`.
6. Incomplete multi-location evidence → `UNCERTAIN` unless compatible evidence conclusively resolves the opportunity under the normative Phase 4 rules.
7. Explicit incompatible work-authorization/residency requirement → `OUT_OF_SCOPE`.
8. Missing authorization evidence → preserve `UNCERTAIN` where authorization is material; never invent incompatibility.
9. Japanese required + candidate language `NONE` → `OUT_OF_SCOPE` unless a suitable alternative language is explicitly allowed.
10. Slovak requirement + candidate `COMPREHENSION_ONLY` → must not be rejected solely for language.
11. Unknown/unparseable geography → `UNCERTAIN`, not `OUT_OF_SCOPE`.
12. Exceptional relocation posture must not make ordinary foreign onsite/hybrid roles `IN_SCOPE`.

## Live Validation v1 regression cases

Create fixtures/tests from preserved evidence where practical for these known cases. Do not mutate historical validation artifacts.

Expected direction:

- J&J US-only → `OUT_OF_SCOPE` once post-detail US evidence is available.
- Pfizer permanent US work-authorization requirement → `OUT_OF_SCOPE`.
- Pure Storage Santa Clara onsite → `OUT_OF_SCOPE`.
- WPP Chicago/New York → `OUT_OF_SCOPE`.
- Red Hat Tokyo + Japanese requirement → `OUT_OF_SCOPE`.
- WPP Mexico City → `OUT_OF_SCOPE`.
- WPP Düsseldorf → `OUT_OF_SCOPE`.
- DBG Cork incomplete multi-location → `UNCERTAIN` rather than confidently eligible/in-scope.
- Wrike/Klaxoon Belgium/remote with unresolved Czech employment feasibility → `UNCERTAIN`.

Where preserved evidence is insufficient to construct a faithful regression fixture, document that limitation rather than fabricating missing evidence.

## Structured reasons

The evaluator must return enough structured information to explain *why* a status was assigned.

Prefer a small controlled reason vocabulary, for example conceptually:

```text
PRAGUE_LOCATION_COMPATIBLE
CZECH_REMOTE_CONFIRMED
FOREIGN_ONSITE_INCOMPATIBLE
REMOTE_COUNTRY_RESTRICTED
WORK_AUTHORIZATION_INCOMPATIBLE
WORK_AUTHORIZATION_UNKNOWN
REQUIRED_LANGUAGE_INCOMPATIBLE
REMOTE_ELIGIBILITY_UNKNOWN
INCOMPLETE_MULTI_LOCATION
GEOGRAPHY_UNKNOWN
```

Use naming consistent with the codebase. Avoid prose-only decisions.

A reason should reference the evidence that triggered it where practical.

## Fingerprinting

If the accepted Phase 4 `SPEC.md` requires or clearly benefits from an assessment fingerprint, implement a deterministic fingerprint over the evaluator's relevant inputs/output suitable for later retrospective manifests.

Do not add database persistence for it in this slice.

Do not include irrelevant opaque adapter metadata.

## Cache guarantees

Tests must prove:

- changing only `market_access_policy` may change market assessment;
- semantic-profile fingerprint remains unchanged for policy-only changes;
- existing semantic-v1 cache identity remains reusable;
- evaluator execution makes zero semantic-assessor calls.

Do not alter the existing semantic contract, model, reasoning effort, prompt, or scoring preferences.

## Lifecycle guarantees

Tests must prove:

- evaluating an active job as `OUT_OF_SCOPE` does not close it;
- evaluator execution does not mutate Phase 2 state;
- no SQLite migration is introduced;
- complete inventory remains the sole authority for presence/closure.

Use pure-function tests where possible. Add repository integration tests only where needed to prove non-mutation.

## Portability

Both candidate profiles must use the same evaluator and schema.

Do not add primary-candidate branches.

The portability profile may produce different statuses solely because its configuration differs.

## Explicit non-goals

Do not implement in this slice:

- live-validation filtering/routing;
- `OUT_OF_SCOPE` shortlist exclusion;
- `UNCERTAIN → REVIEW` recommendation cap;
- opportunity clustering;
- preferred variant selection;
- decision preferences;
- seniority recommendation guard;
- semantic-v2;
- scoring-weight changes;
- database migration;
- UI;
- automated actions.

## Documentation

Update documentation only enough to state that the **pure CurrentCandidateMarketStatus evaluator** is implemented.

Do not claim ranking integration is implemented.

Update `docs/STATUS.md` and `docs/ARCHITECTURE.md` only if necessary to preserve current truth.

If implementation creates a material architectural decision not already covered by `docs/decisions.yaml`, propose the decision record in the deliverable rather than adding unnecessary governance records automatically.

## Validation

Run:

```bash
.venv/bin/pytest -q
git diff --check
```

No live source calls.
No semantic-model calls.

## Deliverable

Return:

A. files changed
B. evaluator contract
C. status/reason vocabulary
D. normalization rules implemented
E. Live Validation regression-case results
F. lifecycle and semantic-cache guarantees
G. portability result
H. full offline test result
I. ambiguities or evidence limitations discovered
J. recommended Slice 3 implementation packet
K. recommended commit boundary

Do not commit.
