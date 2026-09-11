# SPEC-013 — Source Portfolio and Role-Coverage Audit

## Status

`IMPLEMENTED_LOCALLY_AWAITING_REVIEW`

## Purpose

Audit whether Opportunity Radar's current employer intake portfolio is broad and
relevant enough for the candidate's actual career search, with particular focus
on an observed underrepresentation of business/data/decision-analytics roles and
an observed concentration of opportunities in a small number of employers.

This packet must answer two separate questions:

1. **Role coverage:** are potentially attractive career families present in the
   intake at the frequency we would reasonably expect, or is the source portfolio
   structurally missing them?
2. **Employer breadth:** is the current 18-employer portfolio too concentrated
   to provide a useful market view even though absolute vacancy volume is high?

Do not confuse vacancy volume with market coverage. A source portfolio that
produces thousands of jobs from a few employers can still provide a narrow view
of the candidate's opportunity market.

This is an intake/source-portfolio experiment, not a semantic-ranking experiment.

## Triggering human evidence

The candidate explicitly confirmed a viable additional career direction:

> Business/data analyst work is attractive when it is business-facing and aligned
> with the broader AI/transformation shift. The candidate may lack some current
> hard-tool requirements, but has extensive experience turning messy data into
> clear insights and informed business decisions.

Interpret this narrowly and truthfully:

- business analytics / decision support are not new capabilities; they are
  already strongly represented in the candidate profile;
- SQL/Python/tooling gaps must remain visible rather than being hand-waved away;
- the attractive direction is not generic reporting/data administration;
- preference is strongest where analytics supports decisions, transformation,
  commercial/product/business operations, or AI-enabled work;
- this statement is not authority to rewrite semantic-v1 or scoring weights.

The human also observed repeated employers during the 60-item compute-worthiness
review and questioned whether intake should broaden the employer portfolio.

## Known current portfolio

The committed source configuration currently contains 18 employers spanning
Workday, Greenhouse, AlmaCareer/Jobs.cz, SuccessFactors, generic HTML, JSON-feed,
and Phenom adapters.

The fresh SPEC-009 run observed 16,490 postings and 3,977 ACTIVE JobInstances,
but later audit evidence showed substantial employer concentration; the largest
employer represented approximately 57% of the routed audit population.

High volume therefore does not establish adequate employer or role-family
coverage.

## Core principle

Source selection should maximize **useful market coverage**, not raw posting
count.

Conceptually:

```text
EMPLOYER PORTFOLIO
        ↓
market-compatible opportunity supply
        ×
role-family relevance
        ×
source quality / maintainability
        ×
employer diversity
        ↓
USEFUL MARKET COVERAGE
```

Do not make the source portfolio candidate-blind merely for architectural purity.
Adapters and normalized job contracts remain candidate-independent, but the set
of employers we choose to observe is a product/research portfolio and may be
selected to improve coverage of the candidate's target market.

## Non-goals

Do NOT in this packet:

- add dozens of employers directly to production configuration;
- run a full refresh against newly discovered employers;
- make semantic-model calls;
- tune Luna, semantic-v1, scoring weights, preference effects, clustering, or
  seniority rules;
- rewrite historical judgments or SPEC-012 evidence;
- create a generic web/job-search crawler;
- integrate LinkedIn scraping or other sources that violate source terms;
- select employers only because they happen to use an easy ATS;
- equate title keywords with actual final job suitability;
- promote a new candidate preference vocabulary without checking existing
  taxonomy/profile coverage first.

## Part A — Current employer-portfolio audit

Using the current operational database and committed source configuration,
produce a read-only employer-level inventory.

For each configured employer report at minimum:

- adapter/source type;
- complete inventory count from the latest valid run;
- ACTIVE job count;
- usable detailed ACTIVE count;
- market-status distribution where current deterministic evaluation is possible;
- routed normal-candidate count;
- opportunity-cluster count;
- share of total routed population;
- compatible semantic-cache coverage (diagnostic only);
- source completeness/failure evidence;
- refresh/network cost indicators available from existing run evidence.

Report portfolio concentration using at least:

- top-1 employer share;
- top-3 employer share;
- top-5 employer share;
- Herfindahl-Hirschman Index or another explicit concentration metric;
- effective number of employers where useful.

Calculate concentration at more than one boundary where possible:

```text
all observed inventory
→ usable ACTIVE detail
→ market-routed candidate population
```

The point is to distinguish source-volume concentration from candidate-relevant
market concentration.

## Part B — Role-family coverage audit

Create a deterministic diagnostic role-family classifier for audit purposes, or
reuse an existing suitable taxonomy layer if one already exists.

Do not turn this into a production ranker.

At minimum distinguish enough families to answer the current question:

