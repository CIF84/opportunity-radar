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