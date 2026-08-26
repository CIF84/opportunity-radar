# Opportunity Radar

## Mission

Build an automated opportunity-detection system that continuously monitors
the relevant employment market and identifies high-value career opportunities
that would be impractical to discover manually.

The initial focus is Prague, Czechia, and remote roles accessible from Czechia.

## Problem

Relevant opportunities are fragmented across:

- company career sites
- applicant tracking systems (ATS)
- job boards
- search engines
- professional networks

Manual monitoring does not scale, while relying on individual job boards
creates incomplete coverage, stale listings, and platform dependency.

The system should discover opportunities from first-party sources where
possible, verify that vacancies remain active, eliminate duplicates, and
eventually rank opportunities according to personal relevance.

## Current Phase: Feasibility

Before building the application, test the fundamental architectural assumption:

> Can a relatively small number of reusable ingestion methods reliably monitor
> 50–100 relevant employers without requiring bespoke scraping logic for most
> companies?

### Initial Experiment

Research 50 target employers and determine:

- career-site / ATS platform
- availability of accessible job endpoints
- structured job data availability
- extraction method
- implementation difficulty
- requirement for bespoke code

### Success Criteria

The architecture is considered promising if:

- at least 70% of employers can be monitored using reusable ATS adapters
- at least 85% can be monitored when generic structured extraction is included
- no more than 15% require bespoke company-specific scraping
- historically relevant opportunities would achieve at least 80% detection
- adding another employer using an already-supported source requires minimal configuration

## Development Principles

1. Coverage before sophistication.
2. Automation before interface.
3. First-party sources before aggregators.
4. Reusable adapters before company-specific scrapers.
5. Verify assumptions before committing to architecture.
6. Keep the system explainable and maintainable.
7. Build only what demonstrably reduces manual effort.

## Feasibility spike

The repository contains the technical ingestion feasibility spike described in
`SPEC.md`. Runtime employer settings live in `config/companies.yaml`; the
research CSV remains evidence rather than runtime configuration.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest -q
.venv/bin/opportunity-radar --max-jobs 2
```

Live integration tests are intentionally separate:

```bash
.venv/bin/pytest -m live -o addopts='' -q
```

See `docs/ingestion_feasibility_report.md` for measured coverage, research
corrections, and the recommendation.

## Phase 2 state spike

The optional stateful runner wraps the validated ingestion boundary with SQLite
observations, lifecycle state, and deterministic change events:

```bash
.venv/bin/opportunity-radar-state --company pure_storage --max-jobs 2
```

This does not change the Phase 1 CLI or adapter contracts. See
`docs/state_change_architecture_report.md` for the Phase 2 evidence and limits.
The state refresh is serial across employers and serial across each employer's
details. It preserves the complete identity inventory for lifecycle inference,
then fetches details only for references retained by the geography-first scope
policy. Explicitly out-of-scope references are intentional skips, not detail
failures. `--max-jobs N` applies after scope selection, so it never limits the
lifecycle inventory; sampling is recorded with `selected_details_complete=false`.
Successful details are reused while their listing fingerprint is unchanged and
the periodic refresh interval is not due. The default conservative interval is
168 hours; override it with `--detail-refresh-hours HOURS` or declaratively per
source with `options.detail_refresh_hours`. Existing pre-migration detail rows
are refreshed once to establish reuse evidence.
A bounded 18-employer diagnostic run is therefore:

```bash
.venv/bin/opportunity-radar-state --max-jobs 5
```

The bounded pre-detail scope experiment measures conservative geography
selection from complete listing inventories without fetching any details or
writing Phase 2 state:

```bash
.venv/bin/opportunity-radar-scope-measure
```

Its immutable JSON artifact separates projected normalization operations from
projected network detail requests. Unknown geography and remote eligibility
remain selected; titles are recorded but never used for exclusion.
`--workday-schema-sample 3` additionally records bounded public listing-entry
samples and the first listing response's keys/facets for each Workday employer;
it still performs no detail requests.
`--successfactors-diagnostic-pages 2` captures a bounded, sanitized snapshot of
pagination, totals, filters, data attributes, hidden fields, and referenced
public endpoints from SuccessFactors listing pages already requested.

## Phase 3 relevance spike

The offline Phase 3 layer loads a versioned candidate profile and shared
taxonomy, applies conservative eligibility, extracts neutral evidence,
performs rank-only triage, and produces explainable candidate-specific
assessments. Its deterministic fake semantic assessor validates contracts,
scoring, SQLite reuse, and benchmark portability without an external model:

```bash
.venv/bin/opportunity-radar-phase3 --output output/phase3_benchmark.json
```

Phase 3 does not modify adapters, normalized jobs, or lifecycle state. See
`docs/phase3_architecture_report.md` for benchmark limitations and the next
experimental step.

The bounded semantic ROI harness compares a genuinely pre-semantic baseline,
configured model tiers, projected token cost, stability, and selective-call
strategies:

```bash
.venv/bin/python -m opportunity_radar.roi_experiment
```

External calls are opt-in with `--run-external` and require the credential
named in `config/semantic_experiment.yaml`. Offline execution never makes a
model call.

Before the bounded 28-call run, verify transport and credentials with exactly
one identical semantic request:

```bash
.venv/bin/python -m opportunity_radar.roi_experiment --smoke-external
```

## Live Decision Validation experiment

The live-validation layer reuses the existing Phase 1–3 state and assessment
contracts. Preflight is read-only and never calls a semantic model:

```bash
.venv/bin/opportunity-radar-live-validation preflight
```

After reviewing source health, cache misses, and estimated cost, assessment is
an explicit opt-in command. It uses Luna only and writes an immutable usage
manifest:

```bash
.venv/bin/opportunity-radar-live-validation assess
.venv/bin/opportunity-radar-live-validation prepare
.venv/bin/opportunity-radar-live-validation record <batch_id> <review_number> APPLY --agree
.venv/bin/opportunity-radar-live-validation report <batch_id>
```

Batch manifests are immutable. Human corrections append a new JSONL judgment
that identifies the judgment it supersedes; historical records are never
rewritten. The reviewed sample is deliberately stratified and its aggregate
metrics are not presented as a market-wide estimate.
