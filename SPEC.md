# Opportunity Radar
## Cumulative Normative Specification — Phases 1–3

This file preserves the successive Phase 1–3 specifications. Explicit later
"Architecture Decisions After Review" sections supersede conflicting earlier
exploratory text within the same phase. Current implemented structure is
described in `docs/ARCHITECTURE.md`; current phase, frozen items, failures, and
next gate are in `docs/STATUS.md`. Phase 4 concepts are not implemented or
normative here yet.

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

# Opportunity Radar
## Phase 3 — Relevance, Fit & Opportunity Scoring

## 1. Purpose

Phase 1 established reliable ingestion from heterogeneous public career sources.

Phase 2 established persistent job state, repeated observations, lifecycle tracking, and deterministic change detection.

Phase 3 turns the resulting active-job universe into a ranked set of opportunities relevant to a specific candidate.

The system must reduce large volumes of vacancies into a manageable shortlist while preserving:

- explainability;
- candidate configurability;
- separation between facts and interpretation;
- separation between deterministic filtering and semantic judgment;
- independent scoring dimensions rather than one opaque score.

Phase 3 is the first phase whose output should directly reduce the user's manual job-search workload.

---

## 2. Core Question

Can Opportunity Radar reliably identify and rank high-value opportunities for a candidate while remaining:

- configurable for different candidates;
- explainable;
- resistant to noisy job titles;
- conservative with hard rejection rules;
- adaptable as candidate capabilities and goals evolve?

---

## 3. Guiding Principles

### Candidate-specific information is data, not code

Candidate background, preferences, goals, and constraints must be represented through configuration.

The scoring engine must not contain hard-coded knowledge of a particular candidate.

---

### Personal relevance is downstream of ingestion

Source ingestion remains candidate-independent.

```text
Sources
  ↓
Normalized jobs
  ↓
Persistent active state
  ↓
Eligibility
  ↓
Relevance assessment
```

Candidate preferences must never influence whether a vacancy is ingested or retained.

---

### Facts, interpretation, and estimates remain separate

Example:

```text
FACT
"Requires advanced Python"

    ↓

INTERPRETATION
Candidate has a significant Python capability gap

    ↓

ESTIMATE
Conversion probability decreases
Learning opportunity increases
```

Do not collapse these layers into one opaque decision.

---

### Hard filters should be rare

Reject jobs deterministically only when evidence establishes genuine incompatibility.

Examples:

- job cannot legally or practically be worked from an eligible location;
- mandatory language requirement is not met;
- role requires relocation that candidate explicitly forbids;
- clearly incompatible role family explicitly excluded by candidate.

Do not hard reject solely because of:

- seniority mismatch;
- degree requirement;
- technical gaps;
- industry change;
- unusual career trajectory.

Those belong in scoring.

---

### Preserve dimension scores independently

Never persist only a composite opportunity score.

Every dimension must remain available independently so weighting can change later without repeating semantic interpretation unnecessarily.

---

### Explain every meaningful score

Scores should include:

- value;
- confidence;
- reasoning;
- supporting evidence where available.

---

## 4. High-Level Architecture

```text
ACTIVE JOBS
    ↓
EligibilityFilter
    ↓
DeterministicFeatureExtractor
    ↓
TriageScore
    ↓
SemanticAssessment
    ↓
DimensionScores
    ↓
CompositeCalculator
    ↓
OpportunityAssessment
    ↓
Ranked Radar
```

Candidate configuration enters downstream:

```text
CandidateProfile
       ↓
EligibilityFilter
DeterministicFeatureExtractor
SemanticAssessment
CompositeCalculator
```

Employer-level intelligence may later enter independently through:

```text
EmployerProfile
       ↓
OpportunityAssessment
```

---

## 5. CandidateProfile

The scoring engine consumes a structured `CandidateProfile`.

The profile represents candidate facts, capabilities, experience, preferences,
hard constraints, strategic goals, and scoring preferences.

Conceptual structure:

```text
CandidateProfile
├── profile
├── facts
├── capabilities
├── experience
├── preferences
├── hard_constraints
├── strategic_goals
└── scoring_preferences
```

---

## 6. Experience Representation

Some candidate attributes are better represented as experience/context rather than skills.

Examples:

```yaml
experience:
  years_total: 20

  leadership:
    people_management: true
    max_direct_team_size: 3

  environments:
    - global_enterprise
    - matrix_organization
    - technology

  domains:
    - subscriptions
    - cybersecurity
    - pricing
    - customer_retention
    - business_operations
```

This supports interpretation of requirements such as:

- senior stakeholder exposure;
- global organization experience;
- matrix leadership;
- regulated-sector experience;
- team-size requirements.

---

## 7. Preferences

Preferences influence desirability but are not hard constraints.

Example:

