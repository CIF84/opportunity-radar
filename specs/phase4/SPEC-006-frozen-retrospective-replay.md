# SPEC-006 — Frozen Phase 4 Retrospective Replay

## Status

`APPROVED_FOR_IMPLEMENTATION`

## Purpose

Run a deterministic, zero-semantic-call retrospective replay of the immutable
30-case Live Decision Validation v1 batch through the now-implemented Phase 4
decision architecture.

This is an **experiment**, not a rewrite of historical validation.

The purpose is to answer:

> After correcting candidate-market routing, opportunity identity, decision
> preferences, and explicit junior-role handling while reusing the original
> semantic-v1 assessments, how much of the original `NO_GO` remains?

Before implementation, read the repository control plane and all Phase 4 work
packets, especially:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING_MODEL.md`
- `docs/decisions.yaml`
- `experiments/registry.yaml`
- Phase 4 in `SPEC.md`
- `SPEC-001` through `SPEC-005`
- immutable batch `output/live_validation/batch-20260826T210045Z-6492b09a/batch.json`
- canonical v1 report beside that batch

Do not alter the official v1 batch, judgments, assessments, or report.

## Frozen baseline

Baseline experiment:

```text
validation_batch_id = batch-20260826T210045Z-6492b09a
reviewed postings    = 30
original verdict     = NO_GO
strict APPLY recall  = 100%
shortlist APPLY recall = 100%
top attention acceptance = 35%
ranking agreement    = 40%
```

The replay must preserve the exact original human judgments as evaluation
evidence. It may reinterpret the system's decision unit from posting to
opportunity cluster only in separately labeled Phase 4 metrics.

## Frozen intervention

Freeze and record the exact identities/fingerprints for:

- Git commit used for replay;
- candidate profile version;
- semantic-profile fingerprint;
- Phase 3 scoring-preference fingerprint;
- market-access-policy fingerprint;
- market-status rules fingerprint;
- clustering contract/version and relevant fingerprints;
- decision-preference fingerprint;
- preference matching-rules fingerprint;
- preference-effect-policy fingerprint;
- effective decision-policy fingerprint;
- seniority-guard policy/rules fingerprint;
- semantic model;
- reasoning effort;
- semantic contract;
- relevant cached semantic assessment IDs/content fingerprints.

Do not change any frozen policy merely because replay metrics are disappointing.

## Hard zero-call requirement

The replay must make **zero external semantic calls** and **zero live-source
calls**.

It must reuse only existing persisted/cached `phase3-semantic-v1` assessments
that are compatible under the existing semantic cache contract.

If required semantic evidence for a replay member is missing or incompatible:

- do not call a model;
- do not synthesize semantic scores;
- classify the replay case as unassessable/pending with an explicit reason;
- preserve it in denominators only where the predeclared metric definition says
  it belongs.

Add a test/dry-run guard that fails if an external semantic transport would be
invoked.

## No historical mutation

The replay must not:

- append or supersede human judgments;
- rewrite `batch.json`;
- rewrite the official `validation_report.md`;
- overwrite semantic assessments;
- change `JobInstance` lifecycle/state;
- create Phase 2 events;
- migrate SQLite;
- modify candidate/taxonomy/policy configuration;
- tune thresholds/weights/effect mappings;
- broaden clustering rules.

The replay produces a **new immutable experiment artifact** under a new Phase 4
experiment/run identity.

## Replay unit model

Report two clearly separated views.

### 1. Posting-level diagnostic view

Preserve all 30 original review entries and report, for each:

- original review number;
- original JobInstance/observation/assessment identity;
- original human APPLY/DONT_APPLY judgment;
- original system recommendation/tier/rank evidence;
- current Phase 4 market status and reasons;
- cluster ID and all reviewed batch members in that cluster;
- whether this posting is the preferred variant;
- reused semantic assessment ID;
- base composite score;
- preference effect and matched evidence;
- decision-adjusted score;
- recommendation before market/preference/seniority caps where useful;
- final Phase 4 recommendation;
- seniority-guard result;
- whether it contributes an independent opportunity-level decision.

This view is diagnostic only. Do not treat duplicate posting variants as
multiple human application opportunities in the opportunity-level metrics.

### 2. Opportunity-level evaluation view

Collapse high-confidence clusters using the implemented clustering contract.

For each reviewed opportunity:

- cluster ID;
- reviewed member review numbers;
- preferred reviewed/current viable member;
- human opportunity-level application intent;
- Phase 4 final recommendation;
- market status;
- relevant preference effects;
- seniority guard;
- rank/order among reviewed opportunities;
- agreement classification.

## Human opportunity intent derivation

Use only the recorded human judgments/notes and previously accepted Phase 4
interpretation. Do not invent new human labels.

Known accepted duplicate interpretation:

- Kiwi reviews 3, 4, 5, and 9 represent one intended human application, with
  the Prague/Czech variant preferred.
- WPP reviews 11 and 12 represent one underlying Growth Consulting opportunity
  and one human non-application decision.

For other clusters discovered by the deterministic replay:

- if the 30-case human evidence does not establish one shared application
  intent unambiguously, do not silently collapse human labels for evaluation;
- mark the cluster as `HUMAN_CLUSTER_INTENT_UNRESOLVED` (or equivalent);
- report it diagnostically;
- exclude it only from metrics whose denominator explicitly requires resolved
  opportunity-level intent.

This prevents post-hoc clustering from fabricating benchmark truth.

## Recommendation semantics

Use the implemented Phase 4 decision architecture exactly as committed:

```text
market status
  -> hard eligibility
  -> cluster / preferred variant
  -> cached semantic-v1 assessment
  -> unchanged Phase 3 base composite
  -> frozen decision-preference effect
  -> deterministic recommendation thresholds
  -> market uncertainty cap
  -> seniority guard
