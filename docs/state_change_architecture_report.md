# Opportunity Radar — Phase 2 State & Change Detection Report

Run date: 2026-08-24

Scope: persistent state and deterministic change detection only

Recommendation: **GO for the Phase 2 state architecture**

## Result

Phase 2 adds a persistence-agnostic boundary after Phase 1 ingestion. Adapters and the existing feasibility CLI remain operational. A separate stateful runner records source evidence, normalized job observations, current lifecycle state, and deterministic change events in SQLite.

The offline suite passes all specified lifecycle scenarios plus the additional closure, sampling, rollback, and idempotency cases. Two repeated live observations across five source families produced stable inventories and zero false changes on the second run.

## Architecture

The implemented flow is:

```text
JobSourceAdapter
  -> complete JobReference inventory
  -> successful NormalizedJob details
  -> SourceOutcome
  -> employer-level SQLite transaction
  -> JobObservation evidence
  -> lifecycle/content inference
  -> JobInstance state + Events
```

Inventory and detail completeness are independent:

- `inventory_complete` controls presence and closure inference.
- `details_complete` records whether all current content was retrieved.
- `observed_count` is the number of identities in the completed inventory.
- Detail failures preserve presence but cannot overwrite fingerprints or snapshots.
- Sampling can retain a complete inventory while producing incomplete detail coverage.

Confirmed zero inventory is stored as `SUCCESS`, `inventory_complete=true`, and `observed_count=0`. An empty result without confirmed-zero evidence is an incomplete extraction failure and cannot close jobs.

## SQLite and transactions

The sample database uses schema version 1 and contains:

- `ingestion_runs`
- `source_observations`
- `job_instances`
- `job_observations`
- `events`

Foreign keys are enabled for every connection. Partial unique indexes enforce exact external-ID identity and company-scoped canonical-URL fallback identity. Network ingestion completes before the employer write transaction starts. A failed state transaction rolls back all state changes; its failure observation is then recorded separately.

Change inference is implemented in Python rather than SQL or adapters. Normalized snapshots remain immutable evidence. `job_instances` stores only lifecycle/current-fingerprint pointers and does not duplicate the current snapshot.

## Fingerprinting

Material fingerprints include title, deterministically sorted location tuples, work mode, employment type, department, and description. Canonicalization uses Unicode NFKC, HTML-to-text conversion, NBSP/whitespace collapse, trimming, stable JSON, and SHA-256.

Operational and identity metadata—including retrieval time, source, canonical URL, posting date, and validity date—is excluded. Description comparison is normalized exact comparison; no fuzzy threshold or LLM is used.

## Offline evidence

The deterministic suite covers:

- new and unchanged jobs;
- new plus closed jobs;
- failed and unvalidated-empty sources producing no closures;
- confirmed zero inventory closing all active jobs;
- material field changes;
- formatting-only description changes;
- exact-identity reopening;
- location-order stability;
- known present jobs with failed details;
- sampled detail runs preserving unsampled content;
- transaction rollback;
- repeated processing without duplicate observations/events;
- repeated closed observations without duplicate closure events;
- URL-only identity remaining separate from a later external-ID identity.

Result: **29 offline tests passed**, with live tests separately excluded by default.

## Repeated live stability evidence

Johnson & Johnson was replaced by Red Hat because the former had already demonstrated repeated request-timeout behavior in the Phase 1 acceptance rerun. The live set was:

- Red Hat / Workday
- Pure Storage / Greenhouse
- Siemens / Alma Career
- SAP / SuccessFactors
- Roche / Phenom

Both runs completed all five inventories successfully. Each run intentionally sampled two details per employer, so `details_complete=false` and the run status is correctly `PARTIAL`.

| Employer | Inventory count, run 1 | Inventory count, run 2 |
|---|---:|---:|
| Red Hat | 40 | 40 |
| Pure Storage | 302 | 302 |
| Siemens | 51 | 51 |
| SAP | 25 | 25 |
| Roche | 1,159 | 1,159 |

Run 1 created 10 `NEW` events for the sampled normalized jobs. Run 2 wrote 10 new observation records and produced **zero content or lifecycle events**. No jobs were falsely closed; all ten persisted instances remained active.

Evidence is available in:

- `output/phase2_sample.sqlite3`
- `output/state_change_report_run1.txt`
- `output/state_change_report.txt`

## Architecture corrections

1. Phase 1's `EmptyInventoryError` was split into confirmed and unvalidated variants. The existing Phase 1 runner still treats both as the display status `EMPTY`; only Phase 2 interprets confirmed zero as complete lifecycle evidence.
2. A source outcome was introduced between ingestion and persistence because the Phase 1 `EmployerResult` does not preserve inventory identities or separate inventory/detail completeness.
3. Source persistence errors use `INTERNAL_ERROR`. This is operational evidence rather than a source-network classification.
4. Sampled runs are `PARTIAL` even when every inventory succeeds, because content observation is deliberately incomplete.
5. URL-only identities are not migrated or merged when an external ID later appears.

## Recommendation

**GO** for the Phase 2 state/change architecture. The model preserves evidence, prevents closure under incomplete observations, produces deterministic changes, and remains isolated from adapters and product concerns.

This recommendation does not authorize scoring, LLMs, UI, notifications, scheduling, cloud deployment, probabilistic deduplication, repost detection, or other product features.