```yaml
preferences:
  sectors:
    preferred:
      - technology
      - healthcare
      - fintech
      - data

  role_characteristics:
    preferred:
      - business_analytics
      - decision_intelligence
      - ai_transformation
      - strategy
      - business_operations
      - product_adoption

  work_style:
    prefer:
      - autonomy
      - analytical_problem_solving
      - cross_functional_work
```

---

## 8. Constraints

Constraints can produce deterministic rejection when explicitly configured as hard constraints.

Example:

```yaml
constraints:
  location:
    home_country: Czechia
    eligible_cities:
      - Prague
    remote_from_home_country: true
    relocation_allowed: false

  languages:
    Czech: native
    English: fluent

  excluded_role_families:
    - quota_carrying_sales
    - pure_software_engineering
    - ml_research
```

The configuration must distinguish hard constraints from preferences.

---

## 9. Strategic Goals

Strategic goals represent direction rather than current capability.

Example:

```yaml
strategic_goals:
  ai_future_alignment:
    importance: very_high

  learning:
    importance: high

  career_optionality:
    importance: high

  autonomy:
    importance: high

  compensation:
    importance: medium

  employer_brand:
    importance: medium
```

This distinction matters because a capability gap can lower immediate fit while increasing learning value.

Example:

```text
Advanced SQL required
Candidate SQL = intermediate

Immediate fit             ↓
Conversion probability    ↓
Learning opportunity      ↑
Long-term value           ↑ potentially
```

The scoring engine should be able to represent such trade-offs.

---

## 10. Candidate Profile Versioning

Candidate capabilities and priorities change over time.

Each profile should therefore have:

```text
profile_id
version
created_at
```

Future opportunity assessments should record which profile version produced them.

This enables later comparisons such as:

```text
Profile Aug 2026
SQL = intermediate

Profile Jan 2027
SQL = advanced
```

and future analysis of how learning changed opportunity fit.

Full profile-history analytics are out of scope for Phase 3.

---

## 11. Stage 1 — Eligibility Filter

Eligibility answers only:

> Is this vacancy realistically addressable?

Output:

```text
ELIGIBLE
INELIGIBLE
UNCERTAIN
```

Each result must include explicit reasons.

Examples:

```text
INELIGIBLE
reason:
"Position requires permanent residence in the United States."
```

```text
ELIGIBLE
reason:
"Prague is explicitly listed as a job location."
```

```text
UNCERTAIN
reason:
"Posting says remote but does not define eligible countries."
```

`UNCERTAIN` should normally remain in the funnel rather than being rejected.

---

## 12. Eligibility Rules

Initial deterministic eligibility should evaluate:

- physical location;
- remote eligibility;
- relocation requirements;
- explicit work authorization constraints where available;
- mandatory language requirements;
- explicitly excluded role families.

Avoid inference beyond evidence.

If information is missing:

```text
UNKNOWN != INELIGIBLE
```

---

## 13. Stage 2 — Deterministic Feature Extraction

Eligible jobs receive inexpensive deterministic feature extraction.

The purpose is:

- triage;
- reduce semantic-scoring volume;
- expose useful structured signals.

This layer is not the final judgment.

Suggested positive concept families:

```text
business_analytics
business_operations
strategy
transformation
decision_support
decision_intelligence
pricing
forecasting
experimentation
stakeholder_management
leadership
ai
genai
automation
product
change_management
commercial_strategy
```

Suggested negative/specialization features:

```text
software_engineering_heavy
data_engineering_heavy
ml_research_heavy
devops_heavy
quota_sales
regulated_specialist
very_junior
deep_domain_specialization
```

Use concept dictionaries/synonym groups rather than isolated keywords where practical.

---

## 14. Deterministic Triage Score

A cheap preliminary score may be calculated to control semantic-processing volume.

Example:

```text
triage_score: 0–100
```

Its purpose is only:

> Which jobs deserve deeper analysis?

It should not be displayed as the final opportunity score.

Thresholds must be configurable.

Hard eligibility always takes precedence over triage.

---

## 15. Semantic Assessment

Only vacancies passing configurable triage criteria receive semantic assessment.

The semantic layer must evaluate the vacancy against the structured CandidateProfile.

It should return structured output rather than free-form prose.

Suggested output domains:

- functional fit;
- existing-experience leverage;
- AI/future alignment;
- learning opportunity;
- long-term strategic value;
- conversion probability;
- seniority fit;
- employer/career value where context exists;
- compensation potential where evidence exists;
- lifestyle/autonomy.

---

## 16. Dimension Scores

Initial dimensions:

### Functional Fit

How closely does the actual work align with candidate capabilities and preferred work?

---

### Existing Experience Leverage

How much does the role benefit from accumulated candidate expertise?

---

### AI / Future Alignment

How strongly does the role position the candidate toward durable AI-era capabilities and environments?

---

### Learning Opportunity

How much valuable capability development is likely?

A gap may increase this score while decreasing immediate fit.

---

### Long-Term Strategic Value

How much option value could this role create over a 5–10+ year horizon?

Consider:

