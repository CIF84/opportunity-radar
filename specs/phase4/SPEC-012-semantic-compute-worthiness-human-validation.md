# SPEC-012 — Human Validation of Semantic Compute Worthiness

## Status

`APPROVED_FOR_IMPLEMENTATION`

## Purpose

Design and prepare a bounded, cache-blind human labeling experiment that tests
whether Opportunity Radar can predict **where expensive semantic reasoning is
worth spending**.

SPEC-011 showed that current cheap deterministic evidence cannot reduce the
~3,109 routed semantic cache misses aggressively while preserving all five known
historical human-APPLY opportunity units. Rather than immediately introduce a
cheap secondary model or pay for full-population semantic completion, collect
new human evidence about the compute-allocation decision itself.

Primary question:

> Given only evidence available before a new semantic-v1 assessment, can a cheap
> deterministic triage meaningfully separate opportunities that deserve deep
> semantic reasoning from those that do not?

This experiment evaluates **semantic compute worthiness**, not final job fit,
application intent, or the frozen SPEC-008 ranking protocol.

## Context

Read before implementation:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING_MODEL.md`
- `experiments/semantic_compute_allocation_v1.yaml`
- SPEC-008 through SPEC-011
- sanitized SPEC-011 aggregate receipt

Preserve all existing lifecycle, market, clustering, semantic-cache, preference,
scoring, seniority, and prospective-protocol contracts.

## Authority boundary

This packet authorizes:

- offline/read-only use of the fresh operational SQLite state;
- deterministic, cache-blind sample construction;
- creation of a private human-review packet for semantic compute worthiness;
- sanitized aggregate preview/manifest evidence;
- code/tests/docs needed to prepare and later record/evaluate this experiment.

This packet does **not** authorize:

- Luna or any other external model call;
- live source refresh;
- creation of the SPEC-008 prospective validation batch;
- modification of the frozen SPEC-008 protocol;
- promotion of the SPEC-011 triage into runtime policy;
- changes to semantic-v1, scoring weights, preference effects, market rules,
  clustering, or seniority guard;
- automated preference/profile learning;
- external actions.

## Human label

The human is not asked whether they would apply.

For each sampled opportunity, ask:

> **Would it be worth spending deeper AI reasoning on this opportunity before
> deciding whether it deserves your attention?**

Use exactly three primary labels:

```text
WORTH_DEEP_ASSESSMENT
NOT_WORTH_DEEP_ASSESSMENT
NEED_MORE_INFO
```

Interpretation:

- `WORTH_DEEP_ASSESSMENT`: pre-semantic evidence leaves enough plausible value,
  uncertainty, or surprising upside that deeper reasoning is justified;
- `NOT_WORTH_DEEP_ASSESSMENT`: available evidence is already sufficient to say
  deeper semantic reasoning would probably not be a good use of compute;
- `NEED_MORE_INFO`: the review packet itself lacks enough pre-semantic evidence
  to make the compute-worthiness judgment.

Do not translate these labels into APPLY/DONT_APPLY.

## Optional reason taxonomy

Allow optional structured reasons without requiring them for every item.
Keep the taxonomy small and compute-allocation-oriented, for example:

```text
PLAUSIBLE_TARGET_ROLE
HIGH_UPSIDE_OR_LEARNING
AMBIGUOUS_ROLE_REQUIRES_INTERPRETATION
OBVIOUS_FUNCTIONAL_MISMATCH
OBVIOUS_SENIORITY_MISMATCH
OBVIOUS_DOMAIN_MISMATCH
MARKET_ACCESS_ALREADY_DECISIVE
INSUFFICIENT_EVIDENCE
OTHER
```

The human may add a short private note.

Reasons are diagnostic evidence and must not silently mutate candidate
preferences or runtime rules.

## Sampling unit

Sample `OpportunityCluster`, not posting.

Use the current fresh post-historical-exclusion routed population used by
SPEC-011. The sample must be **cache-blind**:

- semantic cache hit/miss status cannot influence selection;
- semantic score/recommendation cannot influence selection;
- existing semantic payload content cannot influence selection;
- historical human labels cannot influence selection except for explicit
  exclusion of previously reviewed opportunity members where required to keep
  this experiment prospective relative to human labeling.

Preferred variant may be chosen using only already-approved deterministic
market/cluster evidence available before semantic assessment.

## Proposed sample size

Freeze **60 opportunity clusters** for human review.

This is intentionally a learning experiment, not a statistically definitive
product validation.

Use three triage strata from the unpromoted SPEC-011 audit:

```text
20 SEMANTIC_PRIORITY
20 SEMANTIC_OPTIONAL
20 SEMANTIC_DEFER
```

If `SEMANTIC_DEFER` has fewer than 20 eligible fresh clusters, include all
available DEFER items and reallocate the shortfall to OPTIONAL while preserving
an explicit shortfall record. Do not weaken the DEFER rule merely to fill quota.

Do not change sample size after seeing human labels.

## Employer balance

The fresh routed population is heavily concentrated in one employer (~57%).
Prevent the review from becoming an EY-specific experiment.

Predeclare:

- maximum **5 selected opportunities per employer** across the full 60-item
  sample where population permits;
- deterministic employer-balanced selection within each stratum;
- if the cap prevents filling a stratum, relax only through a documented,
  deterministic fallback order after all under-cap employers are exhausted.

Report every cap relaxation.

## Selection evidence

Selection may use only the SPEC-011 triage inputs and deterministic seed.

Freeze and record:

- experiment ID/version;
- Git commit;
- operational database SHA-256;
- triage contract/version/fingerprint;
- candidate market-policy fingerprint where relevant;
- clustering contract/version;
- historical-exclusion evidence hash;
- deterministic seed;
- sample IDs/order privately;
- sanitized stratum/employer counts publicly.

Do not use semantic cache state as a selection feature.

## Blind review surface

The human review should expose enough **pre-semantic** evidence to answer the
compute-worthiness question without exposing the system's triage label.

For each opportunity show, privately:

- employer;
- title;
- preferred/current location/work-mode evidence;
- concise deterministic market-status evidence where useful;
- employment type/department if available;
- normalized description or a bounded readable excerpt sufficient to understand
  the role;
- source link when available so the human can inspect the vacancy;
- explicit note if evidence is incomplete.

Do NOT foreground or reveal during initial labeling:

- `SEMANTIC_PRIORITY/OPTIONAL/DEFER`;
- semantic cache hit/miss;
- existing semantic score/dimensions;
- current system recommendation/rank;
- historical human labels;
- expected cost.

The blind packet should be private/local and Git-ignored.

## Review order

Use a deterministic shuffled order across strata/employers so the human is not
presented with 20 PRIORITY, then 20 OPTIONAL, then 20 DEFER.

Freeze review order before labels.

## Reserves and availability

Freeze **5 reserves per requested stratum** where population permits.

If a selected opportunity becomes unavailable before review:

- use the next frozen same-stratum reserve;
- preserve the original selection and replacement reason in private evidence;
- do not resample based on observed human labels.

If a stratum lacks reserves, record the limitation rather than changing the
triage definition.

## Evaluation metrics

Do not use final job-ranking gates from SPEC-008. This experiment asks a
different question.

After all labels are collected, report:

### Per-stratum worthiness rate

For each triage stratum:

```text
WORTH_DEEP_ASSESSMENT / adjudicated labels
NOT_WORTH_DEEP_ASSESSMENT / adjudicated labels
NEED_MORE_INFO count
```

### Priority precision

```text
WORTH among SEMANTIC_PRIORITY / adjudicated SEMANTIC_PRIORITY
```

### Defer safety

Critical metric:

```text
1 - (WORTH among SEMANTIC_DEFER / adjudicated SEMANTIC_DEFER)
```

Also report the raw number of WORTH items incorrectly placed in DEFER.

### Optional yield

How often OPTIONAL is actually worth deeper assessment.

### Information sufficiency

`NEED_MORE_INFO` rate overall and by stratum.

### Employer effects

Sanitized per-employer counts/label rates only where privacy-safe and sample
size makes interpretation reasonable. Do not overinterpret small cells.

## Predeclared directional gates

Because this is an exploratory learning experiment, use directional gates rather
than production promotion criteria.

A compute-allocation policy is **not ready for promotion** unless at minimum:

- `SEMANTIC_DEFER` has >=90% NOT_WORTH safety among adjudicated DEFER items;
- no more than 2 adjudicated DEFER items are labeled WORTH;
- `SEMANTIC_PRIORITY` worthiness precision is >=60%;
- overall `NEED_MORE_INFO` <=20%;
- no evidence of catastrophic employer-specific blind spots in reviewed data.

Passing these gates is necessary but not sufficient for runtime promotion.

If DEFER safety fails, explicitly conclude that current cheap triage cannot be
used as a hard semantic-compute gate.

## Counterfactual economics

After labels, estimate what semantic spend would have been under simple policies
such as:

- assess PRIORITY only;
- assess PRIORITY + OPTIONAL;
- assess all except DEFER;
- assess all routed opportunities.

For each report:

- projected current-population calls/cost;
- observed human WORTH recall on the 60-item sample;
- observed WORTH precision among assessed sample items;
- caveat that sample-based estimates are exploratory.

Do not promote a policy solely because it is cheap.

## Future-model implications

The report should explicitly distinguish three possible conclusions:

1. **Deterministic triage is sufficient to test further.**
2. **A cheap learned/model-based screening signal is justified.**
3. **Full semantic assessment is simpler/safer than a screening layer at current
   scale and cost.**

Do not implement a cheap model in this packet.

## Interaction-learning implications

Treat the 60 labels as experiment evidence, not automatic preference updates.

The future feed/control-panel vision may generate similar compute-worthiness
signals implicitly, but this packet must preserve the governance loop:

```text
human interaction
  -> observation
  -> hypothesis
  -> bounded evaluation
  -> explicit promotion
