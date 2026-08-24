# Opportunity Radar
## Technical Feasibility Spike — Specification v0.1

## 1. Purpose

Opportunity Radar is intended to automate discovery of relevant employment
opportunities across the Czech and remote-accessible European job market.

The initial market research examined 50 target employers.

The research suggests that a relatively small number of recurring career-site
and ATS patterns may cover a large proportion of these employers.

This spike exists to test that assumption with working code before committing
to the architecture of the full Opportunity Radar system.

The spike is successful if reusable adapters can reliably retrieve live
vacancies from representative employers and transform them into one common
job representation.


## 2. Question Being Tested

Can a small number of reusable ingestion adapters monitor a substantial
number of employers without requiring company-specific scraping logic?

This is an architecture-validation experiment, not a production application.


## 3. Evidence From Research

The initial 50-company fingerprinting exercise identified these important
source families:

- Workday
- Alma Career / Jobs.cz
- SuccessFactors
- Greenhouse
- Ashby
- SmartRecruiters
- Phenom-like career sites
- generic first-party career-search pages
- a small number of company-specific implementations

The first-pass research indicates approximately:

- 50 employers examined
- 37 technically verified
- 12 probable
- 1 unclear
- ~66% potentially covered by reusable standardized ATS/board adapters
- ~98% with some plausible machine-readable first-party ingestion route
- ~12% currently expected to require company-specific handling

These figures are hypotheses from research and must now be validated through
working ingestion code.


## 4. Scope

The spike will initially implement five ingestion families:

1. Workday
2. Greenhouse
3. Alma Career / Jobs.cz
4. SuccessFactors
5. Generic first-party career search

The first four test reusable platform adapters.

The fifth tests whether employers without a supported ATS can still be handled
through a reusable generic extraction mechanism.


## 5. Representative Employers

Use multiple employers from each family where practical.

Suggested initial test set:

### Workday

- Johnson & Johnson
- Red Hat
- Pfizer

### Greenhouse

- Pure Storage
- Productboard
- WPP

### Alma Career / Jobs.cz

- Siemens
- Honeywell
- ČSOB

### SuccessFactors

- SAP
- EY
- Deutsche Börse Group

### Generic Career Search

- GoodData
- Kiwi.com
- Allegro

Target:

15 employers across 5 ingestion families.

The exact employers may be changed if technical investigation shows that a
research classification was incorrect.

Such corrections should be documented rather than worked around silently.


## 6. Non-Goals

Do NOT implement:

- user interface
- Streamlit
- authentication
- automated job applications
- LinkedIn scraping
- job relevance scoring
- LLM integration
- embeddings
- vector database
- notifications
- scheduling
- CV generation
- application tracking
- remote deployment
- production monitoring

These belong to later phases.

The purpose of this spike is ingestion feasibility only.


## 7. Normalized Job Model

Every adapter must attempt to return the same representation.

Required fields:

- source
- company_id
- company_name
- external_job_id
- title
- location
- canonical_url
- description
- date_posted
- retrieved_at

Optional fields:

- valid_through
- employment_type
- remote_status
- department
- country
- city

Fields unavailable from a source should be null.

Adapters must not invent missing values.


## 8. Proposed Architecture

    target_companies.csv
            |
            v
      Source configuration
            |
            v
       Adapter registry
            |
       +----+----+----+----+
       |    |    |    |    |
       v    v    v    v    v
      WD    GH   AC   SF   Generic
       |    |    |    |    |
       +----+----+----+----+
            |
            v
       Raw source data
            |
            v
         Normalize
            |
            v
      NormalizedJob[]
            |
            v
     Validation / Report


WD = Workday
GH = Greenhouse
AC = Alma Career
SF = SuccessFactors


## 9. Adapter Contract

All adapters should expose the same conceptual interface.

Example:

    class JobSourceAdapter:
        def fetch_jobs(self, company_config) -> list[NormalizedJob]:
            ...

