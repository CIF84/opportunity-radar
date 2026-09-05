# SPEC-008 — Prospective Phase 4 Validation Design

## Status

`APPROVED_FOR_IMPLEMENTATION`

## Purpose

Design and implement the **preparation layer only** for a genuinely prospective,
cluster-sampled Phase 4 validation.

Do not execute paid semantic assessment or collect human judgments in this
packet. The output is a frozen prospective protocol plus a prepared/dry-run
batch manifest that can be reviewed before any external calls or human labels
exist.

The experiment must answer whether the committed Phase 4 architecture
generalizes to fresh opportunities without tuning against the historical
30-posting validation set.

Before implementation, read the repository control plane, Phase 4 specs,
experiment registry, the official v1 validation evidence, and the sanitized
SPEC-006/SPEC-007 aggregate receipts.

## Governing principle

The historical 30-case batch is now development evidence. It must not be used to
choose cases, thresholds, preference weights, semantic prompt changes, or
stopping rules for this prospective validation.

Prospective validation must freeze the protocol **before** human judgments are
recorded.

## Frozen product configuration

Keep frozen:

- `gpt-5.6-luna`;
- reasoning `low`;
- `phase3-semantic-v1`;
- Phase 3 scoring weights;
- candidate profile and semantic projection;
- market-access policy and market-status rules as committed after SPEC-007;
- clustering contract;
- preferred-variant policy;
- decision-preference state;
- preference matching rules;
- preference-effect mapping;
- seniority guard;
- recommendation thresholds;
- disagreement taxonomy.

This packet must record all relevant versions/fingerprints in the prospective
protocol manifest.

## Validation unit

The primary validation unit is an **OpportunityCluster**, not a source posting.

Each sampled cluster contributes at most one review item, using the deterministic
preferred active variant selected by the committed Phase 4 policy.

Preserve member-posting evidence so clustering and preferred-variant correctness
can be judged separately.

Human judgment must distinguish:

1. **attention decision** — does this opportunity deserve meaningful attention?
2. **application intent** — would the human actually apply now, given the
   available evidence?
3. **preferred variant agreement** — for multi-member clusters, is the system's
   selected variant the one the human would use?
4. **market-status agreement** — does `IN_SCOPE / UNCERTAIN / OUT_OF_SCOPE`
   reflect the human's practical interpretation?

Do not force these into one binary label.

## Prospective population

The batch must be prepared from a fresh current-state run performed after this
protocol is frozen, not from the historical v1 batch.

Population requirements:

- active detailed opportunities under the current committed architecture;
- cluster membership computed using the committed deterministic contract;
- all-out-of-scope clusters retained in the population for diagnostics but not
  eligible for normal attention sampling except the explicit market-control
  stratum below;
- no historical review number or prior human judgment may influence selection;
- previously reviewed opportunities should be excluded from the primary
  prospective sample when they can be identified deterministically, and their
  exclusion count must be reported.

If a fresh state refresh is required, preparation may specify the command and
cost/request estimate but must not execute live-source calls in this packet.

## Sample size

Freeze a target of **40 opportunity clusters**.

Rationale:

- materially larger than the 26 opportunity units in the retrospective replay;
- small enough for careful manual review;
- large enough that a handful of false positives cannot dominate the result;
- suitable as a directional validation, not a claim of population-level
  statistical certainty.

Do not increase or decrease the target after observing human outcomes.

If fewer than 40 eligible fresh clusters exist, include the full eligible
population and report the shortfall. Do not backfill with historical reviewed
opportunities merely to reach 40.

## Predeclared stratified sample

Prepare exactly these strata where population permits:

### A. Top attention — 15 clusters

Highest-ranked normal-attention clusters under the frozen Phase 4 decision
policy.

Purpose: measure whether the system's strongest recommendations deserve human
attention.

### B. Mid attention / REVIEW boundary — 10 clusters

Sample around the boundary where uncertainty, preference effects, or moderate
scores make prioritization difficult.

Use a deterministic selection rule defined in code/config before seeing human
judgments. Prefer clusters with final `REVIEW` or the nearest equivalent
boundary state.

