# SPEC-002 — Candidate Market Routing Integration

## Status

`APPROVED_FOR_IMPLEMENTATION`

## Purpose

Implement Phase 4 Slice 3 only: give the already implemented pure `CurrentCandidateMarketStatus` evaluator deterministic authority at the candidate-ranking boundary.

The goal is to prevent explicitly out-of-scope opportunities from entering the normal shortlist and to prevent unresolved market practicality from producing `APPLY`, while preserving Phase 1–3 lifecycle, semantic-v1, cache, and scoring invariants.

Before implementation, read the repository control plane and current normative Phase 4 specification:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING_MODEL.md`
- `docs/decisions.yaml`
- `SPEC.md`
- `specs/phase4/SPEC-001-current-candidate-market-status.md`

Do not rely on conversation context.

## Required behavior

At the candidate-ranking boundary, evaluate each current detailed job with `CurrentCandidateMarketStatus` before terminal shortlist/recommendation behavior.

Policy precedence for this slice:

```text
CurrentCandidateMarketStatus.OUT_OF_SCOPE
    -> excluded from the normal candidate shortlist
    -> no lifecycle mutation
    -> no closure/deactivation

CurrentCandidateMarketStatus.UNCERTAIN
    -> remains inspectable/rankable for verification
    -> terminal recommendation may be at most REVIEW

CurrentCandidateMarketStatus.IN_SCOPE
    -> existing Phase 3 behavior continues unchanged