- capability compounding;
- future role access;
- network exposure;
- industry exposure;
- strategic breadth.

---

### Conversion Probability

Estimate likelihood of progressing through the hiring funnel.

Treat separately from desirability.

Inputs may include:

- direct requirement alignment;
- seniority mismatch;
- education requirements;
- technical gaps;
- industry specialization;
- language requirements;
- unusually strong transferable experience.

Do not assume functional fit equals conversion probability.

---

### Seniority Fit

Compare job level/responsibility with candidate career level.

Both over-leveling and substantial down-leveling may reduce score.

---

### Employer / Career Value

Eventually derived primarily from EmployerProfile rather than repeatedly inferred from each vacancy.

For Phase 3, this dimension may remain limited or partially populated.

---

### Compensation Potential

Score only when supported by evidence or cautiously inferred.

Low-confidence estimates must be marked low confidence.

---

### Lifestyle / Autonomy

Consider explicit information such as:

- remote/hybrid;
- working hours;
- travel;
- shifts;
- work-location constraints.

Do not invent workplace culture from vacancy prose.

---

## 17. Score Representation

Each dimension must contain:

```text
score
confidence
reason
evidence
```

Suggested score:

```text
0–10
```

Suggested confidence:

```text
LOW
MEDIUM
HIGH
```

Example:

```json
{
  "functional_fit": {
    "score": 8.7,
    "confidence": "HIGH",
    "reason": "The role strongly combines business analytics, stakeholder consulting and AI-enabled transformation.",
    "evidence": [
      "consult directly with international clients",
      "generate deep insights",
      "champion AI innovation"
    ]
  }
}
```

Evidence should quote minimally or reference extracted job requirements without reproducing excessive source text.

---

## 18. Strengths, Gaps, and Risks

Every semantic assessment should separately produce:

```text
strengths
gaps
risks
```

### Strength

Candidate capability positively supporting the application.

Example:

```text
Strong executive stakeholder and decision-support experience.
```

### Gap

Missing or underdeveloped capability relative to the role.

Example:

```text
Limited practical Airflow/dbt experience.
```

### Risk

Something that may materially affect desirability or conversion but is not simply a capability gap.

Example:

```text
Role may be substantially more hands-on technical than its consulting language suggests.
```

Do not merge these categories.

---

## 19. Composite Opportunity Score

The composite is calculated deterministically from persisted dimension scores.

Suggested initial weights:

```text
Functional fit                 20%
Existing experience leverage   15%
AI / future alignment          15%
Learning opportunity         12.5%
Long-term strategic value    12.5%
Conversion probability         10%
Seniority fit                   5%
Employer / career value         5%
Compensation potential        2.5%
Lifestyle / autonomy          2.5%
```

Weights are hypotheses, not permanent truth.

They must live in configuration rather than code.

Example:

```text
config/scoring.yaml
```

Changing weights should permit recomputation of composite scores without rerunning semantic assessment.

---

## 20. Strategic Weighting

Candidate strategic priorities may affect composite weighting.

However:

- CandidateProfile expresses importance/preferences.
- Scoring configuration determines how those importance levels map to weights.

Do not hide arbitrary dynamic weighting rules inside semantic prompts.

Phase 3 may initially use one explicit scoring configuration optimized for the first candidate.

Architecture must support other configurations later.

---

## 21. OpportunityAssessment

Suggested conceptual model:

```text
OpportunityAssessment
├── assessment_id
├── job_instance_id
├── candidate_profile_id
├── candidate_profile_version
├── assessed_at
├── eligibility
├── deterministic_features
├── triage_score
├── dimension_scores
├── strengths
├── gaps
├── risks
├── composite_score
├── recommendation
└── model/scoring metadata
```

Recommended decision labels:

```text
HIGH_PRIORITY
APPLY
REVIEW
STRETCH
LOW_PRIORITY
REJECTED
```

These labels are derived from scores/rules and must remain configurable.

---

## 22. Assessment Persistence

Phase 3 assessments should be persisted separately from job observations and lifecycle state.

A job is a fact about the market.

An assessment is candidate-specific interpretation.

Therefore:

```text
JobInstance
      ↓
OpportunityAssessment(candidate_profile_version)
```

The same job may later support multiple candidate profiles or multiple profile versions.

Do not add candidate-specific fields to `job_instances`.

---

## 23. Reassessment

Do not automatically rerun semantic assessment every ingestion cycle.

A reassessment may be triggered when:

- a job materially changes;
- the CandidateProfile version changes;
- scoring logic/model version changes;
- assessment is missing.

Simple cache/reuse behavior is sufficient for Phase 3.

---

## 24. LLM Boundary

The semantic model receives:

- normalized job content;
- structured CandidateProfile;
- dimension definitions;
- output schema.

It must not receive responsibility for:

- eligibility rules that can be evaluated deterministically;
- composite weight calculation;
- persistence;
- job identity;
- lifecycle inference.

The LLM provides structured interpretation.