```text
BUSINESS_ANALYTICS
DATA_ANALYTICS
DECISION_INTELLIGENCE / DECISION_SUPPORT
BUSINESS_OPERATIONS / REVENUE_OPERATIONS
AI_TRANSFORMATION / DIGITAL_TRANSFORMATION
PRODUCT / PRODUCT_STRATEGY
COMMERCIAL / PRICING / RETENTION
DATA_SCIENCE / ML_ENGINEERING
SOFTWARE_ENGINEERING
CLOUD / INFRASTRUCTURE / SECURITY_ENGINEERING
FINANCE / ACCOUNTING / TAX
SALES / ACCOUNT_MANAGEMENT
CUSTOMER_SUPPORT / SERVICE
HR / PEOPLE
LEGAL
CLINICAL / MEDICAL
SUPPLY_CHAIN / WAREHOUSE / FIELD_SERVICE
OTHER / AMBIGUOUS
```

Names may follow existing taxonomy conventions if equivalent concepts already
exist. Prefer reuse over parallel ontology growth.

For each family report:

- total current opportunity clusters;
- current market `IN_SCOPE / UNCERTAIN / OUT_OF_SCOPE` distribution;
- employer count contributing at least one opportunity;
- top contributing employers and concentration;
- title-only versus description-supported classification confidence where
  relevant;
- examples privately for audit, not in repository-safe aggregate evidence.

Specifically inspect likely title variants for analyst-type work, including but
not limited to:

- Business Analyst
- Data Analyst
- Business Intelligence / BI Analyst
- Insights Analyst
- Commercial Analyst
- Strategy Analyst
- Operations Analyst
- Revenue Operations / Sales Operations Analyst
- Product Analyst
- Decision Scientist / Decision Intelligence
- Analytics Manager / Insights Manager
- Business Performance / Planning / Strategy & Operations

Do not assume the exact word `Analyst` is required. The candidate's historical
work often maps to analytics/decision-support roles with different titles.

## Part C — Candidate-direction representation audit

Inspect the current candidate profile and taxonomy before changing anything.

Determine whether the existing representation already captures:

```text
business analytics
turning messy data into insight
business decision support
decision intelligence
forecasting / KPI decomposition
commercial analytics
AI-enabled analytical work
transformation adjacency
```

The expected starting hypothesis is that capability representation is already
strong, while explicit decision-preference matching may understate
`business_analytics` / `decision_support` as attractive role directions.

Report exactly what is already represented and what, if anything, is missing.

If a missing decision-preference concept is clearly justified by the explicit
human statement, propose the smallest generic profile/taxonomy change, but do
not silently implement it unless doing so is explicitly included in the bounded
implementation and preserves all existing semantic/scoring fingerprints that
should remain stable.

No generic preference should imply attraction to low-level reporting, data entry,
or administrative data-maintenance roles merely because they contain the word
`data`.

## Part D — Source-portfolio expansion strategy

Design a principled employer-discovery framework rather than proposing random
companies.

A candidate employer should be evaluated along dimensions such as:

1. **Market access**
   - Prague/Czech presence;
   - Czech-compatible remote employment;
   - European remote where Czech employment is plausible.

2. **Target-role density**
   - business/data analytics;
   - decision intelligence / insights;
   - AI/digital transformation;
   - business/revenue operations;
   - product/strategy;
   - adjacent roles leveraging commercial/analytics leadership.

3. **Career-direction quality**
   - evidence of real AI/data transformation work rather than AI marketing copy;
   - roles with judgment, implementation ownership, and business impact;
   - plausible seniority/stretch envelope.

4. **Portfolio diversification**
   - avoid adding employers whose vacancy mix simply duplicates the current
     dominant source profile;
   - increase sector/business-model diversity where useful;
   - avoid one employer becoming the majority of candidate-routed supply.

5. **Source operability**
   - public career site available;
   - reliable inventory completeness;
   - supported ATS/adapter preferred when quality is otherwise equal;
   - new adapter cost explicitly identified rather than hidden.

Do not let adapter convenience dominate career relevance.

## Part E — Candidate employer discovery

Perform a bounded discovery exercise for potential new sources.

Target an initial longlist of approximately 20–40 candidate employers, then
score/rank them using the framework above.

Seek diversity across useful categories such as:

- Prague/Czech technology and SaaS;
- data/analytics/BI companies;
- AI-native or AI-platform companies with Czech/European hiring;
- fintech/payments and digital banking;
- cybersecurity;
- consumer/subscription technology;
- consultancies or enterprise transformation organizations only where execution
  ownership is plausible;
- remote-first European technology companies that can legally employ from
  Czechia.

The discovery process may use public career pages and ATS evidence. It must
record source URLs/evidence and distinguish:

```text
CONFIRMED_CURRENT_SOURCE
LIKELY_SOURCE
UNVERIFIED_CANDIDATE
```

Do not fabricate ATS tenants or endpoints.

## Part F — Existing-adapter leverage

For each shortlisted employer, identify whether onboarding appears possible via
an existing adapter family:

```text
Workday
Greenhouse
SuccessFactors
AlmaCareer/Jobs.cz
Phenom
JSON feed
generic HTML
```

Classify integration effort roughly as:

```text
CONFIG_ONLY
SMALL_ADAPTER_EXTENSION
NEW_ADAPTER_REQUIRED
UNKNOWN
```

This is an engineering-cost signal, not the primary ranking criterion.

## Part G — Proposed portfolio target

Recommend a bounded next employer expansion, not the final universe.

Prefer a staged proposal, for example:

```text
Wave A: 8–12 high-value / low-integration-cost employers
Wave B: 8–12 high-value employers requiring more source work
Watchlist: promising but insufficient evidence
```

The proposal should explain expected effect on:

- employer concentration;
- analyst/decision-support role coverage;
- AI-transformation role coverage;
- Prague/Czech/remote market coverage;
- network/runtime burden;
- maintenance burden.

Do not promise exact role counts from employers that have not yet been ingested.

## Part H — Intake portfolio policy

Propose a lightweight durable policy for future employer additions/removals.

The policy should prevent the current portfolio from becoming an accidental
historical list.

Consider rules such as:

- review portfolio concentration periodically;
- track unique candidate-relevant opportunity yield per employer;
- distinguish high-volume/low-relevance sources from high-yield sources;
- retire or deprioritize sources that repeatedly produce negligible useful
  opportunity supply unless they serve a deliberate control purpose;
- preserve source diversity;
- add sources to close observed role-family/market gaps;
- measure marginal useful coverage, not raw vacancies.

Do not automatically remove current employers in this packet.

## Part I — Relationship to semantic compute allocation

Keep intake breadth and compute allocation conceptually separate.

A broader employer portfolio may initially increase job volume and semantic
misses. That is acceptable if it improves the **quality and diversity of the
candidate opportunity universe**.

The architecture should therefore become:

```text
SOURCE PORTFOLIO
maximize useful market coverage
        ↓
DETERMINISTIC MARKET / HARD NEGATIVE FILTERS
remove obvious non-opportunities cheaply
        ↓
SEMANTIC COMPUTE ALLOCATION
spend deeper reasoning where it has decision value
        ↓
RANKED OPPORTUNITY FEED
```

Do not optimize source intake merely to make semantic-call counts smaller.

## Required aggregate outputs

Produce a repository-safe audit artifact containing no private human notes or
sensitive candidate details, with at least:

- configured employer count;
- concentration metrics by pipeline boundary;
- role-family coverage counts;
- number of employers represented per target role family;
- analyst/decision-support family findings;
- adapter-family distribution;
- candidate-employer longlist count;
- shortlist by Wave A / Wave B / Watchlist;
- expected integration effort categories;
- limitations;
- recommendation.

Detailed candidate employer evidence may remain private/local if it contains
volatile URLs or working notes; stable public source URLs may be tracked when
appropriate.

## External access / call budget

This packet authorizes bounded public source discovery needed to identify and
verify candidate employers/career pages.

It does NOT authorize:

- semantic-model calls;
- paid APIs;
- job applications or external actions;
- full ingestion/refresh of newly discovered employers.

Prefer deterministic/public HTTP inspection and repository tooling. Record any
source-discovery limitations honestly.

## Tests / validation

Add tests where code is introduced, including at minimum:

- concentration calculations;
- deterministic role-family classification fixtures;
- no employer-specific classification branches;
- analyst-title variant coverage;
- ambiguous roles remain ambiguous rather than forced;
- portfolio audit remains read-only against operational SQLite;
- candidate profile changes, if any, preserve unrelated fingerprints/caches;
- repository-safe aggregate excludes private evidence.

Run:

```bash
.venv/bin/pytest -q
git diff --check
```

No semantic calls.
No mutation of operational SQLite.
No new-employer production refresh.

## Decision gates

At the end, answer explicitly:

1. Is current employer concentration high enough to justify portfolio expansion?
2. Is business/data/decision-analytics coverage genuinely weak relative to the
   newly confirmed career direction, or merely hidden under alternate titles?
3. Is the gap primarily employer selection, role taxonomy/classification, market
   routing, or some combination?
4. Which 8–12 employers should form Wave A, and why?
5. Which existing employers, if any, appear high-volume but low marginal value?
6. Does the candidate profile need a bounded analytics-direction preference
   update?
7. What should the durable employer-intake policy be?
8. What is the smallest next implementation packet after the audit?

## Deliverable

Return:

A. files changed
B. audit/run identity and commands
C. current employer-portfolio concentration
D. per-employer useful-market contribution summary
E. current role-family coverage
F. business/data/decision-analytics coverage diagnosis
G. candidate-profile representation diagnosis
H. employer-discovery method
I. candidate employer longlist summary
J. Wave A / Wave B / Watchlist recommendation
K. adapter/integration effort assessment
L. expected coverage/diversification benefit
M. durable intake-portfolio policy proposal
N. relationship to semantic-compute architecture
O. privacy/evidence handling
P. tests/validation
Q. recommended next packet
R. recommended commit message

Do not commit or push implementation until explicit approval.
