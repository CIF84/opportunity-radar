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