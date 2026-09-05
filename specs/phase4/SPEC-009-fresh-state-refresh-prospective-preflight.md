# SPEC-009 — Fresh State Refresh and Prospective Preflight

## Status

`APPROVED_FOR_EXECUTION`

## Purpose

Perform the separately authorized operational transition required before the
prospective Phase 4 validation batch:

1. refresh the complete configured 18-employer market state using the current
   committed ingestion architecture and existing persisted-detail reuse policy;
2. run the already-frozen SPEC-008 prospective sampler/preflight against that
   refreshed state;
3. report the exact semantic cache misses, required external semantic-call count,
   estimated cost, source completeness, and selected/reserve composition;
4. stop before any prospective semantic assessment or batch creation.

This packet authorizes public employer listing/detail network acquisition needed
for the normal state refresh. It does **not** authorize semantic-model calls,
prospective batch creation, human judgments, or external actions.

Before execution read:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING_MODEL.md`
- `experiments/phase4_prospective_validation_v1.yaml`
- `SPEC-008`
- current state-runner/detail-reuse documentation

## Authority boundary

Authorized in this packet:

- synchronize the local repo with `origin/main` when safe;
- call the configured public employer sources through existing adapters;
- obtain complete inventories under existing completeness rules;
- apply existing retrieval-scope selection;
- perform detail requests only when the committed detail-reuse policy says they
  are due/required;
- update the normal operational SQLite state through the existing state runner;
- derive the prospective preflight from the refreshed state;
- write local operational reports/diagnostics under existing privacy rules.

Not authorized:

- any Luna/OpenAI/external semantic call;
- creating/finalizing the immutable prospective validation batch;
- recording human judgments;
- changing sampling protocol, strata, reserves, gates, seed, employer caps, or
  stopping rules;
- changing candidate policy, preferences, market rules, clustering, semantic
  contract, scoring, or seniority policy;
- changing adapter/source contracts merely to make a source pass;
- application submission, messaging, or any other external action beyond public
  job-source retrieval.

If execution discovers a source-contract failure or other correctness problem,
record/report it and preserve existing lifecycle safety. Do not improvise a fix
inside this operational packet.

## Step 1 — Pre-execution integrity check

Before network work:

- verify working tree is clean;
- synchronize with `origin/main` when safe;
- record Git commit;
- verify SQLite schema is expected version 3;
- record the current latest ingestion run/state counts;
- verify SPEC-008 frozen protocol parses and its fingerprint/identity is stable;
- verify semantic configuration remains Luna / low / `phase3-semantic-v1`;
- verify no semantic transport is configured to execute in this packet.

Stop if unexplained divergence, dirty state, schema mismatch, or frozen protocol
mismatch exists.

## Step 2 — Fresh 18-employer state refresh

Run the normal state refresh across all configured employers.

Use:

- complete inventory retrieval;
- current committed market retrieval scope;
- current persisted detail reuse;
- current configured detail refresh interval (168 hours unless committed config
  says otherwise);
- no artificial `--max-jobs` sampling cap unless the normal committed production
  command itself specifies one. The goal is a fresh operational state suitable
  for prospective sampling, not another bounded diagnostic sample.

The refresh must preserve the established lifecycle invariants:

- complete inventory controls presence/closure;
- incomplete source inventory cannot drive closure;
- intentional scope skips are not detail failures;
- reused details do not create false observations/content-change events;
- selected detail failures do not cause closure;
- JSON-feed/Phenom normalization-only operations remain distinct from network
  detail requests;
- no semantic calls occur.

## Refresh reporting

Report globally and per employer at minimum:

- inventory count;
- inventory completeness/status;
- selected for detail;
- intentionally skipped;
- reused details;
- details due/to fetch;
- details fetched;
- detail failures;
- network detail requests;
- elapsed time;
- source errors/warnings;
- resulting active/closed/detail-state counts.

Also identify:

- newly discovered active detailed jobs;
- newly closed jobs;
- materially changed detailed jobs;
- jobs whose existing semantic cache may now be stale because their material
  content fingerprint changed;

without assessing them semantically.

## Step 3 — Frozen prospective preflight

After the refresh completes, run SPEC-008's frozen prospective preparation in
preflight/preview mode only.

The sampler must use the committed protocol exactly:

- 40 OpportunityClusters;
- strata `15 / 10 / 10 / 5`;
- five frozen reserves per stratum;
- maximum four normal items per employer;
- maximum one market control per employer;
- deterministic seed/fallback/blind order;
- historical reviewed-member overlap exclusion;
- no human-label influence;
- no early stopping.

Do not create the actual prospective batch.

## Required preflight evidence

Report:

### Population

- active jobs;
- active jobs with usable detail;
- active opportunity clusters;
- normal candidate clusters;
- historical-overlap exclusions;
- market-status distribution;
- recommendation/attention distribution where relevant.

### Sample and reserves

For selected 40 and reserves 20:

- count by stratum;
- count by employer (sanitized aggregate only in repository-safe output);
- employer-cap relaxations, if any;
- market-status distribution;
- preferred-variant availability;
- unassessable/pending clusters;
- cache hits;
- cache misses.

### Semantic budget

For the selected sample, and separately for reserves:

- compatible semantic cache hits;
- semantic cache misses;
- exact number of external semantic calls that would be required to make the
  selected batch assessable;
- reserve calls that might be required later if replacements are activated;
- estimated cost using the committed live-validation estimator;
- model/reasoning/contract identity used for the estimate.

No semantic calls may be made to obtain these numbers.

## Step 4 — Stop at paid-execution boundary

After reporting preflight, stop.

Do not:

- assess cache misses;
- create/finalize the prospective batch;
- expose the blind review to the human as a frozen validation batch;
- spend semantic budget.

The next transition requires explicit human approval of the reported call count
and estimated cost.

## Privacy and evidence

Operational SQLite, detailed preflight items, vacancy identities, titles,
locations, URLs, descriptions, candidate-specific evidence, and blind-review
content remain local/private under `OPERATING_MODEL.md`.

Repository-safe evidence may include only sanitized aggregate counts,
configuration fingerprints, run IDs, source completeness summaries, call/cost
budgets, hashes/provenance, limitations, and conclusions.

Do not commit operational SQLite or detailed preflight artifacts.

This packet is primarily an operational execution packet. Do not create a code
commit merely because the refresh/preflight ran. If no code/docs changes are
needed, report that explicitly.

## Failure behavior

If one or more employer sources fail:

- preserve their incomplete status;
- do not let absence close jobs for incomplete inventories;
- complete other employers when safe;
- still run prospective preflight only if the resulting state is valid under
  the frozen protocol;
- clearly state whether source incompleteness compromises prospective sampling.

If it compromises the sample, stop before semantic authorization and recommend a
separate bounded source-repair packet.

## Validation

Before/after execution, run the minimum relevant offline integrity checks if
needed, but do not modify frozen behavior.

At minimum report:

- Git commit and clean/dirty state;
- SQLite schema;
- state refresh run ID/status;
- source completeness;
- prospective preflight/preview run ID;
- zero semantic calls proof;
- zero prospective judgments/batch creation proof.

## Deliverable

Return:

A. pre-execution integrity result
B. exact state-refresh command
C. refresh run ID/status and elapsed time
D. per-employer refresh summary
E. resulting operational-state counts and meaningful deltas
F. source failures/incompleteness and lifecycle implications
G. prospective preflight run ID
H. fresh population and sample/reserve aggregate composition
I. selected semantic cache hits/misses
J. selected required semantic-call count and estimated cost
K. reserve cache hits/misses and contingent cost
L. whether the fresh state is valid for prospective execution
M. explicit confirmation that zero semantic calls, zero prospective judgments,
   and zero prospective batch creation occurred
N. exact next approval decision required from the human

Do not commit or push operational evidence unless a repository-safe aggregate
artifact was already part of the committed SPEC-008 convention and contains no
private evidence. Do not alter code to complete this packet unless a correctness
blocker is first reported and separately approved.