Implementation details may differ between ATS families.

The rest of the application should not need to know whether a vacancy came
from Workday, Greenhouse, Alma Career, SuccessFactors, or generic HTML.


## 10. Configuration Over Code

Employer-specific information should live in configuration wherever possible.

Example concept:

    company_id: johnson_johnson
    company_name: Johnson & Johnson
    adapter: workday
    tenant: ...
    careers_url: ...

Adding another employer using an already-supported ATS should ideally require
configuration only.

Avoid:

    if company == "Johnson & Johnson":
        ...

unless the spike proves that a genuine source-specific exception is necessary.


## 11. Source Behaviour

Adapters should:

1. request the current vacancy inventory
2. retrieve available job metadata
3. construct or capture canonical job URLs
4. retrieve job descriptions where reasonably possible
5. normalize results
6. report failures explicitly

Adapters should not:

- bypass authentication
- bypass CAPTCHAs
- attempt anti-bot evasion
- scrape LinkedIn
- submit applications
- imitate logged-in users

Only publicly accessible vacancy information is in scope.


## 12. Error Handling

Failure of one employer must not terminate the entire run.

Example:

    J&J             PASS    42 jobs
    Red Hat         PASS    31 jobs
    Pfizer          FAIL    HTTP 403
    Pure Storage    PASS    57 jobs

The system should continue processing remaining employers.

Errors should contain enough information for diagnosis.


## 13. Validation

For every employer tested, record:

- source reachable
- jobs returned
- number of jobs
- required fields populated
- stable job ID available
- canonical URL available
- description available
- location available
- posting date available
- parsing errors
- request errors
- adapter used

A source returning HTTP 200 but zero jobs is NOT automatically considered
successful.

Zero results must be distinguishable from extraction failure.


## 14. Output

The spike should produce a human-readable report.

Example:

    OPPORTUNITY RADAR — INGESTION SPIKE

    Employers tested: 15
    Successful: 13
    Failed: 2

    Workday
    -------------------------
    Johnson & Johnson   PASS
    Red Hat             PASS
    Pfizer              PASS

    Greenhouse
    -------------------------
    Pure Storage        PASS
    Productboard        PASS
    WPP                 PASS

    ...

It should also save normalized job records in a machine-readable format.

Preferred initial format:

    output/jobs.json

CSV may additionally be generated if useful.


## 15. Metrics

Calculate:

### Employer success rate

    successfully ingested employers / tested employers


### Adapter success rate

For each adapter family:

    successfully ingested employers / employers tested


### Field completeness

For required fields:

    populated values / possible values


### Reusability

Track whether employer-specific parsing logic was required.


### Effective adapter coverage

Using target_companies.csv, estimate how many of the 50 researched employers
could theoretically use each adapter that successfully passes the spike.


## 16. Success Criteria

The spike PASSES if:

1. At least 80% of representative employers can be ingested successfully.

2. At least 4 of the 5 tested ingestion families work reliably.

3. At least 90% of successfully ingested jobs contain:

   - company
   - title
   - location
   - canonical URL
   - external job ID

4. At least 80% contain a usable job description.

5. Platform adapters work across multiple employers without employer-specific
   parsing logic.

6. Failures are isolated and observable.

7. Results support the hypothesis that the architecture can reasonably scale
   toward 50+ employers.


## 17. Failure Criteria

The architecture should be reconsidered if:

- major ATS families require bespoke logic per employer
- fewer than 4 source families prove reusable
- fewer than 80% of representative employers can be ingested
- career sources frequently block automated public access
- canonical job identity cannot be established reliably
- job descriptions cannot be retrieved sufficiently for future relevance scoring


