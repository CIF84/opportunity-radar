# Opportunity Radar — Current Architecture

Status: authoritative description of the architecture currently implemented in
this repository. Historical phase reports describe earlier validation gates;
`SPEC.md` remains the normative phase specification.

## Layer map

```text
OBSERVE
  -> RETRIEVAL SCOPE
  -> STORE STATE
  -> INTERPRET
  -> DECIDE
  -> HUMAN VALIDATE
  -> ACT (not implemented)
```

## OBSERVE

Responsibility: discover the complete current vacancy identity inventory for a
configured employer and normalize selected public vacancy details.

- Main modules: `config.py`, `registry.py`, `models.py`, `adapters/*`,
  `runner.py`.
- Inputs: declarative `config/companies.yaml` and public source responses.
- Outputs: `JobReference` inventory and `NormalizedJob` details.
- Nature: deterministic source parsing and normalization.
- Persistence: none inside adapters.

Invariants:

- `list_jobs(company_config) -> list[JobReference]` and
  `fetch_job(job_reference) -> NormalizedJob` remain separate.
- One vacancy remains one job even when it has multiple locations.
- Raw location strings are preserved and work mode is separate from location.
- The adapter registry selects source families only; employer-specific values
  belong in configuration.
- Adapters normalize source facts. They do not own candidate relevance,
  lifecycle, persistence, scoring, or action.

## RETRIEVAL SCOPE

Responsibility: use listing-level geography evidence to avoid unnecessary
detail retrieval while conservatively retaining unknown and potentially
compatible vacancies.

- Main modules: `scope_selection.py`, `state_runner.py`,
  `scope_measurement.py`; policy: `config/market_scope.yaml`.
- Input: complete `JobReference` inventory and normalized `ListingFacts`.
- Output: detail-selection decision and evidence.
- Nature: deterministic, candidate-independent retrieval policy.
- Persistence: selection aggregates are stored with source outcomes; complete
  listing evidence is retained in dedicated measurement artifacts.

Invariants:

- Complete unfiltered inventory—not selected details—controls presence and
  closure.
- Retrieval scope does not imply candidate eligibility or desirability.
- Unknown geography is retained, not converted into incompatibility.
- An intentional detail skip is not a detail failure and cannot cause a false
  closure.

## STORE STATE

Responsibility: preserve observations, infer current lifecycle state, record
material changes, and reuse successful details conservatively.

- Main modules: `state_models.py`, `change_detection.py`,
  `state_repository.py`, `state_runner.py`.
- Inputs: complete identity inventory, successful details, source outcome, and
  previous persisted state.
- Outputs: ingestion/source observations, job observations, `JobInstance`
  state, events, and detail-reuse evidence.
- Nature: deterministic state inference.
- Persistence: SQLite schema version 3 in the current implementation.

Invariants:

- Observation, state, and event are distinct concepts.
- Absence implies closure only after a successful complete identity inventory.
- Detail failure never implies absence and never overwrites prior content.
- Inventory completeness and selected-detail completeness are separate.
- Exact identity is company plus external job ID, with company-scoped canonical
  URL fallback when no external ID exists.
- URL-only identity is not automatically migrated when an external ID later
  appears.
- Adapters remain unaware of persistence.
- A `JobInstance` lifecycle is independent of suitability for any candidate.

## INTERPRET

Responsibility: interpret a current job for a versioned candidate using
conservative eligibility, neutral features, and a provider-independent semantic
assessment contract.

- Main modules: `phase3_config.py`, `phase3_models.py`, `market_status.py`,
  `eligibility.py`, `features.py`, `semantic.py`, `experimental_semantic.py`.
- Inputs: `SemanticJobInput`, candidate profile, market-normalization rules,
  taxonomy, deterministic features, and semantic assessor.
- Outputs: structured candidate-market assessment, eligibility evidence, and
  six dimension scores with structured strengths, gaps, and risks.
- Nature: market status, eligibility, and features are deterministic;
  dimension interpretation may be semantic.
- Persistence: candidate profiles and semantic assessments are versioned in
  SQLite outside the assessor.

Invariants:

- Candidate facts, capabilities, preferences, constraints, goals, and weights
  are data/configuration, never candidate-specific Python branches.
- Omitted capability means `UNKNOWN`; it is not explicit `NONE`.
- `UNKNOWN != INELIGIBLE`.
- Semantic models do not own identity, lifecycle, persistence, hard
  eligibility, composite arithmetic, recommendation, or action authority.
- Job descriptions are evidence and untrusted input, never model instructions.
- `CandidateProfile` version 2 validates a separately fingerprinted
  `market_access_policy`; that policy is excluded from semantic-v1 inputs.
