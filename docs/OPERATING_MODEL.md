# Opportunity Radar — Operating Model

This document defines the lightweight rules by which a solo builder or coding
agent may preserve evidence, learn from use, run experiments, promote changes,
and take action. It does not add product behavior.

## Evidence classes

- **FACT** — an assertion from an identified source, such as a candidate fact
  or a field stated by an employer. A fact retains source and version; it is not
  assumed timeless or universally true.
- **OBSERVATION** — time-bound captured evidence, such as a source inventory,
  normalized job snapshot, source outcome, or model-call usage record.
- **INFERENCE** — a rule/model interpretation derived from identified inputs,
  such as lifecycle state, eligibility, semantic dimensions, or clustering.
- **PREFERENCE** — a candidate's subjective policy input. It is versioned and
  must not be disguised as a market fact.
- **DECISION** — a deterministic system conclusion or explicit human choice,
  such as recommendation, promotion, rejection, or judgment.
- **EXPERIMENT RESULT** — measured evidence under frozen inputs and a declared
  intervention. It is not production policy until explicitly promoted.
- **ACTION** — an internal or external state-changing operation.

These classes must not silently overwrite one another. A new observation may
change current state without deleting the old observation. A human judgment may
challenge an inference without rewriting it. An experiment may motivate a new
policy version but may not mutate policy by itself.

## Learning loop

```text
observation
  -> recommendation
  -> human judgment
  -> disagreement pattern
  -> hypothesis
  -> bounded experiment
  -> evaluation
  -> explicit decision
  -> promotion / rejection
```

One judgment is evidence, not an automatic policy change. Feedback must never
silently mutate candidate configuration, taxonomy, deterministic rules,
semantic prompts, weights, or production behavior.

An explicit candidate confirmation may promote a fact or preference into an
accepted decision record. That promotion preserves the human policy, but does
not claim runtime implementation. Code/configuration adoption is a separate,
reviewable change with its own version, tests, and experiment gate. Personal
rationale may remain in the decision record while runtime configuration keeps
only the minimum operational policy.

Promotion guidance:

- Candidate fact corrections require candidate confirmation and a new profile
  version.
- Preferences require explicit declaration or a repeated, reusable pattern;
  one-off dislikes remain judgment evidence.
- Deterministic-policy changes require reproducible fixtures, conservative
  UNKNOWN behavior, regression tests, frozen-batch replay, and an accepted
  decision.
- Taxonomy concepts require a reusable distinction and more than one plausible
  consumer/case.
- Semantic-contract changes require residual semantic failures after upstream
  routing/preferences are addressed, a new contract identity, and comparative
  evaluation.
- Retrospective replay is diagnostic. A prospective batch is required for a
  new directional validation claim.

## Experiment lifecycle

```text
HYPOTHESIS
  -> BASELINE
  -> FROZEN INPUTS
  -> INTERVENTION
  -> MEASUREMENT
  -> RESULT
  -> DECISION
  -> PROMOTION / REJECTION / FOLLOW-UP
```

Every major experiment is indexed in `experiments/registry.yaml`. Its packet
should preserve, directly or by referenced immutable artifacts:

- experiment ID, type, owner, status, and dates;
- hypothesis, baseline, intervention, and predeclared metrics;
- paths and fingerprints for frozen inputs;
- Git commit and dirty-worktree state;
- database/run identity where applicable;
- candidate, taxonomy, policy, prompt/contract, model, reasoning, and scoring
  identities where applicable;
- time/call/cost budget;
- result, limitations, and decision;
- artifact paths and integrity hashes when practical;
- related decision IDs.

Secrets must never enter an experiment packet. Large artifacts stay at their
existing paths; the registry links rather than duplicates them.

## Authority model

- **INSPECT** — read repository, local state, and permitted public evidence.
  No per-action approval is needed.
- **ANALYZE** — derive diagnoses or recommendations without authoritative
  writes. No approval is needed.
- **DERIVE** — regenerate replaceable reports/status from existing evidence.
  Allowed under standing project policy when provenance is retained.
- **OPERATE_INTERNAL** — append operational observations, refresh state, or run
  a bounded approved experiment. Requires an explicit operating policy and
  declared limits; external paid calls require budget/provider authorization.
- **PROPOSE_CHANGE** — draft code, configuration, profile, taxonomy, or policy
  changes without promoting them. Allowed when requested.
- **PROMOTE** — make a proposed change authoritative, change a frozen contract,
  or accept/reject a material decision. Requires explicit human approval.