Application code provides deterministic control.

---

## 25. Model Metadata

Every semantic assessment should record enough metadata to understand how it was created.

Suggested:

```text
provider
model
prompt/schema version
assessment version
created_at
```

Do not rely on exact reproducibility of probabilistic output.

Instead preserve the result and version its inputs.

---

## 26. EmployerProfile — Deferred but Reserved

Some opportunity dimensions are employer-level rather than job-level.

Future structure may contain:

```text
EmployerProfile
├── company_id
├── employee_reputation
├── financial_strength
├── compensation_reputation
├── equity_availability
├── AI_strategy
├── career_option_value
└── evidence/confidence
```

Do not build web employer research automation in Phase 3 unless necessary for basic scoring.

Initially:

- employer dimensions may be null;
- manually configured;
- or conservatively derived from known structured data.

Do not repeatedly ask the semantic job scorer to rediscover generic employer facts.

---

## 27. Future Capability — Learning Intelligence

Not part of Phase 3 implementation.

The architecture should preserve the data required for future analysis of repeated capability gaps across opportunity history.

Future objective:

> Expected career leverage per unit of learning effort.

Conceptually:

```text
OpportunityAssessment history
        ↓
Repeated strengths / gaps
        ↓
Opportunity quality × gap frequency
        ↓
Estimated learning effort
        ↓
Learning priorities
```

Future system question:

> What is the market telling the candidate about who they should become?

Phase 3 should therefore preserve structured `gaps`, dimension scores, candidate-profile versions, and opportunity history.

Do not implement course recommendations or learning-path generation now.

---

## 28. Offline Evaluation Dataset

Before trusting the scorer, create a small benchmark dataset from previously evaluated opportunities.

Use historical opportunities where a human judgment already exists.

Suggested examples:

- MSD AI Product Analyst
- J&J Senior Pricing Analyst
- Siemens Data/AI role
- BCG Associate
- Mastercard Econometrics
- IDC Wearables
- Wrike Strategy & Operations
- Novartis Platform Services
- Deutsche Börse Strategy AI Analyst
- WPP Automation & AI

For each benchmark opportunity record:

- expected broad ranking;
- known strengths;
- known gaps;
- major risks;
- whether opportunity was considered worth applying to.

Do not require exact reproduction of historic numerical scores.

The scorer should reproduce the broad reasoning and ordering.

---

## 29. Evaluation Criteria

Phase 3 should be considered successful if:

1. hard eligibility filters reject only clearly incompatible vacancies;
2. relevant historical opportunities survive deterministic triage;
3. semantic scoring produces structured valid output;
4. strengths, gaps, and risks are meaningfully separated;
5. dimension scores remain individually persisted;
6. composite recalculation works without semantic rescoring;
7. benchmark ranking broadly matches human historical judgment;
8. noisy job titles do not prevent strong semantic matches;
9. low-confidence dimensions remain explicitly low confidence;
10. CandidateProfile can be replaced without changing scoring-engine code.

---

## 30. Failure Criteria

Reconsider the architecture if:

- candidate-specific logic leaks throughout application code;
- hard filters remove historically desirable opportunities;
- semantic scoring depends excessively on job title;
- composite scores cannot be explained from dimensions;
- small wording changes produce wildly unstable rankings;
- assessments require repeated LLM calls when underlying job/profile has not changed;
- scoring cannot support a second hypothetical candidate without code changes.

---

## 31. Phase 3 Non-Goals

Do not implement:

- automatic CV tailoring;
- automated applications;
- job-board UI;
- email/Slack notifications;
- daily scheduling;
- web employer-reputation research pipeline;
- learning-path recommendations;
- rejection prediction from historical applicant data;
- probabilistic duplicate/repost logic;
- multi-user authentication;
- SaaS billing;
- cloud deployment.

---

## 32. Phase 3 Deliverables

At completion provide:

1. CandidateProfile schema;
2. candidate configuration loader;
3. eligibility filter;
4. deterministic feature extraction;
5. configurable triage scoring;
6. semantic assessment interface;
7. structured dimension-score schema;
8. strengths/gaps/risks extraction;
9. configurable composite calculator;
10. OpportunityAssessment persistence;
11. benchmark evaluation dataset;
12. benchmark report;
13. sample ranked opportunity output;
14. tests;
15. documented architecture corrections;
16. recommendation:

```text
GO
CONDITIONAL GO
NO-GO
```

for the relevance/scoring architecture.

---

## 33. Guiding Product Principle

> The system should not decide for the candidate.

Its purpose is to compress the market into a small number of explainable decisions worth human attention.

A high-quality result is not:

> "This job scores 8.7."

A high-quality result is:

> "This job deserves attention because it strongly leverages existing capabilities, accelerates the candidate's AI trajectory, has two manageable technical gaps, and has a moderate conversion risk caused by seniority mismatch."

## 34. Architecture Decisions After Review