Purpose: test calibration and whether uncertainty is useful rather than merely
conservative.

### C. Low-priority controls — 10 clusters

Deterministically sample from low-ranked/`LOW_PRIORITY` normal-market clusters.

Purpose: estimate missed attractive opportunities and preserve recall pressure.

### D. Market controls — 5 clusters

Sample explicit `OUT_OF_SCOPE` or strongly market-incompatible clusters that
otherwise have nontrivial semantic/base fit where possible.

Purpose: validate that market routing is rejecting the right opportunities.

These five are **control items**, not normal shortlist items, and must be labeled
as such in metrics.

If a stratum has insufficient population, use a predeclared deterministic
fallback order and record the transfer. Do not choose replacements manually.

## Sampling determinism and blindness

Selection must be reproducible from:

- population manifest;
- frozen configuration fingerprints;
- explicit deterministic sorting/sampling seed;
- protocol version.

Use a fixed seed recorded in the experiment configuration if random sampling is
needed inside a stratum.

Human judgments, historical disagreement categories, employer preferences from
v1 review notes, or retrospective residual identities must not influence sample
selection.

Avoid excessive employer concentration. Add a deterministic concentration rule:

- target maximum 4 sampled clusters per employer across the 35 normal-attention
  items;
- market controls may add at most 1 additional cluster from an employer;
- if the available population makes this impossible, relax only enough to fill
  the sample and record the relaxation.

This prevents EY/J&J-sized inventories from dominating the human review set.

## Semantic-call policy

Preparation must classify every prospective preferred variant as:

- compatible semantic cache hit;
- semantic cache miss;
- semantically unassessable from current detail.

This packet makes zero external semantic calls.

Before the later execution packet, report:

- expected external call count;
- estimated cost using the existing live-validation estimator;
- cache-hit count;
- unassessable count;
- model/reasoning/contract identity.

No execution packet may proceed until the human explicitly approves the
estimated external-call/cost budget.

## Human review contract

Prepare a review format that hides information that would bias the human toward
agreeing with the system where practical.

The human must be able to inspect the vacancy evidence and URL, but the initial
judgment surface should not foreground:

- system rank number;
- numeric score;
- system recommendation;
- preference effect;
- disagreement expectation.

After the human records the independent judgment, system evidence can be shown
for adjudication/explanation.

At minimum collect per opportunity:

```text
attention: YES | NO
application_intent: APPLY | DONT_APPLY | NEED_MORE_INFO
market_status_human: IN_SCOPE | UNCERTAIN | OUT_OF_SCOPE
preferred_variant_agreement: AGREE | DISAGREE | NOT_APPLICABLE
note: optional
```

If `NEED_MORE_INFO`, preserve what information is missing. Do not coerce it into
APPLY or DONT_APPLY.

## Predeclared primary metrics

### 1. Human APPLY attention recall

