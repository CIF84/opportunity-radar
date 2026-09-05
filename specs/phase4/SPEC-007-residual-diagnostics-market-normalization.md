# SPEC-007 — Residual Diagnostics and Bounded Market Normalization

## Status

`IMPLEMENTED_AWAITING_APPROVAL`

## Purpose

Investigate the residual Phase 4 retrospective disagreements without tuning the
semantic model, scoring weights, clustering contract, or frozen preference-effect
mapping. Implement only the smallest deterministic correction that is already
supported by explicit evidence: the Texas/US market-normalization gap.

This packet is diagnostic-first. Its goal is to distinguish:

- deterministic normalization defects;
- incomplete preference matching/evidence;
- appropriate unresolved market uncertainty;
- genuine residual semantic/rubric failures.

Before implementation, read:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING_MODEL.md`
- `docs/decisions.yaml`
- `experiments/registry.yaml`
- Phase 4 in `SPEC.md`
- `SPEC-006`
- the sanitized Phase 4 replay aggregate registered in the repo

Detailed private replay evidence may be read locally if present, but it must not
be committed or pushed.

## Frozen items

Do not change:

- `gpt-5.6-luna`;
- reasoning effort `low`;
- `phase3-semantic-v1`;
- Phase 3 weights;
- preference stance values;
- preference effect mapping (`+0.4/+0.2/0/-0.3`, aggregate cap `[-1,+1]`);
- clustering rules;
- seniority guard policy;
- historical judgments;
- official v1 report;
- Phase 2 lifecycle/identity semantics.

No external semantic calls. No live-source calls.

## Part A — Texas market-normalization correction

### Known defect

The frozen Phase 4 replay found review 27, a Texas vacancy, remained
`UNCERTAIN` instead of becoming `OUT_OF_SCOPE`, while other explicit foreign
market cases were correctly excluded.

### Required diagnosis

Identify the exact normalized/detail evidence available for review 27 and the
exact reason current `CurrentCandidateMarketStatus` failed to recognize it as
explicit US geography.

Do not assume the cause in advance. Record:

- available raw/structured location evidence;
- normalization path used;
- rule that failed or was absent;
- whether the same pattern occurs elsewhere in the 406-job corpus.

### Allowed correction

Implement the smallest reusable, employer-independent normalization rule that
converts explicit US state/location evidence such as `Texas` / `El Paso, Texas`
into explicit United States geography when the evidence is unambiguous.

The rule must be declarative/shared where practical and must not rely on source
URL parsing or employer-specific branches.

Do not build a comprehensive world geography engine.

### Required controls

Tests must prove:

- `El Paso, Texas` -> explicit US evidence -> `OUT_OF_SCOPE` for the current
  candidate's Prague-only onsite/hybrid policy;
- `Santa Clara, California` remains correctly out of scope;
- arbitrary words containing state-code-like substrings do not become US states;
- ambiguous names shared with non-US places remain uncertain unless sufficient
  contextual evidence exists;
- Czech/Prague evidence remains unchanged;
- remote-eligibility semantics remain unchanged.

If a small declarative state-name list is the cleanest solution, use it. Avoid
postal-code heuristics that could recreate the prior `CZ` false-positive class.

## Part B — Residual disagreement diagnostics

Diagnose the three non-semantic residual opportunity disagreements identified by
SPEC-006:

- review 13 — advisory/execution preference;
- review 17 — orthopaedics preference;
- review 23 — Klaxoon market uncertainty + preference.

Also retain the two known semantic residuals as controls:

- review 10 — GoodData senior BI Solution Architect;
- review 18 — EY FP&A Assistant Director.

For each case, produce a structured diagnostic that answers:

1. What market status was produced and why?
2. What cluster/preferred variant applied?
3. Which semantic concepts/dimensions were reused?
4. Which preference concepts matched?
5. Which expected relevant preferences failed to match, if any?
6. What numeric preference effect resulted?
7. What recommendation existed before/after deterministic caps?
8. What exact architectural layer best explains the residual disagreement?

Use existing disagreement categories where applicable.

## Preference diagnostics: no policy tuning

For reviews 13, 17, and 23, determine whether the frozen preference layer failed
because of:

- missing text/structured evidence;
- taxonomy/matching-rule coverage;
- current preference concept too broad/narrow;
- bounded effect too weak to cross a terminal threshold;
- interaction with market uncertainty cap;
- human judgment depending on employer/product conviction not yet representable.

Do **not** change preference stances or numeric effect weights in this packet.

A matching-rule correction is allowed only when the current candidate preference
already exists and the job evidence clearly expresses that same concept, but the
declarative matcher fails to recognize it. Such a correction must be generic,
non-employer-specific, and independently testable.

If the case instead requires a new candidate preference/conviction concept,
report it as a proposed future policy change and do not add it here.

## Klaxoon uncertainty

Review 23 must receive special treatment.

The frozen policy intentionally treats unresolved Czech employment access for a
foreign/remote role as `UNCERTAIN`, capped at `REVIEW`.

Do not force Klaxoon to `OUT_OF_SCOPE` or `IN_SCOPE` without explicit current
evidence. Determine whether its residual disagreement is actually an error or a
correctly conservative unresolved case.

If the human decision depends partly on product conviction rather than market
access, keep those causal layers separate.

## Corrected retrospective replay

After the bounded Texas normalization fix (and only any clearly justified generic
matching correction), rerun the Phase 4 replay offline as a **new immutable
corrected retrospective run**.

Do not overwrite the SPEC-006 replay.

Label this run explicitly as:

```text
POST_HOC_CORRECTED_RETROSPECTIVE
```

or equivalent.

It is not a new independent validation batch.

Report changes relative to SPEC-006:

- market-status counts;
- opportunity shortlist units;
- attention recall;
- top-attention acceptance;
- ranking agreement;
- APPLY acceptance;
- residual disagreements;
- gate status changes;
- number of decisions changed solely by Texas normalization;
- number changed by any allowed matching correction.

Zero semantic calls remain mandatory.

## Experiment integrity

The corrected replay must record:

- parent SPEC-006 replay identity/hash;
- Git commit/dirty state;
- changed rule fingerprints;
- unchanged frozen policy fingerprints;
- zero-call evidence;
- sanitized aggregate receipt suitable for Git;
- detailed replay rows only in ignored local/private artifacts.

Do not commit candidate- or judgment-derived detailed evidence.

## Decision output

The main deliverable is not merely a new metric. It is a recommendation for what
the next prospective experiment should test.

Classify each residual into one of:

```text
FIXED_DETERMINISTIC_NORMALIZATION
FIXED_GENERIC_PREFERENCE_MATCHING
CORRECTLY_UNCERTAIN_MARKET_ACCESS
UNREPRESENTED_PREFERENCE_OR_CONVICTION
SEMANTIC_V1_RESIDUAL
OTHER
```

Then recommend whether we are ready to design a prospective Phase 4 validation
batch without changing semantic-v1.

## Tests

Add tests proving at least:

- Texas regression becomes `OUT_OF_SCOPE`;
- no regression in Prague/Czech/remote cases;
- normalization is employer-independent;
- diagnostic classification is deterministic;
- preference diagnostics do not mutate preference state/effect policy;
- corrected replay performs zero semantic/live calls;
- official v1 and SPEC-006 artifacts remain unchanged;
- detailed corrected replay evidence remains ignored/private;
- sanitized aggregate is safe to track;
- SQLite schema remains v3;
- Phase 2 state remains byte-identical/read-only.

## Validation

Run:

```bash
.venv/bin/pytest -q
git diff --check
```

Run the corrected offline replay and report its run ID.

## Deliverable

Return:

A. files changed
B. exact Texas root cause
C. normalization correction implemented
D. corpus-level impact of the correction
E. structured diagnostics for reviews 10, 13, 17, 18, 23, and 27
F. any generic preference-matching correction, with evidence
G. corrected retrospective run ID
H. before/after replay metrics vs SPEC-006
I. residual disagreement classification
J. zero-call/cache/lifecycle/privacy guarantees
K. test result
L. recommendation: ready/not ready for prospective Phase 4 validation
M. if ready, proposed prospective validation design questions (do not implement)
N. recommended commit message

Do not commit or push until explicit approval.