The Phase 3 architecture review identified several areas where the initial specification created unnecessary precision, overlapping dimensions, or excessive risk of false-negative filtering.

The following decisions supersede conflicting Phase 3 assumptions above.

### 34.1 Phase 3 Objective

Phase 3 should answer:

> Which active opportunities deserve this candidate's attention, and why?

The architecture should optimize first for **recall, explainability, and portability across candidates**.

Optimization of model cost, precision of composite scores, and processing volume is secondary until benchmark evidence exists.

---

### 34.2 Candidate-Specific Information Is Configuration

Candidate-specific facts, preferences, constraints, and strategic direction must exist as structured data.

The scoring engine must not contain candidate-specific Python logic.

The same scoring implementation must support a materially different candidate by replacing configuration only.

The initial runtime profile should live in:

```text
config/candidate.yaml
```

Future profile-generation mechanisms such as:

- onboarding forms;
- CV parsing;
- conversational setup;
- imported professional profiles;
- user settings;

must compile into the same internal `CandidateProfile` representation.

They must not define alternative scoring architectures.

---

### 34.3 CandidateProfile Conceptual Separation

Candidate information should distinguish:

#### Candidate facts

Examples:

- residence;
- work authorization;
- language proficiency;
- career experience;
- management scope;
- domains worked in.

#### Capabilities

What the candidate can currently do and at what level.

#### Preferences

What kinds of work, sectors, and environments the candidate finds more desirable.

Preferences influence ranking but do not imply rejection.

#### Hard constraints

Explicit conditions that genuinely make an opportunity unacceptable or inaccessible.

#### Strategic goals

The direction in which the candidate wants their career and capabilities to evolve.

#### Scoring preferences

How strongly different assessment dimensions influence ranking.

Scoring preferences must remain separable from semantic candidate facts so weight-only changes do not require semantic reassessment.

---

### 34.4 Capability Representation

Capabilities must use stable controlled `capability_id` values.

Suggested structure:

```yaml
capabilities:
  - capability_id: business_analytics
    level: expert
    confidence: high
    evidence:
      - source: candidate_assertion
```

Initial controlled level vocabulary:

```text
NONE
BASIC
DEVELOPING
INTERMEDIATE
ADVANCED
EXPERT
```

Initial confidence vocabulary:

```text
LOW
MEDIUM
HIGH
```

Capability evidence may remain lightweight in Phase 3, but the schema should reserve it for future profile generation and validation.

Stable capability IDs must also be reused by:

- deterministic job features;
- strengths;
- gaps;
- semantic evidence.

This is important for future aggregate capability-gap analysis.

#### UNKNOWN, NONE, and omitted capabilities

An omitted capability means `UNKNOWN`: the profile contains no explicit
assessment of that capability. Omission must never be interpreted as evidence
that the candidate has no capability.

`NONE` is an explicit assessed level. It may be used only when the profile
deliberately asserts that the candidate does not currently possess the
capability. `UNKNOWN` and `NONE` are therefore semantically distinct.

#### Shared taxonomy

Controlled IDs used by candidate profiles, deterministic features, benchmark
strengths/gaps, and benchmark risks are registered in:

```text
config/taxonomy.yaml
```

The taxonomy distinguishes descriptive kinds such as `CAPABILITY`, `DOMAIN`,
`EXPERIENCE`, `CREDENTIAL`, `ROLE_CHARACTERISTIC`, `RISK`, and `COMPOSITE`.
An ID may belong to more than one kind where the same stable concept is used in
multiple contexts. Lightweight parent/support/equivalence relationships may
clarify broad concepts, but they must not create automatic scoring behavior or
become a general ontology engine.

#### Domain-depth vocabulary

Candidate experience domains use one controlled depth vocabulary:

```text
LIMITED
MODERATE
DEEP
```

Domain depth describes experience context and must not reuse capability-level
terms such as `DEVELOPING`.

---

### 34.5 Hard Eligibility

Eligibility returns:

```text
ELIGIBLE
INELIGIBLE
UNCERTAIN
```

The rule:

> UNKNOWN != INELIGIBLE

must be enforced in both code and tests.

Hard rejection requires:

1. explicit source evidence;
2. a relevant explicit candidate fact or hard constraint;
3. deterministic incompatibility.

Initial hard-rejection categories are limited to:

- explicit incompatible geography or work-location requirement;
- explicit mandatory language requirement not met;
- explicit work-authorization incompatibility where candidate authorization facts are known;
- explicit mandatory relocation when the candidate prohibits relocation.

Do not hard reject based on:

- seniority mismatch;
- years-of-experience requirements;
- degree requirements;
- skill gaps;
- industry unfamiliarity;
- compensation uncertainty;
- unusual career history;
- employer quality;
- role-family classification unless future evidence demonstrates sufficiently reliable deterministic classification.

Excluded or undesirable role families should initially influence triage/ranking rather than eligibility.

---

### 34.6 Deterministic Features Must Be Neutral

Deterministic extraction records what evidence exists in the job.