```

Respect the actual code precedence if documentation and code differ; report any
such discrepancy as a blocker rather than silently choosing one.

`OUT_OF_SCOPE` opportunities are absent from the normal attention shortlist.
`UNCERTAIN` is capped at `REVIEW`.
Explicit governed junior/graduate roles are capped at `LOW_PRIORITY` when the
candidate guard applies.

## Predeclared metrics

Do not invent favorable metrics after seeing results.

### Required posting-level diagnostics

Report:

- 30 original reviews accounted for;
- posting-level final recommendation distribution;
- posting-level ranking agreement using the original v1 definition where still
  meaningful;
- count excluded by `OUT_OF_SCOPE`;
- count capped by `UNCERTAIN`;
- count affected by preferences;
- count activated by seniority guard;
- count of cached semantic assessments reused;
- unassessable count;
- external calls = 0.

Posting-level metrics are diagnostic because duplicates distort application
precision.

### Required opportunity-level metrics

For opportunities with resolved human intent, report:

1. **Human APPLY opportunity recall in the attention shortlist**
   - denominator: resolved human-APPLY opportunities;
   - numerator: those represented in the Phase 4 normal attention shortlist.

2. **Top-attention acceptance**
   - use the repository's existing TOP/HIGH or equivalent attention definition
     consistently;
   - numerator: human-APPLY opportunities among top-attention opportunities;
   - denominator: top-attention opportunities with resolved human intent.

3. **Opportunity-level ranking agreement**
   - preserve the accepted validation interpretation where possible;
   - define exact agreement logic in the artifact before reporting the value.

4. **Opportunity-level APPLY/recommendation acceptance**
   - human-APPLY opportunities among opportunities receiving terminal `APPLY`;
   - if market policy means fewer terminal APPLY recommendations because
     `UNCERTAIN` is capped at REVIEW, report this separately from attention
     recall.

5. **Preferred-variant agreement**
   - denominator: resolved multi-member opportunities where human evidence
     identifies a preferred variant;
   - numerator: deterministic preferred variant agrees.

6. **Cluster adjudication diagnostics**
   - reviewed multi-member clusters;
   - resolved human cluster intents;
   - unresolved human cluster intents;
   - known false merges = 0 requirement for promoted interpretation.

## Predeclared Phase 4 retrospective gates

Evaluate, but do not tune to satisfy:

- 100% human-APPLY opportunity recall in the attention shortlist;
- at least 60% opportunity-level top-attention acceptance;
- at least 60% opportunity-level ranking agreement;
- known explicit incompatible-market opportunities removed from normal
  shortlist;
- DBG Cork incomplete-location case remains uncertain and does not exceed its
  deterministic caps;
- Klaxoon unresolved remote-access case remains uncertain;
- known Kiwi variants form one opportunity and Prague is preferred;
- known WPP Growth Consulting variants form one opportunity;
- zero labeled/known false merges in the reviewed evidence;
- zero semantic calls;
- no mutation of official v1 evidence or Phase 2 state.

Report each gate independently as PASS/FAIL/UNRESOLVED.

Do not collapse these into a single `GO` unless the experiment registry/current
spec already defines such a composite verdict. Prefer a transparent gate table.

## Comparative decomposition

The replay should make it possible to understand **which architectural layer
changed which decisions**.

For each reviewed case and in aggregate, report the contribution of:

- market routing;
- clustering/application-unit correction;
- decision preferences;
- seniority guard.

Where practical, produce deterministic ablation diagnostics using the same
frozen evidence:

```text
baseline v1
+ market routing
+ clustering
+ preferences
+ seniority guard
```

Ablations must make zero model calls and must be clearly labeled post-hoc
explanatory diagnostics, not independent validation experiments.

Do not use ablations to retune policy.

## Residual disagreement analysis

After replay, identify cases where Phase 4 still disagrees with the recorded
human decision and classify them using existing disagreement categories where
supported.

Pay particular attention to the two previously identified semantic cases:

- GoodData senior BI Solution Architect;
- EY FP&A Assistant Director.

Do not change semantic-v1 in this packet.

The output should tell us whether these remain genuine residual semantic/rubric
failures after upstream corrections.

## Artifact

Create a new immutable artifact, suggested location:

```text
output/phase4_replay/<run_id>/replay.json
output/phase4_replay/<run_id>/report.md
```

Use repository conventions for run IDs.

The artifact should include:

- experiment/run identity;
- created timestamp;
- Git commit and dirty-state flag;
- all frozen fingerprints/versions;
- baseline references/hashes;
- posting-level replay rows;
- opportunity-level rows;
- metrics;
- gate table;
- ablation diagnostics;
- residual disagreements;
- limitations;
- zero-call evidence.

Do not overwrite a prior replay run.

## Experiment registry

Add/register this experiment in `experiments/registry.yaml` according to the
existing control-plane convention.

The registry entry must distinguish:

- retrospective/post-hoc replay;
- immutable baseline evidence;
- frozen intervention policy;
- result artifact;
- promotion decision pending human review.

Do not mark the experiment promoted merely because code executed successfully.

## Tests

Add tests proving at least:

- all 30 review entries are accounted for;
- official v1 files remain byte-identical after replay;
- external semantic transport cannot be invoked;
- cached semantic IDs are reused where compatible;
- known Kiwi/WPP human-intent derivation is correct;
- unresolved new clusters cannot fabricate human opportunity labels;
- metric denominators/numerators are deterministic;
- gate evaluation is deterministic;
- ablation order is deterministic;
- replay artifact is immutable/non-overwriting;
- SQLite schema remains v3;
- Phase 2 lifecycle/state is unchanged.

## Validation

Run the full offline suite and the retrospective replay itself.

Expected commands should be documented by the implementation. At minimum:

```bash
.venv/bin/pytest -q
git diff --check
```

The replay command must be offline with respect to source and semantic network
calls.

## Deliverable

Return:

A. files changed
B. replay command and run identity
C. frozen configuration/fingerprint summary
D. zero-call/cache-reuse evidence
E. posting-level diagnostic metrics
F. opportunity-level metrics
G. gate table
H. ablation/decomposition results
I. residual disagreement cases
J. clustering/preferred-variant diagnostics
K. limitations/unresolved human-intent cases
L. proof official v1 evidence and Phase 2 state were unchanged
M. full test result
N. interpretation: what fraction/type of the original NO_GO remains after Phase 4 deterministic corrections
O. recommended next decision/work packet
P. recommended commit boundary/message

Do not commit or push until explicit approval.