- **EXTERNAL_ACTION** — submit an application, send a message, publish,
  purchase, or disclose data. Requires explicit per-action authorization.

Credential availability does not grant authority. A recommendation of `APPLY`
does not grant authority to submit an application.

Future agent action evidence should record actor/agent/model identity,
authority basis, input hashes, operation, affected records, timestamps,
external IDs, status, and error. External actions must be idempotent where the
target permits it.

## AI governance

Semantic models are governed dependencies behind a provider-independent
assessor contract.

Controls:

- structured input/output contracts;
- explicit provider, model, reasoning, prompt, schema, taxonomy, and assessor
  identities;
- semantic cache keys based on semantic inputs, not scoring weights;
- deterministic lifecycle, identity, eligibility, arithmetic, recommendation,
  and authority outside the model;
- frozen benchmarks and prospective human validation;
- token/cost/latency/failure records;
- explicit promotion of a new model or semantic contract;
- visible failure with no invented assessment.

Current known gap: persisted semantic identity does not yet include every
provider/reasoning/prompt/taxonomy field in this policy. Existing cache records
must be preserved. Closing that gap requires a versioned decision, not silent
reinterpretation.

## Data governance for the personal local MVP

- API credentials remain in environment variables and must never be committed,
  printed, or persisted in diagnostics.
- Public job listings retain source URL, observation time, and normalized
  evidence. Avoid retaining full raw pages unless a bounded fixture or
  diagnostic is needed.
- `config/candidate.yaml` and candidate profiles contain personal information.
- Semantic assessments and human judgments are derived profiling data even
  when job listings are public.
- Repository public/private status is not currently established as a durable
  policy. Until it is, raw judgment notes remain local and excluded from Git.
- `data/live_validation/judgments.jsonl` is the local append-only judgment
  authority. It requires a separately chosen durable private backup before the
  local workspace can be treated as replaceable.
- Aggregate validation metrics and redacted reports may be repository evidence
  when they do not disclose raw personal notes.
- SQLite databases may contain public job content, candidate snapshots, and
  inferred assessments. Treat them as personal local state, not public build
  artifacts.
- Retention, export, backup, and deletion rules remain open decisions before
  multi-user or hosted operation.

## Output and evidence ownership

Every output belongs to one class:

- **CANONICAL_EVIDENCE** — frozen input/result required to support an accepted
  or directional conclusion. Track when safe and reasonably sized, or keep in
  documented durable private storage.
- **DERIVED_REPORT** — reproducible human-readable rendering of canonical
  evidence. Replaceable; may be tracked as a gate summary.
- **LOCAL_STATE** — mutable operational database or sensitive local evidence.
  Back up privately; do not treat as a portable repository contract.
- **DIAGNOSTIC** — bounded investigation artifact useful for a specific issue.
  Retain only while referenced by an experiment/decision.
- **SUPERSEDED** — immutable historical evidence replaced as current guidance.
  Keep only when it explains a decision or regression baseline.

Current classification:

| Path/pattern | Class | Policy |
|---|---|---|
| `benchmarks/**` | CANONICAL_EVIDENCE | Track and version; never rewrite to improve results |
| `research/target_companies.csv` | CANONICAL_EVIDENCE | Track research corrections with provenance |
| `output/live_validation/*/batch.json` | CANONICAL_EVIDENCE | Track frozen reviewed batch when privacy-safe |
| final aggregate `validation_report.md` | DERIVED_REPORT | Track as gate evidence |
| `data/live_validation/judgments.jsonl` | CANONICAL_EVIDENCE, private | Exclude from Git pending explicit privacy/backup decision |
| `output/opportunity_radar.sqlite3` | LOCAL_STATE | Private backup; do not publish by default |
| `output/*sample*.sqlite3`, `*diagnostic*.sqlite3` | DIAGNOSTIC | Historical currently; future generated copies should be ignored |
| `output/scope_measurement/*.json` | CANONICAL_EVIDENCE or SUPERSEDED | Registry identifies the final evidence and historical predecessors |
| phase reports in `docs/` | DERIVED_REPORT / historical | Keep immutable; STATUS supplies current guidance |
| `output/jobs.json`, `run_results.json`, `summary.json` | DERIVED_REPORT / historical | Retained for Phase 1 evidence, not current market state |
| `output/test_receipt.json` | DERIVED_REPORT | Optional latest local receipt; never authoritative |

No existing large artifact is deleted or migrated by this control-plane change.
Future default-generated local state and diagnostics should be ignored unless
an experiment registry entry explicitly promotes them as evidence.
