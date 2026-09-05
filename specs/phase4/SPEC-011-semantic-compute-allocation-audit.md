# SPEC-011 — Semantic Compute Allocation Audit

## Status

`APPROVED_FOR_IMPLEMENTATION`

## Purpose

Do not spend approximately $8 to semantically assess the full routed market yet.
Instead, determine whether Opportunity Radar can allocate expensive semantic
reasoning only where it creates decision value while preserving essentially all
opportunities the human would want to see.

The fresh SPEC-009 state exposed the current scale:

```text
16,490 observed postings
  -> 3,949 selected for detail
  -> 3,935 usable active detailed jobs
  -> 3,870 opportunity clusters
  -> 3,326 normal candidate clusters before historical exclusion
  -> ~3,109 routed semantic cache misses after historical exclusion
```

Full semantic completion is estimated at roughly $8.24. The cost itself is not
prohibitive, but assessing thousands of opportunities merely to identify a small
attention set is not yet an acceptable product architecture assumption.

This packet is an **audit and experiment-design slice**, not authorization to
call Luna or change the frozen prospective validation protocol.

Primary question:

> Using evidence available before expensive semantic assessment, how much can
> the current routed population be reduced while preserving known human-APPLY
> recall and avoiding cache-status selection bias?

Secondary question:

> What is the smallest safe next experiment that can test a compute-allocation
> funnel without prematurely building a second semantic model?

## Context and invariants