It should not decide whether a feature is good or bad for a particular candidate.

Prefer:

```text
software_engineering_intensity
quota_sales_responsibility
people_management_scope
pricing_strategy
business_analytics
ai_enabled_work
```

rather than:

```text
bad_software_engineering_match
good_ai_match
```

Feature evidence should retain:

```text
concept_id
matched_text
source_field
match_rule_version
```

CandidateProfile and scoring logic interpret the feature later.

---

### 34.7 Triage Is Rank-Only Initially

Deterministic triage must not exclude otherwise eligible jobs during the Phase 3 experiment.

Its initial purposes are:

- processing order;
- diagnostic evidence;
- eventual model-cost control.

All benchmark jobs receive semantic assessment regardless of triage score.

A semantic-processing threshold may be introduced only after measured benchmark recall demonstrates that valuable opportunities are not being lost.

False-negative cost is considered substantially greater than false-positive semantic-processing cost.

---

### 34.8 Core Semantic Dimensions

The initial semantic model uses six core dimensions.

#### Functional Alignment

How closely the actual responsibilities and nature of the work align with what the candidate can and wants to do.

#### Experience Leverage

How strongly the role benefits from accumulated professional expertise, transferable experience, and previously demonstrated capabilities.

#### Learning / Growth Value

How much valuable capability development the role is likely to create.

A capability gap may reduce immediate alignment while increasing learning value.

#### Strategic Alignment

How strongly the role advances the candidate's explicitly configured long-term career direction.

This replaces candidate-specific dimensions such as `AI Future Alignment`.

For the initial candidate, AI-enabled work and Decision Intelligence may be strategically important.

Another candidate may have completely different strategic goals without requiring scoring-engine changes.

#### Seniority Alignment

How well the role's responsibility, organizational scope, and level align with the candidate's professional seniority.

Down-level and over-level situations may both reduce alignment.

#### Application Competitiveness

How credible the candidate appears against the explicitly stated requirements and transferable requirements of the vacancy.

This replaces `conversion_probability`.

It is not a statistical probability of interview or hire.

The system does not possess sufficient evidence about applicant pools, recruiter behavior, employer funnel rates, hiring politics, or referrals to estimate real hiring probability.

---

### 34.9 Deferred / Optional Dimensions

The following are not initial core composite dimensions:

- employer/career value;
- compensation potential;
- lifestyle/autonomy.

These may be stored as supplemental assessments when supported by evidence.

They must remain null when evidence is insufficient.

Do not invent:

- employer quality from generic branding language;
- compensation from title alone;
- autonomy or workplace culture from ordinary job-description prose.

A future `EmployerProfile` may provide reusable employer-level evidence.

---

### 34.10 Semantic Score Scale

Semantic dimensions use an anchored integer scale:

```text
1 = strongly misaligned / poor
2 = weak
3 = mixed / moderate
4 = strong
5 = exceptional
```

Each dimension should have its own behavioral rubric explaining what 1–5 means in that context.

The semantic assessor must not output pseudo-precise scores such as:

```text
8.7
```

The purpose of the semantic score is ordinal comparison and structured interpretation, not measurement precision.

---

### 34.11 Dimension Representation

Each semantic dimension contains:

```text
score
confidence
reason
job_evidence
candidate_evidence
```

`score` may be null if available evidence cannot support the dimension.

Confidence represents strength of supporting evidence, not subjective model certainty.

Use:

```text
LOW
MEDIUM
HIGH
```

Unknown or unsupported information must remain null rather than being converted to a low score.

---

### 34.12 Strengths, Gaps, and Risks

These remain separate concepts.

#### Strength

Candidate evidence supporting performance or candidacy.

#### Gap

Missing or underdeveloped candidate capability relative to job demand.

#### Risk

A material concern that is not simply a capability deficiency.

Examples:

- ambiguous role scope;
- substantial down-leveling;
- unusually high technical intensity;
- mandatory travel;
- unclear deployment authority.

Strengths and gaps should use stable concept identifiers shared with `CandidateProfile`.

Suggested structure:

```json
{
  "kind": "gap",
  "concept_id": "sql",
  "statement": "Role expects deeper practical SQL capability than currently demonstrated.",
  "importance": "HIGH",
  "confidence": "HIGH",
  "job_evidence": [],
  "candidate_evidence": []
}
```

Risks may use controlled risk categories plus explanatory text.

This structure should preserve future compatibility with:

- CV tailoring;
- interview preparation;
- aggregate capability-gap analysis;
- Learning Intelligence.

Those features remain out of scope.

---

### 34.13 Initial Composite Dimensions and Weights

The Phase 3 experiment uses only the six core dimensions:

```text
Functional Alignment          25%
Experience Leverage           15%
Learning / Growth Value       15%
Strategic Alignment           20%
Seniority Alignment           10%
Application Competitiveness   15%
```

These weights are hypotheses.

They are not considered optimized or permanent.