Among human `APPLY` opportunities in the 35 normal-attention + low-control
sample, proportion receiving system attention (`APPLY` or `REVIEW`, or the
repository's equivalent normal attention definition).

Target: **100%**.

### 2. Top-attention acceptance

Among the 15 Top-attention sampled clusters, proportion with human
`attention=YES`.

Target: **>= 60%**.

This is the direct prospective successor to the failed retrospective gate.

### 3. Ranking agreement

Use a predeclared opportunity-level agreement definition consistent with the
Phase 4 replay where possible.

Target: **>= 60%**.

### 4. Terminal APPLY acceptance

Among system terminal `APPLY` opportunities in the evaluated normal sample,
proportion with human `application_intent=APPLY`.

Directional target: **>= 60%**.

Do not substitute this for attention recall.

### 5. Market-status agreement

Among adjudicable sampled opportunities, exact agreement between deterministic
market status and human practical interpretation.

Target: **>= 90%**.

### 6. Preferred-variant agreement

Among sampled multi-member clusters where the human can adjudicate a preferred
variant, agreement with deterministic preferred member.

Target: **>= 80%**.

### 7. Cluster correctness

Human-reviewed multi-member sampled clusters with no false merge.

Required: **zero confirmed false merges** for promotion of the current
high-confidence clustering rule.

Report false splits diagnostically when observed; do not fail the rule solely
for conservative false splits in this experiment unless they materially distort
application intent.

## Secondary diagnostics

Report separately:

- recommendation distribution;
- market-status distribution;
- employer distribution;
- cache-hit/miss distribution;
- preference-effect distribution;
- seniority-guard activations;
- `NEED_MORE_INFO` rate;
- low-control human-attention positives;
- market-control false exclusions;
- multi-member cluster count;
- unassessable count.

Do not invent new success gates after seeing results.

## Stopping rule

The primary stopping rule is **40 completed cluster judgments** according to the
frozen sample manifest.

Exceptions:

- if a sampled vacancy becomes unavailable after batch creation, preserve it as
  post-batch availability evidence and do not reinterpret the original system
  ranking as wrong solely for that reason;
- replace an unavailable item only if the batch protocol predeclares a reserve
  item for that exact stratum;
- reserve ordering must be frozen at batch creation;
- do not stop early because metrics look good or bad.

If the human chooses to abandon the experiment, record it as incomplete rather
than computing a promoted verdict from a convenience subset.

## Batch immutability

The later prepared batch must freeze:

- opportunity cluster IDs and member identities;
- preferred variant at batch creation;
- job content fingerprints;
- semantic assessment identity or planned cache miss;
- all Phase 4 policy fingerprints;
- sample stratum and reserve order;
- protocol version;
- Git commit;
- creation timestamp.

Human judgments must be append-only/supersedable under the existing governance
model.

## Privacy/evidence boundary

Follow the evidence policy established during SPEC-006/007:

Repository-safe:

- protocol/configuration;
- code/tests;
- aggregate counts and sanitized metrics;
- fingerprints/hashes;
- experiment registry/status conclusions.

Private/local unless explicitly authorized:

- raw human notes;
- detailed candidate-derived per-opportunity evidence;
- detailed review artifacts;
- judgment log.

The implementation must not stage private evidence for Git.

## Implementation scope for SPEC-008

Implement only what is needed to **prepare and inspect** the prospective
experiment safely:

1. prospective protocol/config file;
2. deterministic cluster-level sampling logic;
3. historical-reviewed-opportunity exclusion logic;
4. employer concentration controls;
5. semantic cache/cost preflight;
6. dry-run/preparation manifest schema;
7. blind-review artifact/template generation;
8. reserve-item ordering;
9. tests for metric definitions and stopping rules;
10. experiment-registry and STATUS updates.

Do not:

- run live state refresh;
- call semantic models;
- record human judgments;
- compute a prospective verdict;
- tune Phase 4 policy.

If current local state is sufficient to create a **diagnostic preview** of the
sample, it may do so read-only, but the preview is not the prospective batch.
The actual batch must be created only after the protocol is committed and any
required fresh state/semantic execution is separately approved.

## Required tests

At minimum prove:

- sampling is deterministic;
- exactly one preferred variant represents a cluster;
- historical reviewed opportunities cannot enter primary prospective sample;
- employer cap works and relaxation is explicit;
- strata targets/fallbacks are deterministic;
- market controls are excluded from normal-attention metrics;
- reserve ordering is frozen;
- human labels cannot influence selection;
- cache preflight makes zero external calls;
- cost estimate is deterministic from known inputs;
- metric definitions have stable denominators/numerators;
- `NEED_MORE_INFO` is not coerced;
- unavailable-after-batch does not become automatic ranking disagreement;
- private detailed artifacts remain ignored/non-trackable;
- SQLite schema/lifecycle remain unchanged.

## Deliverable

Return:

A. files changed
B. prospective protocol version and frozen design
C. sampling algorithm and strata
D. employer concentration behavior
E. historical-overlap exclusion behavior
F. semantic cache/cost preflight result using current state if available
G. diagnostic sample preview, clearly labeled non-prospective, if generated
H. blind human-review format
I. metric definitions and gates
J. stopping/reserve rules
K. privacy/evidence guarantees
L. full offline validation result
M. unresolved issues requiring human approval before batch creation
N. recommended execution packet and exact approval boundary
O. recommended commit message

Do not commit or push until explicit approval.