Read before implementation:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING_MODEL.md`
- `experiments/phase4_prospective_validation_v1.yaml`
- SPEC-008 through SPEC-010
- frozen historical validation evidence and sanitized Phase 4 replay receipts

Preserve:

- Luna / low / `phase3-semantic-v1`;
- Phase 3 scoring weights;
- market routing;
- clustering;
- preferences/effect mapping;
- seniority guard;
- SPEC-008 prospective protocol as historical/frozen v1;
- Phase 1/2 lifecycle semantics;
- semantic cache identity;
- human judgments.

Do not reinterpret cache availability as relevance.

## Non-goals

Do NOT:

- make any external semantic/model calls;
- refresh live sources again;
- create the prospective validation batch;
- change human judgments;
- tune Luna or semantic-v1;
- change scoring weights or preference effects;
- build embeddings/vector search;
- introduce a cheap LLM/model router yet;
- build ML training infrastructure;
- create a generalized learned ranker;
- use cache hit/miss as an input feature to relevance selection;
- mutate Phase 2 lifecycle/state;
- add UI/feed/control panel;
- optimize against prospective human outcomes that do not yet exist.

## Product principle

Semantic compute is a scarce resource even when its unit price is low.
Opportunity Radar should aim to spend deeper reasoning where:

```text
expected decision value × uncertainty
```

is high.

Obvious nonmatches should not receive the same compute as ambiguous,
high-potential opportunities.

This packet must not pretend that this conceptual objective is already a proven
formula. It should identify what pre-semantic evidence can safely approximate a
compute-allocation decision.

## Evidence inventory

Audit exactly what information is available before a new semantic-v1 assessment.
Classify each field as:

- LISTING_LEVEL
- DETAIL_NORMALIZED
- DETERMINISTIC_DERIVED
- CANDIDATE_CONFIGURATION
- HISTORICAL_CACHE_ONLY
- SEMANTIC_ONLY

At minimum inspect availability/quality for:

- title;
- employer;
- location/work mode;
- employment type;
- department/category where available;
- normalized description text;
- source update/posting age evidence;
- deterministic market status;
- hard eligibility evidence available without semantic output;
- explicit junior/graduate guard evidence;
- taxonomy-backed lexical concepts derivable without semantic assessment;
- candidate functional/domain preferences that can match deterministic evidence;
- opportunity-cluster membership/variant evidence;
- existing semantic cache state (audit only, never relevance feature).

Produce aggregate coverage/missingness statistics across the fresh routed
population.

## Historical recall corpus

Use existing frozen human judgments only as retrospective safety evidence.

The audit must identify all historically reviewed opportunities with human
`APPLY` intent and determine whether each proposed cheap pre-semantic filter
would retain them.

Known historical opportunity clustering must be respected, including the Kiwi
multi-posting group.

Do not use the historical 30-case evidence to tune dozens of thresholds until
100% recall is achieved. Candidate policies/rules evaluated here must be simple,
predeclared, interpretable, and few in number.

The historical corpus is small and biased. Treat 100% historical APPLY recall as
a **necessary but insufficient** safety condition.

## Candidate cheap-filter families to audit

Evaluate independently and in conservative combinations.

### 1. Explicit deterministic incompatibility

Examples:

- `OUT_OF_SCOPE` market status;
- hard `INELIGIBLE` evidence available without semantic reasoning;
- explicit language/authorization incompatibility;
- explicit junior/graduate guard as prioritization evidence, not necessarily
  exclusion.

Do not weaken current UNKNOWN semantics.

### 2. Title/role-family evidence

Test whether bounded lexical/taxonomy evidence from titles can identify obvious
role-family nonmatches.

Examples may include clearly engineering-only, warehouse/material handling,
clinical/medical-specialist, legal, accounting/controller, or other role
families where the candidate lacks plausible target alignment.

Rules must be generic/taxonomy-backed where possible, not employer-specific and
not one-off exclusions copied from historical judgments.

Prefer `DEPRIORITIZE_FOR_SEMANTIC` over permanent exclusion when uncertainty
remains.

### 3. Positive target-role evidence

Identify cheap positive evidence that should protect a role from pruning, such
as bounded matches to:

- business/commercial operations;
- transformation;
- AI/automation;
- product strategy/development;
- analytics/decision intelligence;
- pricing/revenue/retention;
- implementation ownership;
- other already-approved candidate preference/taxonomy concepts.

A strong positive signal should normally override a weak negative cheap signal
for compute allocation.

### 4. Description lexical/taxonomy evidence

Audit whether deterministic concept matching against normalized descriptions can
add meaningful recall-safe discrimination beyond titles.

Do not recreate the semantic model with a giant keyword engine.

### 5. Information uncertainty

Identify cases where pre-semantic evidence is insufficient or conflicting.
These should preferentially flow **toward** semantic assessment rather than be
filtered out.

The allocation policy should be conservative around uncertainty.

## Required experimental outputs

For each candidate filter/funnel stage report:

- starting routed population;
- retained count;
- deferred/deprioritized count;
- reduction percentage;
- historical human-APPLY opportunities retained / total;
- historical human-DONT_APPLY opportunities retained / total where useful;
- false-negative historical APPLY identities privately for audit;
- coverage/missingness limitations;
- employer concentration effects;
- market-status distribution before/after;
- semantic cache hit/miss distribution **for diagnostics only**;
- projected Luna calls if the retained cache-miss population were fully
  assessed;
- projected cost using the existing estimator.

Do not call Luna to obtain these outputs.

## Funnel candidates

Evaluate a small number of explicit candidate funnels, for example:

```text
F0 = current routed population
F1 = remove deterministic incompatibility only
F2 = F1 + conservative obvious role-family deprioritization
F3 = F2 + positive-protection / uncertainty escalation
F4 = F3 + bounded description concept evidence (only if it adds measurable value)
```

These labels are illustrative. Use clearer names if appropriate.

Do not produce a combinatorial threshold search.

## Target economics

Report scenarios, not requirements, for reducing current ~3,109 routed cache
misses toward:

- <= 1,000 Luna calls;
- <= 500 Luna calls;
- <= 250 Luna calls;
- <= 100 Luna calls.

For each threshold state whether the audit found an interpretable historical-
recall-safe policy capable of reaching it.

Use the current approximate per-assessment cost only as a projection. Report
both calls and dollars; do not optimize only for dollars.

## Decision-value/uncertainty triage model

Propose a minimal deterministic triage contract with three outputs, unless the
evidence supports a simpler/better representation:

```text
SEMANTIC_PRIORITY
SEMANTIC_OPTIONAL
SEMANTIC_DEFER
```

Possible semantics:

- `SEMANTIC_PRIORITY`: plausible/high-value or uncertain opportunity deserving
  deep assessment;
- `SEMANTIC_OPTIONAL`: some plausible evidence but lower expected attention
  value; assess when budget allows or for exploration/control sampling;
- `SEMANTIC_DEFER`: strong cheap evidence of low candidate relevance; retain in
  lifecycle/state but do not spend semantic compute by default.

This triage must not change JobInstance lifecycle, market status, hard
eligibility, or human-visible final recommendation by itself. It controls
**compute allocation only**.

Do not implement this triage into production runtime unless the packet's audit
results justify a bounded follow-up experiment.

## Exploration requirement

A future compute-allocation policy must preserve exploration so that the system
can discover surprising opportunities and detect bad cheap filters.

Design, but do not necessarily implement, an exploration mechanism such as:

- random/control sample from `SEMANTIC_DEFER`;
- employer-balanced exploration;
- periodic audit sample;
- uncertainty-triggered promotion.

The mechanism must not depend on historical cache availability.

Explain how future human feedback could test false negatives.

## Prospective validation implications

Do not modify SPEC-008 v1 in this packet.

Instead report whether the compute-allocation findings imply that prospective
validation should proceed as:

A. full semantic population completion under v1;
B. a separately versioned v2 protocol that freezes a compute-allocation frame
   before semantic assessment;
C. another bounded experiment first because current evidence is insufficient.

Explain exactly what scientific question changes under option B.

## Mutable-test correction

The SPEC-009 refresh exposed a test coupled to the mutable operational database:
`test_corrected_replay_is_zero_call_read_only_and_bounded` expected the old 406
assessable ACTIVE population.

Fix this test architecture in this packet:

- move the assertion to frozen fixture/snapshot evidence appropriate to the
  retrospective experiment;
- do not weaken the invariant being tested;
- do not mutate current operational SQLite to make the test pass.

Run the full offline suite afterward.

## Current-decision recomposition audit

Separately verify the SPEC-010 observation that compatible cached semantic
payloads can be deterministically recomposed against current:

- job observation;
- market status;
- hard eligibility;
- preference policy;
- seniority guard;
- scoring/recommendation rules;

without an external call and without rewriting the cached semantic payload.

Implement a reusable pure recomposition helper only if it is clearly needed to
perform the audit and does not silently change runtime behavior. Otherwise
report the required design for the next packet.

## Privacy

Detailed job identities, descriptions, candidate evidence, human judgment rows,
false-negative cases, and operational database remain private/local.

A repository-safe aggregate audit receipt may contain:

- run/experiment identity;
- Git/config fingerprints;
- aggregate counts;
- funnel reduction metrics;
- historical APPLY recall counts;
- projected calls/costs;
- limitations;
- conclusions;
- artifact hashes.

No candidate name, job title, URL, description, or judgment note in tracked
aggregate output.

## Experiment registry and status

Register the audit as a new experiment/gate in `experiments/registry.yaml` and
update `docs/STATUS.md` after implementation with:

- why the $8 full-population semantic spend was deferred;
- audit findings;
- whether a bounded compute-allocation experiment is justified;
- exact next human decision.

Do not mark a compute-allocation policy promoted merely because it reduces calls.

## Validation

Required:

```bash
.venv/bin/pytest -q
git diff --check
```

Also prove:

- zero semantic calls;
- zero live-source calls;
- zero prospective batch/judgment creation;
- operational SQLite not mutated by the audit;
- frozen prospective protocol unchanged;
- cache hit/miss status not used as a relevance feature;
- historical official evidence unchanged.

## Deliverable

Return:

A. files changed
B. audit/run identity and commands
C. pre-semantic evidence inventory and coverage
D. current routed population baseline
E. candidate funnel definitions
F. funnel-by-funnel population reduction
G. historical human-APPLY recall for each funnel
H. projected Luna calls and cost for each funnel
I. whether <=1000 / <=500 / <=250 / <=100 calls are defensibly reachable
J. proposed compute-allocation triage contract
K. exploration/control mechanism recommendation
L. current-decision recomposition finding
M. mutable-test correction
N. privacy/evidence handling
O. full validation result
P. recommendation: protocol v1 full completion vs prospective protocol v2 vs
   further experiment
Q. smallest next work packet
R. recommended commit message

Do not commit or push until explicit approval.