```

No self-modifying candidate model.

## Privacy

Private/local only:

- sampled opportunity identities;
- titles;
- URLs;
- descriptions/excerpts;
- human labels/reasons/notes;
- replacement history;
- detailed per-item evaluation.

Repository-safe aggregate evidence may include:

- experiment/run identity;
- configuration fingerprints/hashes;
- sample/stratum/employer aggregate counts;
- aggregate metrics/gates after review;
- projected calls/cost;
- limitations/conclusions;
- private-artifact hashes.

Update `.gitignore`/`OPERATING_MODEL.md` if needed to make this boundary durable.

## Implementation requirements

Implement preparation and later evaluation tooling, but **do not fabricate or
pre-fill human labels**.

Suggested CLI shape, adapted to repository conventions:

```text
opportunity-radar-semantic-worthiness prepare
opportunity-radar-semantic-worthiness record ...
opportunity-radar-semantic-worthiness report ...
```

The preparation command must be zero-call/read-only against operational SQLite.

Recording must be append-only or supersession-safe under the same principles as
Live Validation judgments.

Evaluation must not require semantic calls.

## Preparation deliverable in this packet

Run the preparation step after implementation and report:

- whether 60 selected items can be filled;
- actual stratum counts;
- reserves per stratum;
- employer-cap relaxations;
- historical-overlap exclusions;
- market-status distribution;
- evidence completeness/missingness;
- private blind-review artifact path;
- sanitized aggregate preview path;
- confirmation that triage labels are hidden from blind review;
- confirmation of zero semantic/live calls.

Do not ask the human to start reviewing until implementation is approved and
committed.

## Tests

Add tests proving at least:

- selection is deterministic;
- cache hit/miss cannot affect selection;
- semantic payload/score cannot affect selection;
- historical labels cannot affect selection;
- employer cap and fallback are deterministic;
- DEFER shortfall handling is deterministic;
- review order is frozen and mixed;
- blind packet hides triage/cache/semantic recommendation evidence;
- reserves are frozen before labels;
- record semantics are append-only/supersession-safe;
- metrics and gates are deterministic;
- private evidence is ignored;
- sanitized aggregate contains no candidate/job identity or human notes;
- operational SQLite remains byte-identical;
- zero semantic/live calls.

## Experiment registry/status

Register this as a separate experiment in `experiments/registry.yaml` and update
`docs/STATUS.md` after implementation with preparation status only.

Do not claim triage validation before the human has labeled the sample.

## Validation

Required:

```bash
.venv/bin/pytest -q
git diff --check
```

Confirm:

- external semantic calls: 0;
- live-source calls: 0;
- prospective SPEC-008 batch creation: 0;
- compute-worthiness judgments before human review: 0;
- operational SQLite unchanged;
- frozen SPEC-008 protocol unchanged.

## Deliverable

Return:

A. files changed
B. experiment/protocol identity
C. CLI/workflow implemented
D. selection contract and cache-blind proof
E. selected stratum counts
F. reserve counts
G. employer distribution/cap relaxations
H. historical-overlap exclusion count
I. evidence completeness/missingness
J. blind-review privacy check
K. sanitized aggregate preview
L. zero-call/read-only proof
M. tests/validation
N. exact human review workflow after approval
O. recommended commit message

Do not commit or push until explicit approval.