```

The semantic model must not decide this precedence.

## Integration boundary

Integrate the evaluator where candidate-specific current opportunities enter Phase 3/live-validation decision/ranking flow.

Do not move candidate market policy into:

- adapters;
- retrieval scope;
- Phase 2 lifecycle;
- source normalization identity;
- semantic prompt/input;
- semantic cache identity.

If more than one candidate-ranking entry point exists, identify them and implement the smallest shared boundary that prevents divergent behavior.

## OUT_OF_SCOPE semantics

An `OUT_OF_SCOPE` job:

- remains a valid `ACTIVE` `JobInstance` while source lifecycle says it is active;
- retains its normalized observations and existing semantic assessments;
- is omitted from the normal candidate shortlist/ranked opportunity pool;
- must not be treated as source disappearance;
- must not create a false `CLOSED` event;
- must not delete or invalidate semantic cache rows;
- may remain visible in diagnostics/audit output with its market-status reason.

Do not convert market status into Phase 2 lifecycle state.

## UNCERTAIN recommendation cap

The confirmed candidate policy requires:

```text
UNCERTAIN -> maximum REVIEW
```

Implement this as deterministic terminal-policy composition.

Requirements:

- a semantic/composite result that would otherwise be `APPLY` becomes `REVIEW`;
- an existing `REVIEW` remains `REVIEW`;
- a more restrictive result such as `LOW_PRIORITY` or `INELIGIBLE` must not be promoted upward;
- missing market evidence must not become `OUT_OF_SCOPE` merely to avoid uncertainty;
- the cap must be explainable/auditable in output structures where recommendation reasons are represented.

Do not change Phase 3 scoring weights or semantic dimensions.

## IN_SCOPE behavior

For `IN_SCOPE`, existing Phase 3 composite and recommendation behavior must remain byte-for-byte/equivalently deterministic where practical.

This slice is routing/policy composition, not recalibration.

## Semantic call policy

Market routing must happen early enough to avoid unnecessary new semantic calls for `OUT_OF_SCOPE` jobs when no compatible cached assessment is needed for another purpose.

However, historical existing semantic assessments for jobs that are now `OUT_OF_SCOPE` must remain valid historical evidence and must not be deleted.

For `UNCERTAIN` jobs, semantic assessment may still be used because the opportunity remains a verification candidate; only the terminal recommendation is capped.

Tests must distinguish:

- new OUT_OF_SCOPE cache miss -> no semantic call in normal shortlist assessment path;
- OUT_OF_SCOPE with existing semantic assessment -> assessment remains stored/reusable but job is not shortlisted;
- UNCERTAIN cache miss -> semantic assessment may occur under existing policy, terminal recommendation <= REVIEW;
- IN_SCOPE -> existing semantic behavior.

Do not call external models during implementation/tests; use fake/deterministic assessors and existing cache fixtures.

## Live Validation / preflight behavior

Update live-validation preflight/assessment orchestration only as necessary to reflect the new candidate-market boundary.

Preflight should clearly report, at minimum:

- IN_SCOPE count;
- UNCERTAIN count;
- OUT_OF_SCOPE count;
- jobs eligible for semantic processing under the new routing policy;
- cache hits/misses and expected external calls for the jobs that actually require semantics.

OUT_OF_SCOPE jobs must not inflate expected semantic-call cost for normal candidate ranking.

Preserve the distinction between:

- source failures/detail incompleteness;
- market OUT_OF_SCOPE;
- market UNCERTAIN;
- hard eligibility.

Do not rewrite historical Live Validation v1 artifacts or judgments.

## Regression expectations from Live Validation v1

Use the existing Phase 4 regression fixtures and evaluator results. The routing integration must demonstrate that known explicit market failures no longer enter the normal shortlist:

- J&J US-only;
- Pfizer US hybrid/authorization case;
- Pure Storage Santa Clara onsite;
- WPP Chicago/New York;
- Red Hat Tokyo/Japanese;
- WPP Mexico City;
- WPP Düsseldorf.

The following must remain visible as uncertainty rather than being falsely rejected:

- DBG Cork incomplete multi-location;
- Klaxoon unresolved remote access.

If those uncertain cases would otherwise receive APPLY, the final recommendation must be REVIEW.

This is not yet the full retrospective replay experiment; do not create replacement official metrics in this slice.

## Hard eligibility composition

Preserve existing non-market hard eligibility behavior.

The most restrictive applicable deterministic state wins. Conceptually:

```text
market OUT_OF_SCOPE -> excluded from normal shortlist
hard INELIGIBLE -> INELIGIBLE
market UNCERTAIN -> recommendation <= REVIEW
otherwise -> existing Phase 3 recommendation
```

Do not redesign `EligibilityResult` unless a minimal interface adaptation is required. If overlap or ambiguity is discovered, report it rather than collapsing market and hard eligibility into one concept.

## Persistence and fingerprints

No SQLite migration is expected or desired for this slice.

Market assessments may be computed for runtime/preflight/reporting and preserved in experiment/run manifests where the existing design supports it.

Do not persist them into Phase 2 job lifecycle rows merely for convenience.

Policy-only changes must:

- recompute market status;
- recompute routing/caps;
- leave semantic-profile fingerprint unchanged;
- reuse existing semantic-v1 assessments when semantic inputs are unchanged.

Do not change the semantic cache identity.

## Required tests

Add focused tests proving at least:

1. `OUT_OF_SCOPE` active job is absent from normal ranked shortlist.
2. `OUT_OF_SCOPE` active job remains ACTIVE in Phase 2.
3. `OUT_OF_SCOPE` does not emit closure/content-change events.
4. new `OUT_OF_SCOPE` semantic cache miss causes zero semantic calls in normal ranking flow.
5. existing semantic assessment for an `OUT_OF_SCOPE` job is not deleted/invalidated.
6. `UNCERTAIN` would-be APPLY becomes REVIEW.
7. `UNCERTAIN` REVIEW remains REVIEW.
8. `UNCERTAIN` LOW_PRIORITY is not promoted.
9. `IN_SCOPE` recommendation behavior is unchanged.
10. hard `INELIGIBLE` remains at least as restrictive as before.
11. market-policy-only change can alter routing with zero semantic reassessment when compatible cached semantics exist.
12. preflight counts market statuses separately and estimates semantic calls after routing.
13. Live Validation v1 explicit foreign regression cases are removed from the normal shortlist.
14. Cork/Klaxoon uncertainty cases are retained and capped rather than rejected.
15. SQLite schema remains version 3.
16. full offline suite remains green.

Use synthetic tests for policy composition and existing frozen fixtures for historical regressions where evidence is adequate.

## Explicit non-goals

Do not implement:

- opportunity clustering;
- preferred variant selection;
- decision-preference representation/effects;
- seniority guard beyond anything already represented but not yet activated by later slices;
- retrospective Phase 4 metrics;
- prospective validation;
- semantic-v2;
- scoring-weight changes;
- model/prompt/reasoning changes;
- Phase 1/2 refactors;
- database migration;
- UI/alerts/scheduling;
- application automation.

## Documentation and work-packet state

After implementation, update current-state documentation only enough to state truthfully that market routing and the UNCERTAIN cap are implemented.

Do not mark this work packet committed/complete merely because code exists locally. Implementation and promotion/commit are separate authority transitions.

The implementation report must identify the exact files changed and validation evidence so the human decision layer can approve or reject promotion.

## Git / authority behavior

This repository follows the operating principle:

> Human governance should minimize human operations.

For this packet:

- Codex may inspect, implement, test, and prepare local changes.
- Codex must not commit or push during initial implementation.
- After the human/ChatGPT review explicitly approves the implementation, Codex may be instructed to commit and push the approved working tree itself.
- Before any later work packet is implemented, Codex should verify the working tree is clean and synchronize with `origin/main` when safe.
- If unexplained local changes, divergence, or conflicts exist, stop and report rather than overwrite or improvise.

## Validation

Run:

```bash
.venv/bin/pytest -q
git diff --check
```

No live source calls.
No external semantic calls.

## Deliverable

Return:

A. files changed
B. exact integration boundary
C. OUT_OF_SCOPE routing behavior
D. UNCERTAIN cap behavior
E. semantic-call/cache behavior
F. preflight/reporting changes
G. Live Validation regression results
H. lifecycle/persistence guarantees
I. tests/results
J. ambiguities discovered
K. recommended next work packet
L. recommended commit message

Do not commit or push until explicitly approved.
