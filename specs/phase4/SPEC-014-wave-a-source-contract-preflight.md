# SPEC-014 — Wave A Zero-Detail Source-Contract Preflight

## Status

`APPROVED_FOR_IMPLEMENTATION`

## Purpose

Evaluate the nine SPEC-013 Wave A employers as candidate Opportunity Radar sources **without onboarding them into production** and without retrieving job-detail pages.

The goal is not to prove that a careers site is scrapeable. The goal is to decide whether each source is likely to add **marginal useful market coverage** at acceptable operating cost while preserving Phase 1/2 contracts.

Wave A candidates from frozen SPEC-013 evidence:

- Keboola
- Mews
- Productboard
- Commerzbank
- Erste Group
- ABB
- KPMG
- MSD
- Zentiva

Primary question:

> Which of these employers should earn a production-onboarding experiment because they materially improve employer breadth and target-role coverage for the current candidate while fitting an existing source contract with acceptable operational burden?

Secondary question:

> Which sources fail because of technical/source-contract problems versus simply having low marginal opportunity value?

## Context

Read before implementation:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING_MODEL.md`
- `docs/source_portfolio_and_role_coverage_report.md`
- `experiments/source_portfolio_audit_v1.yaml`
- SPEC-013
- current adapter contracts and tests
- current `config/companies.yaml`

Preserve SPEC-013 as immutable evidence. Do not silently change its Wave A list during this packet.

## Authority boundary

This packet authorizes:

- bounded public listing/index calls for the nine Wave A candidate employers;
- source-contract discovery sufficient to identify ATS/provider/tenant/configuration;
- zero-detail inventory/listing preflight;
- bounded pagination verification;
- listing-level geography/work-mode/title/URL/date/category inspection;
- generic target-role-family signal analysis using the frozen SPEC-013 classifier contract or an explicitly versioned read-only derivative;
- source-operability scoring;
- repository-safe aggregate evidence and private detailed evidence;
- code/tests/docs required to run the preflight.

This packet does **not** authorize:

- adding employers to production `config/companies.yaml`;
- writing to Phase 2 operational SQLite;
- fetching job detail pages as part of the preflight;
- semantic-model calls;
- changing candidate configuration/preferences;
- changing market policy;
- changing existing adapters to make a candidate pass unless a generic source-contract defect is discovered and separately reported;
- implementing Ashby/SmartRecruiters or any new provider adapter;
- full live refresh of existing employers;
- application/external action.

If zero-detail viability cannot be established without detail calls, mark the limitation and stop rather than weakening the experiment.

## Why zero-detail

SPEC-013 showed that raw inventory volume is a poor proxy for useful coverage. Before onboarding a source, Opportunity Radar should know whether listing-level evidence is sufficient to justify the operating cost of full detail retrieval.

The preflight therefore asks:

```text
PUBLIC SOURCE SURFACE
      ↓
provider / tenant / source contract
      ↓
complete or bounded listing inventory
      ↓
listing evidence quality
      ↓
target-role signal + market signal
      ↓
projected detail burden
      ↓
marginal source value
      ↓
