# SPEC-017 — Partial Geography Semantics Audit

Status: `IMPLEMENTED_LOCALLY_AWAITING_REVIEW`

## Purpose

Audit whether current candidate-market routing correctly distinguishes **explicit geographic incompatibility** from **insufficient geographic evidence**, especially for onsite/hybrid vacancies where the country is known but city is absent.

This packet is prompted by SPEC-016 evidence from Mews: Czechia appears among location alternatives, work mode is hybrid, but no Czech city is supplied. Current routing marks all 11 detailed Mews clusters `OUT_OF_SCOPE` because onsite/hybrid work is only accepted in Prague. That may be semantically too strong if the source never established a non-Prague city.

The candidate policy itself is not under review:

> Normal onsite/hybrid work is acceptable in Prague only.

The question is whether the evaluator is claiming `OUT_OF_SCOPE` when the evidence only supports `UNCERTAIN`.

## Governing principle

Do not infer a negative fact from missing evidence.

Conceptually:

```text
explicit Prague hybrid
→ IN_SCOPE

explicit Brno hybrid
→ OUT_OF_SCOPE

Czechia hybrid, city absent
→ UNCERTAIN

foreign-country hybrid
→ OUT_OF_SCOPE
```

This is an evidence-semantics audit, not a relaxation of candidate policy.

## Protected boundaries

Do not change during the audit phase:

- candidate profile or market-access policy;
- accepted onsite/hybrid location (Prague only);
- remote-access policy;
- relocation policy;
- semantic model/prompt/contract/weights;
- existing semantic assessments/cache;
- clustering semantics;
- seniority guard;
- decision preferences;
- Phase 1/2 identity/lifecycle semantics;
- historical experiment evidence;
- source configuration except where read-only evidence inspection requires no production change.

No semantic calls are authorized.

## Phase 1 — Truth-table contract

First define and freeze a generic market-evidence truth table before changing evaluator behavior.

At minimum cover:

| Work arrangement evidence | Geography evidence | Expected status |
|---|---|---|
| hybrid | Prague, Czechia | `IN_SCOPE` |
| onsite | Prague, Czechia | `IN_SCOPE` |
| hybrid | Brno, Czechia | `OUT_OF_SCOPE` |
| onsite | Ostrava, Czechia | `OUT_OF_SCOPE` |
| hybrid | Czechia, city absent | `UNCERTAIN` |
| onsite | Czechia, city absent | `UNCERTAIN` |
| hybrid | Czech Republic alias, city absent | `UNCERTAIN` |
| hybrid | Germany | `OUT_OF_SCOPE` |
| onsite | United States | `OUT_OF_SCOPE` |
| remote | explicit Czech-compatible scope and access | existing frozen rule |
| remote | compatible region but employment access absent | `UNCERTAIN` under frozen rule |
| remote | explicit US-only restriction | `OUT_OF_SCOPE` |
| unspecified work mode | Prague | preserve existing governed behavior unless audit evidence proves contradiction |
| unspecified work mode | Czechia, city absent | preserve/diagnose explicitly; do not improvise |
| any | location entirely absent | `UNCERTAIN` unless another independent hard incompatibility exists |

The truth table must distinguish:

- explicit compatible evidence;
- explicit incompatible evidence;
- partially specified evidence;
- fully missing evidence;
- independent decisive incompatibilities such as explicit foreign employment restriction.

## Phase 2 — Root-cause inspection

Trace current behavior through:

- normalized location/work-mode evidence;
- market-status rules/configuration;
- evaluator precedence/composition;
- reason codes and fingerprints;
- any interaction between country-level and city-level matching.

For the 11 current Mews clusters, report exactly why each is classified `OUT_OF_SCOPE` and whether the reason is:

- explicit non-Prague city;
- explicit incompatible country;
- missing city treated as incompatible;
- independent authorization/work-hours incompatibility;
- another deterministic reason.

Do not assume all 11 share the same exact evidence without verifying.

## Phase 3 — Read-only corpus replay

Replay the proposed truth-table semantics against the entire current ACTIVE detailed corpus without mutating operational state.

At minimum report:

- current market-status counts;
- proposed market-status counts;
- number of changed assessments;
- transition matrix such as:
  - `OUT_OF_SCOPE → UNCERTAIN`
  - `OUT_OF_SCOPE → IN_SCOPE`
  - `UNCERTAIN → IN_SCOPE`
  - other transitions;
- reason-code distribution for changed cases;
- employer distribution of changed cases;
- work-mode distribution of changed cases;
- country/city-evidence completeness for changed cases;
- target-role-family overlap using the frozen SPEC-013 classifier;
- Mews-specific before/after counts.

Critical safety requirement:

A partial-geography correction should normally produce `OUT_OF_SCOPE → UNCERTAIN`, not `OUT_OF_SCOPE → IN_SCOPE`, unless explicit compatible city/access evidence exists independently.

If many `OUT_OF_SCOPE → IN_SCOPE` changes occur, stop and investigate before promotion.

## Phase 4 — Historical regression replay

Replay the proposed semantics against frozen reviewed evidence where market routing affected known decisions.

At minimum verify preserved outcomes for explicit incompatible cases previously validated, including representative:

- US-only / US-hybrid cases;
- Tokyo/Japanese or other explicit foreign cases;
- Mexico City / Düsseldorf / similar explicit foreign-city cases;
- corrected Texas evidence from SPEC-007;
- Prague explicit compatible cases;
- Cork/Klaxoon-style incomplete evidence cases that were intentionally `UNCERTAIN`.

Do not overwrite historical artifacts. Produce a new diagnostic result only.

## Phase 5 — Promotion decision

Only if the audit proves a generic evaluator defect should implementation change current market-status behavior.

Promotion criteria:

1. truth-table behavior is explicit and generic;
2. missing city under an otherwise compatible country does not become explicit incompatibility by absence alone;
3. explicit non-Prague Czech cities remain `OUT_OF_SCOPE` for onsite/hybrid;
4. explicit foreign onsite/hybrid remains `OUT_OF_SCOPE`;
5. remote policy is unchanged;
6. historical explicit-market regressions remain correct;
7. Mews partial-geography cases move only as supported by evidence;
8. no Phase 2 state/lifecycle mutation;
9. semantic cache identity remains unaffected;
10. zero semantic calls.

If evidence shows current behavior is already correct for generic semantics and Mews is source-specific ambiguity, do not modify market evaluator logic. Record the NO-CHANGE result.

## Implementation constraints if promoted

If a correction is justified:

- make the smallest generic deterministic change;
- preserve controlled reason codes or introduce a generic reason code only if needed for auditability;
- update market assessment fingerprint/version only as required by the existing identity contract;
- do not alter candidate policy fingerprint unless policy truly changed (it should not in this packet);
- do not add employer-specific logic;
- do not alter adapters merely to force a desired routing outcome;
- recompute diagnostic market assessments through the normal pure evaluator rather than rewriting historical persisted evidence.

## Mews re-evaluation

After any promoted correction, recompute Mews marginal coverage using current detailed evidence:

- `IN_SCOPE / UNCERTAIN / OUT_OF_SCOPE`;
- routed-cluster delta;
- target-family routed delta;
- semantic-call diagnostic count/cost without calls.

Do not claim Mews is newly `IN_SCOPE` merely because it is no longer `OUT_OF_SCOPE`. `UNCERTAIN` remains distinct.

## Broader source-expansion implication

Report whether partial geography is materially suppressing current-source usefulness beyond Mews.

Classify impact as one of:

- `MEWS_ONLY_EDGE_CASE`
- `BOUNDED_MULTI_SOURCE_CORRECTION`
- `MATERIAL_ROUTING_SEMANTICS_DEFECT`
- `NO_EVALUATOR_DEFECT`

This classification should depend on corpus replay magnitude and decision relevance, not raw changed-row count alone.

## Evidence/privacy

Repository-safe aggregate may contain:

- aggregate transition counts;
- employer-level changed counts;
- generic truth-table cases;
- fingerprints;
- historical regression verdicts;
- Mews aggregate counts;
- conclusions/limitations.

Keep detailed vacancy titles/descriptions/URLs and candidate-derived per-job evidence private/local unless already governed as public repository evidence.

Operational SQLite remains uncommitted.

## Documentation

Update as appropriate:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `README.md`
- `experiments/registry.yaml`
- SPEC-017 implementation status

If evaluator semantics change, document clearly that candidate policy did **not** change; evidence interpretation changed.

## Required tests

Add deterministic offline coverage for at least:

- Prague hybrid → `IN_SCOPE`;
- explicit Brno hybrid → `OUT_OF_SCOPE`;
- Czechia hybrid with city absent → `UNCERTAIN`;
- Czechia onsite with city absent → `UNCERTAIN`;
- explicit Germany hybrid → `OUT_OF_SCOPE`;
- explicit US-only remote → `OUT_OF_SCOPE`;
- missing location → `UNCERTAIN` absent another hard blocker;
- independent explicit incompatibility still dominates incomplete geography;
- aliases/normalization remain whole-token and deterministic;
- Mews regression fixture;
- historical explicit-market regression fixtures;
- no semantic calls;
- no SQLite mutation during audit/replay;
- candidate policy fingerprint unchanged if evaluator correction is promoted.

Run full offline suite and `git diff --check`.

## Stop conditions

Stop and report rather than improvising if:

- the desired correction would require changing candidate policy rather than evidence semantics;
- source evidence cannot distinguish country alternatives from actual vacancy geography;
- a generic fix would make explicit foreign cases uncertain;
- large unexpected `OUT_OF_SCOPE → IN_SCOPE` transitions appear;
- operational state would need rewriting to evaluate the hypothesis;
- unrelated code/config divergence is discovered.

## Deliverable

Return a structured report containing:

A. truth-table contract;
B. current evaluator root cause;
C. Mews evidence diagnosis;
D. whole-corpus transition matrix;
E. changed-case evidence/reason distribution;
F. employer/source concentration of changes;
G. target-family impact;
H. historical regression replay;
I. candidate-policy fingerprint/semantic-cache invariance;
J. evaluator change, if any;
K. Mews re-evaluation;
L. impact classification;
M. privacy/evidence boundary;
N. tests and validation;
O. files changed;
P. recommended next packet;
Q. recommended commit message.

No commit or push until normal review/approval.