Weights must live in scoring configuration rather than Python code.

Changing weights must not require semantic reassessment.

---

### 34.14 Missing Core Dimensions

Missing does not equal zero.

For the initial experiment, a normal composite score requires all six core semantic dimensions.

If a core dimension cannot be supported:

```text
recommendation = REVIEW
```

and the assessment must explicitly identify the missing evidence.

Future versions may introduce defensible renormalization policies if real observations justify them.

Do not implement sophisticated missing-data weighting during the Phase 3 spike.

---

### 34.15 Composite Calculation

Semantic scores remain on the 1–5 scale.

The weighted composite is calculated deterministically.

It may be converted for presentation to a 0–10 RADAR scale.

Conceptually:

```text
semantic dimension scores
        ↓
weighted deterministic mean
        ↓
presentation conversion
        ↓
RADAR composite 0–10
```

Confidence must remain separate from arithmetic.

Do not multiply scores by arbitrary confidence factors.

Composite output should include:

```text
composite_score
core_dimension_coverage
assessment_confidence
```

---

### 34.16 Candidate Profile Fingerprints

Each immutable candidate-profile version should contain:

```text
profile_id
version
created_at
full_profile_fingerprint
semantic_profile_fingerprint
scoring_preference_fingerprint
```

The `semantic_profile_fingerprint` changes when information relevant to semantic interpretation changes.

Examples:

- capability level;
- experience;
- preferences relevant to role interpretation;
- strategic goals.

The `scoring_preference_fingerprint` changes when only weighting/prioritization changes.

Example:

```text
Strategic Alignment weight:
20% → 30%
```

should not invalidate the existing semantic assessment.

Instead:

```text
semantic assessment reused
+
composite recalculated
```

---

### 34.17 Semantic Assessment Reuse

A semantic assessment may be reused when all relevant semantic inputs remain unchanged:

```text
same job_instance_id
same material job fingerprint
same semantic-profile fingerprint
same semantic contract version
same prompt/schema version
same provider/model configuration
```

A new identical Phase 2 observation does not require semantic reassessment.

Reassessment is required when semantic meaning may have changed.

Changing only:

- composite weights;
- recommendation thresholds;
- ranking configuration;

must not trigger a semantic call.

Historical assessments must be preserved rather than deleted.

---

### 34.18 Recommendation Labels

Use a deliberately small initial recommendation set:

```text
APPLY
REVIEW
LOW_PRIORITY
INELIGIBLE
```

`STRETCH` should initially be represented as an explanatory flag or risk pattern rather than a separate terminal recommendation.

Recommendation labels are derived deterministically.

The semantic model does not decide the final recommendation.

---

### 34.19 Employer, Compensation, and Lifestyle Evidence

Employer reputation, financial strength, compensation, equity, and lifestyle attributes are potentially important but require evidence external to most job descriptions.

Do not repeatedly ask the job semantic scorer to rediscover generic company information.

Reserve a future:

```text
EmployerProfile
```

architecture.

For Phase 3 these factors may be:

- manually configured;
- absent;
- supplemental;
- explicitly low-confidence.

They are not required for the core composite.

---

### 34.20 Future Learning Intelligence Compatibility

Phase 3 must preserve structured data sufficient for future analysis of recurring capability gaps.

Required foundations are:

- stable capability IDs;
- structured candidate capability levels;
- structured job requirements/features;
- structured strengths and gaps;
- gap importance;
- assessment scores;
- candidate-profile versions;
- job and observation identity.

Future objective:

> Expected career leverage per unit of learning effort.

Future product question:

> What is the market telling the candidate about who they should become?

Do not implement:

- learning paths;
- course recommendations;
- learning-effort estimates;
- capability graphs;
- career-leverage optimization;

during Phase 3.

---

### 34.21 Benchmark Philosophy

Phase 3 requires an offline human-judgment benchmark before implementation is considered validated.

The benchmark is not a statistical training dataset.

Its purposes are:

- prevent obvious false rejection;
- measure triage recall;
- test misleading job titles;
- test strengths/gaps/risks extraction;
- validate broad relative ranking;
- test portability to another candidate.

Prefer:

- ranking tiers;
- selected pairwise comparisons;
- broad human decisions;

over exact historical numerical scores.

Do not optimize decimal weights against a small benchmark.

Reserve some benchmark examples from iterative tuning where practical.

---

### 34.22 Second-Candidate Portability Test

Phase 3 must include at least one deliberately different hypothetical candidate.

The same:

- CandidateProfile schema;
- eligibility implementation;
- deterministic feature extraction;
- semantic contract;
- scoring implementation;

must work without Python changes.

Only candidate and scoring configuration may differ.

If supporting another candidate requires candidate-specific branches, Phase 3 portability has failed.

---

### 34.23 Phase 3 Experimental Sequence

Implementation should proceed in this order:

1. define CandidateProfile schema;
2. create initial candidate profile;
3. create second hypothetical candidate;
4. assemble immutable benchmark job fixtures;
5. record human benchmark judgments;
6. implement profile validation/fingerprinting;
7. implement deterministic eligibility;
8. implement neutral feature extraction;
9. implement rank-only triage;
10. benchmark eligibility and triage recall;
11. define semantic rubrics and strict structured contract;
12. validate downstream architecture using fake semantic assessments;
13. implement minimal persistence and semantic caching;
14. validate deterministic composite/recommendation behavior;
15. only then integrate one external semantic model;
16. compare semantic output with benchmark human judgment.

Do not skip directly to external LLM integration.

---

### 34.24 BenchmarkJobFixture

Historical benchmark job fixtures are immutable evidence artifacts used for
Phase 3 evaluation. They are not live ingestion records and are therefore not
required to satisfy the complete `NormalizedJob` contract.

`NormalizedJob` represents a successfully normalized vacancy produced by
Phase 1 and includes operational/source fields required by the live ingestion
pipeline.

`BenchmarkJobFixture` represents preserved historical job evidence. Historical
source identity and operational metadata may legitimately be unavailable and
must not be invented merely to satisfy the live model.

#### Required semantic evidence

A benchmark fixture should contain the semantic job evidence required for
Phase 3 assessment:

- `company_name`
- `title`, except where explicitly unavailable in a historical fixture
- `description`
- `locations`
- `work_mode`

A fixture with an unavailable title may remain benchmark-eligible only when
its completeness metadata explicitly records that limitation.

#### Optional historical/source evidence

The following fields may be null or absent where the historical source does
not support them:

- `external_job_id`
- `canonical_url`
- `date_posted`
- `valid_through`
- `employment_type`
- `department`

Missing historical values must remain unknown. Synthetic values, placeholder
URLs, reconstructed IDs, or other invented operational metadata must not be
introduced merely to satisfy `NormalizedJob`.

#### Supplemental evidence

A benchmark fixture may contain versioned supplemental evidence that is useful
for evaluation but is not currently represented by `NormalizedJob`, for
example:

- compensation;
- explicitly stated travel requirements;
- other preserved vacancy facts.

Supplemental evidence must remain distinguishable from the core semantic job
evidence.

#### Work-mode vocabulary

Benchmark fixtures use the serialized `WorkMode` values used by the existing
normalized model:

- `onsite`
- `hybrid`
- `remote`
- `unspecified`

#### Source completeness

Every benchmark fixture must declare `source_completeness`.

Initial supported values are:

- `FULL` — the historical vacancy evidence required by the benchmark is
  preserved without a known material omission.
- `DESCRIPTION_COMPLETE_TITLE_UNKNOWN` — the substantive vacancy description
  is preserved but the exact historical title cannot be established.

`strict_benchmark_eligible` is independent of source completeness. A fixture
with a documented historical limitation may remain strict-eligible when that
missing field is not material to the assertion being tested.

#### Phase 3 boundary

Phase 3 must not construct a live `NormalizedJob` merely to evaluate a
historical benchmark fixture.

The benchmark loader maps `BenchmarkJobFixture` into the same semantic job
input contract consumed by Phase 3 assessment.

This preserves the boundary:

Live vacancy:
`Adapter → NormalizedJob → Phase 2 state → Phase 3 semantic input`

Historical benchmark:
`BenchmarkJobFixture → Phase 3 semantic input`

The two paths converge at the Phase 3 semantic-input boundary rather than at
the Phase 1 normalized-ingestion model.

---

### 34.25 Phase 3 Success Criteria

#### Required synthetic controls

The deterministic offline test suite must include these synthetic cases rather
than adding them to the frozen historical benchmark:

1. **Explicit incompatibility:** source evidence and an explicit candidate hard
   constraint establish a genuine incompatibility. Expected eligibility is
   `INELIGIBLE` with the source and candidate evidence preserved.
2. **Missing core dimension:** one core semantic dimension is unsupported.
   The dimension remains null, no complete composite is invented, and the
   deterministic recommendation is `REVIEW` with missing evidence identified.

Phase 3 passes if:

1. no historically desirable benchmark opportunity is deterministically rejected;
2. missing eligibility evidence never becomes `INELIGIBLE`;
3. triage retains 100% of benchmark `APPLY` opportunities at the tested processing budget;
4. misleading-title benchmark jobs survive triage;
5. a second candidate works without Python changes;
6. semantic outputs validate against the strict schema;
7. unsupported dimensions remain null rather than invented;
8. strengths, gaps, and risks remain meaningfully distinct;
9. broad benchmark ranking agrees with human judgment;
10. composite calculations are exactly reproducible;
11. weight-only changes produce zero semantic reassessments;
12. unchanged job/profile/model contracts reuse semantic assessments;
13. material semantic-input changes invalidate cached assessments;
14. Phase 1 and Phase 2 continue passing unchanged;
15. candidate-specific logic does not leak into adapters, job identity, or market state.