## 18. Proposed Repository Structure

    opportunity-radar/
    |
    +-- README.md
    +-- SPEC.md
    |
    +-- research/
    |   +-- target_companies.csv
    |
    +-- src/
    |   +-- opportunity_radar/
    |       +-- __init__.py
    |       +-- models.py
    |       +-- registry.py
    |       +-- runner.py
    |       |
    |       +-- adapters/
    |           +-- __init__.py
    |           +-- base.py
    |           +-- workday.py
    |           +-- greenhouse.py
    |           +-- almacareer.py
    |           +-- successfactors.py
    |           +-- generic.py
    |
    +-- tests/
    |   +-- test_models.py
    |   +-- test_registry.py
    |   +-- adapters/
    |
    +-- output/
        +-- jobs.json
        +-- ingestion_report.txt


## 19. Testing Philosophy

Tests should distinguish between:

### Unit tests

Test parsing and normalization using saved fixtures.

These should:

- run offline
- be deterministic
- run quickly


### Live integration tests

Test current public career sources.

These may fail because external websites change.

They should therefore be clearly separated from unit tests.


## 20. Implementation Principles

### Prefer observation over assumptions

If live source behaviour contradicts target_companies.csv, update the research
classification.

### Prefer reusable abstractions

Do not solve a platform problem with employer-specific code unless necessary.

### Preserve raw evidence

Where useful, retain representative source responses as test fixtures.

### Fail visibly

Never silently convert parsing failure into an empty vacancy list.

### Keep the spike disposable

Code quality should be sufficient to understand and test the architecture, but
do not prematurely optimize for production scale.

### Coverage before sophistication

The objective is to determine how much of the target market a small number of
adapters can reliably cover.


## 21. Deliverable

At completion, provide:

1. working ingestion prototype
2. automated tests
3. normalized job output
4. ingestion report
5. observed adapter success rates
6. list of source/classification corrections
7. estimate of coverage across the original 50-company dataset
8. recommendation:

   GO
   CONDITIONAL GO
   or
   NO-GO

for proceeding to Opportunity Radar V1.

Architecture Decisions Added in v0.2

Adapter Boundary

Adapters must separate vacancy discovery from vacancy detail retrieval.

The adapter contract is:

list_jobs(company_config) -> list[JobReference]
fetch_job(job_reference) -> NormalizedJob

list_jobs() answers:

What vacancies currently exist for this employer?

fetch_job() answers:

What are the normalized details for this vacancy?

This separation is intentional because many ATS platforms expose lightweight vacancy inventories separately from detailed vacancy pages or endpoints.

It also preserves a clean path toward future incremental ingestion, where only newly discovered or changed vacancies need full detail retrieval.

The spike does not need persistent incremental state yet.

⸻

JobReference

A JobReference should contain only the minimum information needed to uniquely reference and retrieve a vacancy.

Suggested model:

@dataclass
class JobReference:
    company_id: str
    external_job_id: str | None
    canonical_url: str

Additional source-specific metadata may be stored only if needed for later retrieval.

⸻

NormalizedJob

The normalized model represents one underlying vacancy regardless of source platform.

Suggested fields:

@dataclass
class NormalizedJob:
    company_id: str
    company_name: str
    external_job_id: str | None
    title: str
    locations: list[JobLocation]
    work_mode: WorkMode
    canonical_url: str
    description: str | None
    date_posted: date | None
    valid_through: date | None
    employment_type: str | None
    department: str | None
    source: str
    retrieved_at: datetime

Adapters must not invent missing values.

⸻

Location Model

A vacancy is represented as one job regardless of how many locations are associated with the posting.

Locations must not be represented by duplicating job records.

Each job contains:

locations: list[JobLocation]

Suggested location model:

@dataclass
class JobLocation:
    raw: str
    city: str | None = None
    region: str | None = None
    country: str | None = None

The original source location string must always be preserved in raw.

Work arrangement is represented separately:

class WorkMode(Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNSPECIFIED = "unspecified"

Do not infer work mode unless the source provides sufficient evidence.

Example:

Senior Pricing Analyst
external_job_id: R12345
work_mode: HYBRID
locations:
  - Prague, Czechia
  - Zagreb, Croatia
  - Istanbul, Turkey

⸻

Source Truth vs Interpretation

Adapters are responsible for preserving and normalizing source data.

They are not responsible for deciding whether a job is relevant to the user.

Conceptually:

source value
    ↓
raw source representation
    ↓
safe normalization
    ↓
later filtering/scoring

Example:

"Prague, Czech Republic"
    ↓
raw = "Prague, Czech Republic"
city = "Prague"
country = "Czechia"

Whether Prague is an eligible location is handled later outside the adapter layer.

⸻

Company Configuration

Research data and runtime configuration must remain separate.

research/target_companies.csv is the feasibility dataset.

Runtime ingestion configuration should live separately, for example:

config/companies.yaml

Suggested runtime model:

@dataclass
class CompanyConfig:
    company_id: str
    company_name: str
    adapter: str
    careers_url: str | None = None
    jobs_search_url: str | None = None
    ats_tenant: str | None = None
    endpoint_url: str | None = None
    location_filters: list[str] | None = None
    remote_eligible: bool | None = None
    options: dict[str, Any] = field(default_factory=dict)

Employer-specific values should be expressed as configuration wherever possible.

⸻

Adapter Registry

The registry maps configured adapter families to their implementations.

Conceptually:

class AdapterRegistry:
    _adapters = {
        "workday": WorkdayAdapter,
        "greenhouse": GreenhouseAdapter,
        "almacareer": AlmaCareerAdapter,
        "successfactors": SuccessFactorsAdapter,
        "generic_html": GenericHtmlAdapter,
    }

The registry must not contain employer-specific conditional logic.

Forbidden pattern:

if company_id == "johnson_johnson":
    ...

The registry chooses adapter families only.

⸻

Configuration Validation

Adapter-specific configuration must be validated before network requests begin.

Examples:

* Greenhouse may require an ATS tenant/board identifier.
* Workday may require tenant/site information.
* Generic HTML may require declarative selector configuration.

Failures should produce explicit configuration errors rather than obscure downstream parsing failures.

⸻

Generic Adapter Constraint

A generic adapter must genuinely be generic.

Adding a new employer to GenericHtmlAdapter should normally require configuration rather than Python code.

Acceptable:

selectors:
  job_container: "..."
  title: "..."
  url: "..."
  location: "..."

Not acceptable:

if company == "GoodData":
    ...
elif company == "Kiwi":
    ...

If Python changes are required for one employer, treat it as bespoke integration and record that fact explicitly.

⸻

Reusability Test

Where practical, each reusable adapter family should be tested against at least three employers.

An adapter family is considered reusable only if the same implementation works across multiple employers without employer-specific parsing logic.

Example:

WorkdayAdapter
    ├── Johnson & Johnson
    ├── Red Hat
    └── Pfizer

All three should use the same code path.

⸻

Job Identity

Preferred exact identity:

company_id + external_job_id

When a stable external ID is unavailable, canonical URL may act as a secondary exact identifier.

Adapters should preserve enough source information to support future deduplication.

⸻

Deduplication Strategy

The long-term deduplication hierarchy is:

1. Exact identity:
    company_id + external_job_id
2. Canonical URL match
3. Deterministic fingerprint based on normalized fields
4. Probabilistic duplicate scoring when deterministic identity is insufficient

Probabilistic scoring is intentionally not implemented in the ingestion spike.

Its eventual weights and thresholds must be configurable and calibrated against real vacancy data rather than hardcoded now.

⸻

Duplicate vs Repost

Future versions should distinguish between:

* duplicate: multiple representations of the same vacancy
* repost: a newly issued vacancy that is materially similar to an older posting

A future model may separate:

job_instance_id
job_family_id

This is out of scope for the current ingestion spike.

⸻

Implementation Scope Reminder

Implement now:

* source configuration
* adapter registry
* JobReference
* structured locations
* work mode
* NormalizedJob
* list_jobs()
* fetch_job()
* adapter-family reuse
* explicit validation and reporting
* JSON output
* tests

Do not implement now:

* persistent job state
* incremental database ingestion
* probabilistic deduplication
* repost detection
* relevance scoring
* LLMs
* UI
* notifications
* automated applications


# Opportunity Radar
## Phase 2 — Operational Stability: State & Change Detection

## 1. Purpose

Phase 1 validated that Opportunity Radar can ingest vacancies from reusable source families and normalize them into a common job representation.

Phase 2 validates that repeated ingestion runs can be converted into reliable persistent state and meaningful change events.

The system must distinguish:

- what was observed;
- what is currently believed to be true;
- how that belief changed over time.

This phase is about temporal correctness and operational stability.

It is not yet about personal relevance, notifications, or user interface.

---

## 2. Core Principle

> Observations are evidence.  
> State is interpretation.  
> Events describe how state changes over time.

Never destroy observation evidence merely because the current interpretation changes.

---

## 3. Question Being Tested

Can Opportunity Radar repeatedly ingest employer inventories and correctly identify:

- new vacancies;
- unchanged vacancies;
- materially changed vacancies;
- closed vacancies;
- reopened vacancies;

without creating false lifecycle transitions when a source fails or is incompletely observed?

---

## 4. Architectural Boundary

Phase 1 remains unchanged.

```text
External career sources
        ↓
JobSourceAdapter
        ↓
NormalizedJob[]
        ↓
──────── Phase 1 boundary ────────
        ↓
State / Observation Layer
        ↓
Change Detection
        ↓
Events
```

Adapters must remain unaware of persistence and historical state.

---

## 5. Persistence Technology

Use SQLite as the Phase 2 persistence layer.

Reasons:

- zero external infrastructure;
- transactional state;
- uniqueness constraints;
- incremental writes;
- simple historical queries;
- built into Python;
- sufficient scale for the expected workload;
- straightforward migration path later if required.

Do not introduce PostgreSQL, cloud databases, or distributed infrastructure.

---

## 6. Core Concepts

### IngestionRun

Represents one execution of the ingestion pipeline.

Suggested fields:

```python
run_id
started_at
completed_at
status
```

Possible run status values:

```text
RUNNING
COMPLETED
PARTIAL
FAILED
```

---

### SourceObservation

Represents what happened when one employer/source was inspected during one run.

Suggested fields:

```python
run_id
company_id
adapter
status
expected_count
observed_count
complete
error_type
error_message
observed_at
```

Source-level completeness is critical.

Possible source states should preserve the Phase 1 failure semantics:

```text
SUCCESS
EMPTY
SCHEMA_MISMATCH
COUNT_MISMATCH
REQUEST_ERROR
```

Absence of a vacancy may only be interpreted as closure when the source observation is successful and complete.

---

### JobInstance

Represents the persistent identity of one vacancy over time.

Suggested fields:

```python
job_instance_id
company_id
external_job_id
canonical_url

first_seen_at
last_seen_at

lifecycle_state
current_fingerprint
current_snapshot
```

Initial lifecycle states:

```text
ACTIVE
CLOSED
```

A future phase may introduce richer lifecycle states if justified.

---

### JobObservation

Represents one observed state of a vacancy during one ingestion run.

Suggested fields:

```python
run_id
job_instance_id
observed_at
fingerprint
normalized_snapshot
```

`normalized_snapshot` should preserve the serialized normalized job representation.

The observation history must allow later re-evaluation of state transitions.

---

### Event

Represents a meaningful transition or material change.

Suggested fields:

```python
event_id
job_instance_id
run_id
event_type
occurred_at
change_data
```

Initial lifecycle events:

```text
NEW
CLOSED
REOPENED
```

Initial content events:

```text
TITLE_CHANGED
LOCATION_CHANGED
WORK_MODE_CHANGED
EMPLOYMENT_TYPE_CHANGED
DEPARTMENT_CHANGED
DESCRIPTION_CHANGED
```

Multiple content changes may occur in one run.

---

## 7. Identity

Use the identity hierarchy already defined in Phase 1.

Primary:

```text
company_id + external_job_id
```

Secondary exact identity:

```text
canonical_url
```

Probabilistic duplicate detection remains out of scope.

Do not implement `job_family_id` or repost similarity in Phase 2.

---

## 8. Location Model

Retain the Phase 1 multi-location representation.

One vacancy remains one `JobInstance`.

```python
locations: list[JobLocation]
```

Location ordering must not create false change events.

Canonical comparison must therefore normalize/sort locations deterministically before fingerprinting.

Raw source location values remain preserved in snapshots.

---

## 9. Content Fingerprint

Each observed job must have a deterministic material-content fingerprint.

The fingerprint should be calculated from a canonical representation containing fields such as:

```text
title
locations
work_mode
department
employment_type
description
```

Do not include volatile operational metadata such as:

```text
retrieved_at
tracking query parameters
formatting-only HTML differences
```

Suggested process:

```text
NormalizedJob
    ↓
Canonical material representation
    ↓
Normalize harmless formatting
    ↓
Deterministic serialization
    ↓
SHA-256
```

Equal fingerprints imply no material content change.

Different fingerprints trigger field-level comparison.

---

## 10. Field-Level Change Detection

When fingerprints differ, compare material fields individually.

Example output:

```text
TITLE_CHANGED
old: Senior Pricing Analyst
new: Senior Pricing Analytics Specialist
```

```text
LOCATION_CHANGED
added:
  Prague, Czechia
removed:
  Zagreb, Croatia
```

For descriptions:

- normalize HTML and insignificant whitespace;
- preserve source snapshots;
- do not emit changes caused solely by formatting noise.

Description materiality thresholds should be configurable.

Do not use an LLM for comparison.

---

## 11. Lifecycle Inference

### New

A vacancy is `NEW` when its identity is observed successfully for the first time.

```text
unknown job
+
successful source observation
+
job present
→ NEW + ACTIVE
```

---

### Unchanged

Previously active vacancy is observed again with the same material fingerprint.

```text
ACTIVE
+
present
+
same fingerprint
→ remains ACTIVE
```

No event is required unless useful for debugging.

---

### Changed

Previously active vacancy is observed again with a different material fingerprint.

```text
ACTIVE
+
present
+
different fingerprint
→ remains ACTIVE
+ content event(s)
```

---

### Closed

A vacancy may transition to `CLOSED` only when:

1. it was previously ACTIVE;
2. the employer/source inventory was successfully and completely observed;
3. the vacancy identity is absent from that complete inventory.

```text
ACTIVE
+
source SUCCESS + COMPLETE
+
job absent
→ CLOSED
```

Critical rule:

> A source timeout, schema error, incomplete pagination, count mismatch, or other unsuccessful source observation must never close jobs.

---

### Reopened

If the same exact vacancy identity is observed after being CLOSED:

```text
CLOSED
+
same exact identity observed
→ ACTIVE + REOPENED
```

Do not attempt to decide whether a different requisition ID represents a repost during this phase.

---

## 12. Observation Retention

Preserve enough evidence to explain every state transition.

For Phase 2:

- retain every `SourceObservation`;
- retain every material `JobObservation`;
- retain every generated `Event`.

Optimization or historical compaction is out of scope.

---

## 13. SQLite Schema

Initial logical schema:

```text
ingestion_runs
source_observations
jobs
job_observations
events
```

Use relational constraints where helpful.

Examples:

- unique identity where safely enforceable;
- foreign keys between observations/events and runs/jobs;
- transactional writes for one source/run where appropriate.

Avoid over-normalizing `NormalizedJob`.

The full normalized snapshot may be stored as JSON text in `job_observations`.

---

## 14. Transaction Semantics

A partial write must not create false lifecycle state.

Suggested rule:

1. persist the run;
2. ingest one employer;
3. validate source completeness;
4. persist observations;
5. infer transitions;
6. commit employer-level state atomically.

If processing an employer fails before completeness is established:

- record the source failure;
- do not alter lifecycle state for that employer's existing jobs.

---

## 15. Change Detection Service

Persistence and change inference should remain separate concerns.

Conceptual boundary:

```python
previous_state = repository.get_job_state(...)

changes = change_detector.compare(
    previous_state,
    current_observation,
)

repository.persist(...)
```

Do not bury change rules inside SQL statements or source adapters.

---

## 16. Offline Test Scenarios

Phase 2 must be testable without live career sites.

Create deterministic synthetic runs covering at least:

### Scenario A — New job

Run 1:
```text
A
B
```

Expected:
```text
A NEW
B NEW
```

### Scenario B — Unchanged

Run 2:
```text
A
B
```

Expected:
```text
A unchanged
B unchanged
```

### Scenario C — New + closed

Run 3:
```text
A
C
```

with complete source observation.

Expected:
```text
A active
B CLOSED
C NEW
```

### Scenario D — Source failure

Run 4:
```text
source REQUEST_ERROR
```

Expected:

```text
A remains active
C remains active
no closures
```

### Scenario E — Material change

Run 5:

```text
A work_mode HYBRID → REMOTE
```

Expected:

```text
A remains ACTIVE
WORK_MODE_CHANGED event
```

### Scenario F — Formatting-only description change

Expected:

```text
no material DESCRIPTION_CHANGED event
```

### Scenario G — Reopen

Previously closed B reappears with the same exact identity.

Expected:

```text
B ACTIVE
REOPENED event
```

### Scenario H — Multi-location ordering

Same locations returned in different order.

Expected:

```text
no LOCATION_CHANGED event
```

---

## 17. Live Stability Test

After offline behavior is proven, perform repeated live ingestion against a small representative employer set.

Suggested:

- Johnson & Johnson / Workday
- Pure Storage / Greenhouse
- Siemens / Alma
- SAP / SuccessFactors
- Roche / Phenom

Execute at least two live observations.

The objective is not necessarily to wait for a real vacancy change.

Validate:

- repeated inventories remain stable;
- unchanged jobs are not falsely marked changed;
- source failures do not alter lifecycle state;
- snapshots and run metadata persist correctly.

Synthetic fixtures remain authoritative for lifecycle edge cases.

---

## 18. Success Criteria

Phase 2 passes if:

1. all defined offline lifecycle scenarios pass;
2. failed/incomplete source observations create zero false closures;
3. repeated identical observations create zero false content changes;
4. multi-location ordering does not create false changes;
5. material field changes produce correct field-level events;
6. reopening the same exact identity produces `REOPENED`;
7. SQLite retains enough evidence to reconstruct why each event occurred;
8. repeated live runs do not corrupt or duplicate state;
9. adapters remain completely independent from persistence;
10. no product features enter scope.

---

## 19. Non-Goals

Do not implement:

- relevance scoring;
- LLM classification;
- personalized ranking;
- alerts;
- email;
- UI;
- Streamlit;
- scheduled execution;
- cloud deployment;
- LinkedIn ingestion;
- probabilistic deduplication;
- repost-family detection;
- automatic applications;
- CV tailoring.

---

## 20. Deliverables

At completion provide:

1. SQLite persistence implementation;
2. schema/migrations or initialization mechanism;
3. state repository layer;
4. change detection service;
5. deterministic fingerprints;
6. lifecycle/content events;
7. offline tests;
8. limited repeated live tests;
9. sample database;
10. human-readable state/change report;
11. documented architecture corrections;
12. recommendation:

```text
GO
CONDITIONAL GO
NO-GO
```

for operational state/change architecture.

---

## 21. Guiding Principle

> Never infer more certainty than the observations support.

Source reliability and completeness always take precedence over lifecycle inference.