GO / CONDITIONAL / NO-GO
```

## Source onboarding scorecard

Produce one comparable scorecard row per employer.

Required dimensions:

1. **Provider/source type**
   - Greenhouse / Workday / SuccessFactors / AlmaCareer / Generic HTML / other;
   - endpoint/tenant evidence;
   - whether an existing adapter appears reusable without code changes.

2. **Inventory confidence**
   - estimated total listing count;
   - pages/requests required;
   - pagination termination evidence;
   - duplicate identity behavior;
   - whether inventory completeness can be established under existing Phase 1 rules.

3. **Listing evidence quality**
   - title coverage;
   - canonical URL coverage;
   - location coverage;
   - work-mode coverage;
   - date-posted/update coverage where available;
   - department/category/employment-type coverage where available.

4. **Market usefulness**
   - obvious Prague/Czech listing count where identifiable;
   - obvious compatible-remote listing count where identifiable;
   - obvious foreign-only listing count;
   - unknown-market share;
   - do not reinterpret listing scope as final candidate eligibility.

5. **Target-role signal**
   Using the frozen/spec-derived role-family lens, report listing-level counts for at least:
   - business/data analytics;
   - decision support/intelligence;
   - strategy & operations;
   - business/commercial operations;
   - product strategy/product management;
   - AI transformation/automation/adoption;
   - revenue/pricing/growth/retention analytics;
   - clearly unrelated high-volume families when useful for denominator context.

   Count both explicit title-supported evidence and broader adjacent terminology where listing text permits, but do not use job-detail descriptions.

6. **Projected detail burden**
   - inventory size;
   - estimated listings likely to survive current retrieval-scope policy where listing evidence allows simulation;
   - projected detail requests if onboarded;
   - expected zero-network-detail advantages where the source embeds full descriptions in listing/API responses;
   - uncertainty if detail selection cannot be simulated safely.

7. **Diversification value**
   Assess whether the employer adds a business model / sector / employer type materially underrepresented in the current 18-employer portfolio.

8. **Operational risk**
   - anti-bot/rate-limit concerns;
   - unstable selectors/contracts;
   - provider behavior inconsistent with existing adapter assumptions;
   - inaccessible geography;
   - opaque pagination;
   - source likely to require custom code.

9. **Recommendation**
   Controlled verdict:

```text
GO_CONFIGURATION_ONLY
GO_BOUNDED_ADAPTER_FIX
CONDITIONAL_SOURCE_INVESTIGATION
NO_GO_LOW_MARGINAL_VALUE
NO_GO_SOURCE_CONTRACT
```

`GO_BOUNDED_ADAPTER_FIX` is diagnostic only in this packet; do not implement the fix unless it is a generic regression in an already-supported provider contract and separately approved.

## Market-usefulness principle

Do not favor an employer merely because it has many jobs.

The relevant value is closer to:

```text
marginal useful market coverage
= accessible + relevant + evidence-rich + diversifying opportunities
```

rather than:

```text
raw listing count
```

Do not invent a universal numeric formula unless the evidence clearly supports one. A transparent ordinal scorecard is preferable to false precision.

## Candidate-role direction to preserve

The preflight should treat the following as high-value opportunity families because SPEC-013 confirmed they are both underrepresented and compatible with existing candidate capability:

- business analytics;
- decision support / decision intelligence;
- business-facing data analytics;
- strategy & operations;
- commercial/business operations;
- AI transformation / AI adoption / automation;
- product/business strategy;
- pricing/revenue/retention analytics.

Do not equate this with generic data administration, generic reporting operations, payroll, accounting, HR data maintenance, or deep software/data-engineering roles.

Hard-skill gaps remain real. Source discovery should improve the market observed, not pretend the candidate qualifies for every adjacent title.

## Existing-adapter reuse validation

For each candidate claiming configuration-only reuse, prove the expected adapter contract against the public source surface.

At minimum verify:

- source endpoint is reachable;
- listing identity can be derived stably;
- title and canonical URL can be normalized;
- pagination can be bounded/completed;
- source does not require employer-specific branching in generic adapter code;
- the configuration can plausibly live entirely in a candidate preflight config separate from production.

Do not mutate production config.

## Preflight configuration

Create a dedicated experiment/preflight configuration containing the nine Wave A sources.

It must not be loaded by normal production commands.

Suggested shape:

```text
experiments/wave_a_source_preflight_v1.yaml
```

The configuration should preserve source URLs/provider evidence and any candidate selectors/tenant metadata needed for the bounded preflight.

## Call budget

This is a bounded public-source experiment.

Requirements:

- no job-detail retrieval;
- no semantic calls;
- do not crawl arbitrary site content;
- use provider listing APIs/indexes where available;
- record request counts per source;
- stop if pagination behavior exceeds a predeclared safety bound;
- do not repeatedly retry a clearly incompatible source contract.

Set conservative safety limits in experiment configuration and report when reached.

## Private vs repository-safe evidence

Private/local evidence may contain:

- individual job titles;
- listing URLs;
- source response snippets;
- selector/provider diagnostics;
- per-listing target-role classifications.

Repository-safe aggregate evidence may contain:

- employer names;
- public careers/source URLs;
- provider/adapter family;
- aggregate counts/coverage;
- request counts;
- scorecard verdicts;
- target-family aggregate counts;
- market-coverage aggregates;
- projected detail burden;
- limitations/conclusions;
- hashes/fingerprints.

No candidate name or private human notes in repository-safe output.

## Required analyses

### A. Technical source viability

For all nine candidates classify whether the source can be handled by an existing adapter without runtime code changes.

### B. Listing-level usefulness

Estimate whether each source contributes meaningful Prague/Czech/compatible-remote opportunity supply and target-role-family breadth.

### C. Employer diversification

Explain what each employer adds to the current portfolio beyond vacancy count, for example:

- Czech-native data/AI platform;
- hospitality SaaS/product company;
- product-management SaaS;
- banking/financial services;
- industrial technology;
- professional services;
- pharma/healthcare.

### D. Detail-cost projection

Estimate operational detail burden under current scope-selection logic where safe.

### E. Onboarding shortlist

Do not mechanically approve all technically viable sources.

Produce:

```text
FIRST ONBOARDING WAVE
best marginal value + technically ready

SECONDARY CANDIDATES
viable but lower marginal value or higher burden

DO NOT ONBOARD YET
source-contract or value concerns
```

Aim for a first wave of roughly 3–5 employers if evidence supports it. This is guidance, not a quota.

## Success criteria

The packet succeeds if it can answer:

1. Which Wave A sources fit an existing adapter contract?
2. Which materially improve employer breadth?
3. Which materially improve analytics/decision-support/AI-transformation role coverage?
4. Which provide useful market evidence at listing level?
5. Which would create disproportionate detail burden?
6. Which 3–5 employers should enter the first bounded production-onboarding experiment?

It is acceptable for the result to recommend fewer than three if evidence is weak.

## Validation

Required:

```bash
.venv/bin/pytest -q
git diff --check
```

Also prove:

- production `config/companies.yaml` unchanged;
- operational SQLite byte-identical before/after;
- Phase 2 rows/events unchanged;
- semantic calls: 0;
- detail-page calls: 0;
- existing employer state untouched;
- source request counts bounded and reported;
- repository-safe aggregate contains no private candidate/human evidence.

## Experiment registry / project memory

After implementation:

- register the experiment in `experiments/registry.yaml`;
- update `docs/STATUS.md` with actual preflight findings only;
- update `docs/source_portfolio_and_role_coverage_report.md` or create a dedicated Wave A preflight report if that improves provenance;
- do not mark any new employer as production-onboarded.

## Deliverable

Return:

A. files changed
B. experiment/run identity and commands
C. public-source request counts and safety limits
D. nine-employer source/provider map
E. adapter-reuse result per employer
F. inventory and listing-evidence quality per employer
G. market-usefulness aggregates per employer
H. target-role-family signal per employer
I. projected detail burden per employer
J. diversification contribution
K. operational/source-contract risks
L. normalized onboarding scorecard
M. recommended first onboarding wave
N. secondary / no-go candidates and why
O. privacy/integrity confirmation
P. validation result
Q. smallest next packet
R. recommended commit message

Do not commit/push implementation until the normal approval boundary.