- `market_status.py` provides a pure post-detail candidate-market evaluator
  using declarative bounded normalization. Its structured assessment is not
  yet consumed by routing, ranking, or persistence.

## DECIDE

Responsibility: deterministically combine eligible semantic dimensions into a
reproducible composite, recommendation, and ranking.

- Main modules: `phase3_pipeline.py`, `scoring.py`; operational ranking in
  `live_validation.py`.
- Inputs: eligibility, dimension scores, candidate scoring weights, and
  recommendation configuration.
- Outputs: `OpportunityAssessment`, composite score, recommendation, rank/tier.
- Nature: deterministic.
- Persistence: opportunity assessments are separate from `JobInstance` and
  semantic assessments.

Invariants:

- All six core dimensions are required for a normal composite.
- Confidence is preserved but does not multiply scores.
- Missing dimensions produce `REVIEW`, not an invented score.
- Composite weights and recommendation thresholds do not define semantic cache
  identity.
- A recommendation is a decision-support output, not authorization to act.

## HUMAN VALIDATE

Responsibility: freeze a reviewed sample, capture append-only human judgments,
classify disagreements, and calculate directional validation metrics.

- Main module: `live_validation.py`.
- Inputs: active assessed jobs, immutable batch manifest, human decisions.
- Outputs: batch/review artifacts, append-only judgments, derived report.
- Nature: deterministic sampling/reporting plus human judgment.
- Persistence: immutable JSON batch/run packets and local append-only JSONL.

Invariants:

- Batch membership and underlying job records are not rewritten by judgments.
- Supersession appends a replacement judgment; it does not edit history.
- Explicit review/job identities are preferred; ambiguous legacy identifiers
  fail.
- A stratified batch is directional evidence, not an unbiased market estimate.

## ACT

No application submission, messaging, scheduling, or other external action is
implemented.

Future action logic must be downstream of recommendation and require its own
explicit authority. A recommendation of `APPLY` never grants application
authority.

## Cross-layer identities

- `JobReference`: one identity observed at a source.
- `NormalizedJob`: normalized content for one source vacancy.
- `JobInstance`: persistent lifecycle identity for that vacancy.
- `JobObservation`: immutable observed content at a time/run.
- `SemanticAssessment`: candidate interpretation of material job content.
- `OpportunityAssessment`: deterministic decision derived from semantic output
  and scoring configuration.
- Human judgment: validation evidence about a frozen assessment.

The first live validation demonstrated that posting identity, human opportunity
identity, and application intent are not equivalent:

```text
JobInstance != Opportunity != Application intent
```

## Partially implemented Phase 4 direction

The post-validation architecture audit identified four Phase 4 concepts:

1. `CurrentCandidateMarketStatus`: the pure evaluator for `IN_SCOPE`,
   `UNCERTAIN`, or `OUT_OF_SCOPE` after detailed active state is implemented.
   Its routing and recommendation-policy integration are not implemented. It
   does not change lifecycle state.
2. `OpportunityCluster`: a high-confidence employer-scoped grouping above
   independent `JobInstance` records.
3. Preferred variant: candidate-dependent choice of one cluster member for
   attention/application while variant lifecycles remain independent.
4. Preference-aware decision layer: versioned candidate decision preferences
   applied without silently changing cached semantic interpretation.

Items 2–4 remain planned and are not implemented. The candidate's Prague
onsite/hybrid boundary, Czech-compatible remote policy,
exceptional-relocation posture, language/work-access facts, `UNCERTAIN` cap,
and junior-role guard are now represented in the generic CandidateProfile
schema and configuration. Their pure behavioral evaluation is implemented;
downstream routing and recommendation composition remain unimplemented.
Soft preference trade-offs remain accepted policy but are deferred to the
decision-preference slice. Phase 4 of `SPEC.md` defines the boundaries.

The planned responsibility split is:

- candidate-market status owns geographic, remote-employment,
  work-authorization/residency, and required-language practicality;
- hard eligibility owns only explicit non-market hard constraints;
- opportunity clusters group postings without changing member identity or
  lifecycle;
- preferred-variant and decision-preference policy are candidate-dependent;
- terminal policy composition stays deterministic and downstream of semantic
  interpretation.

The gate and implementation order for these experiments are in `STATUS.md`.

## Known architecture debt

- Complete identity inventories drive lifecycle but are not normally retained
  as per-reference run manifests outside scope-measurement artifacts.
- The persisted `details_complete` column now represents selected-detail
  completeness after retrieval scope; the historical name is broader than its
  current meaning.
- Semantic cache identity currently records model through assessor version but
  not every governed model/prompt/provider/taxonomy setting described in the
  operating model.
- `live_validation.py` and `state_runner.py` each concentrate several
  orchestration responsibilities. Preserve behavior and extract only when a
  validated change requires it.
