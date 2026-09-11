# Source Portfolio and Role-Coverage Audit

Status: implementation result for SPEC-013, awaiting review. This is a
read-only intake/source-portfolio experiment, not a production source change or
a semantic-ranking result.

## Run identity

- Experiment: `EXP-SOURCE-PORTFOLIO-001`
- Run: `source-portfolio-audit-20260911-v2`
- Role classifier: `source-portfolio-role-family-v1`
- Starting Git commit: `e0f0a0b7346cc80eb489261547c9619792207b89`
- Audit configuration fingerprint:
  `684cc5ac881573b64f7e397f6949a156f5eba5868db699b9e5c97aae44d7f5bc`
- Operational database SHA-256 before and after:
  `54f82d4b7ec765b565b7d3ecab06117d32eec4fbcc77f4b23206e6b079987e14`
- Semantic calls: 0
- New-employer ingestion calls: 0
- SQLite writes: 0

Command:

```bash
.venv/bin/opportunity-radar-source-portfolio-audit \
  --run-id source-portfolio-audit-20260911-v2
```

## Executive result

The current 18-employer portfolio is too concentrated for a useful view of the
candidate's opportunity market. Concentration increases after market routing:
one employer supplies 57.3% of normal-candidate OpportunityClusters and the
effective breadth is only 2.77 employers.

Business/data/decision-analytics opportunities are not wholly absent. The audit
found 388 clusters with at least one target-family signal, including 164 with a
title-supported signal. The useful supply is still structurally narrow:

- only 18 of the 388 target-family clusters are deterministically `IN_SCOPE`;
- 297 are `UNCERTAIN` and 73 are `OUT_OF_SCOPE`;
- one employer supplies 55.9% of target-family clusters;
- explicit decision-intelligence/support titles are absent; all 14 matches for
  that family depend on description evidence;
- commercial/pricing/retention and AI/transformation evidence is especially
  concentrated in EY.

The gap is therefore a combination of employer selection, title/role-family
visibility, and incomplete market evidence. It is not an absent candidate
capability. The profile already records expert business analytics, decision
support, forecasting, commercial strategy, and business-operations capability.

Recommendation:
`EXPAND_PORTFOLIO_IN_BOUNDED_WAVES_AFTER_SOURCE_CONTRACT_PREFLIGHT`.

## Employer concentration

| Boundary | Total | Top 1 | Top 3 | Top 5 | HHI | Effective employers |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Latest complete inventory | 16,490 | 47.9% | 77.9% | 93.0% | 2,902.75 | 3.45 |
| Usable ACTIVE detail | 3,935 | 48.9% | 78.1% | 87.2% | 2,899.50 | 3.45 |
| Normal-candidate clusters | 3,326 | 57.3% | 80.6% | 88.4% | 3,617.01 | 2.77 |

HHI is reported on the conventional 0–10,000 scale. Effective employers is
the inverse of the fractional HHI. These are concentration diagnostics, not
regulatory market-share claims.

## Per-employer contribution

| Employer | Adapter | Inventory | ACTIVE | Usable detail | Clusters | Routed | Market I/U/O | Routed share | Cache hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EY | SuccessFactors | 7,898 | 1,926 | 1,926 | 1,914 | 1,907 | 0/1,907/7 | 57.3% | 25 |
| Schneider Electric | JSON feed | 3,183 | 677 | 677 | 633 | 456 | 2/454/177 | 13.7% | 14 |
| Johnson & Johnson | Workday | 1,757 | 472 | 472 | 472 | 318 | 3/315/154 | 9.6% | 17 |
| Cisco | Phenom | 1,278 | 148 | 148 | 148 | 146 | 3/143/2 | 4.4% | 18 |
| ČSOB | AlmaCareer | 114 | 114 | 114 | 114 | 113 | 0/113/1 | 3.4% | 23 |
| Pure Storage | Greenhouse | 322 | 209 | 209 | 209 | 85 | 39/46/124 | 2.6% | 20 |
| Deutsche Börse Group | SuccessFactors | 220 | 82 | 82 | 82 | 81 | 66/15/1 | 2.4% | 25 |
| Siemens | AlmaCareer | 50 | 50 | 50 | 50 | 47 | 0/47/3 | 1.4% | 22 |
| Wrike | Greenhouse | 69 | 69 | 69 | 66 | 43 | 1/42/23 | 1.3% | 24 |
| WPP | Greenhouse | 211 | 54 | 54 | 52 | 39 | 0/39/13 | 1.2% | 20 |
| Roche | Phenom | 1,216 | 30 | 30 | 30 | 30 | 0/30/0 | 0.9% | 23 |
| Red Hat | Workday | 40 | 37 | 37 | 37 | 24 | 0/24/13 | 0.7% | 5 |
| SAP | SuccessFactors | 29 | 29 | 29 | 29 | 23 | 23/0/6 | 0.7% | 14 |
| GoodData | Generic HTML | 7 | 7 | 7 | 7 | 7 | 7/0/0 | 0.2% | 5 |
| Kiwi.com | Generic HTML | 11 | 11 | 11 | 7 | 5 | 0/5/2 | 0.2% | 6 |
| Pfizer | Workday | 40 | 17 | 17 | 17 | 1 | 0/1/16 | <0.1% | 1 |
| Honeywell | AlmaCareer | 3 | 3 | 3 | 3 | 1 | 0/1/2 | <0.1% | 2 |
| Allegro | JSON feed | 42 | 42 | 0 | 0 | 0 | 0/0/0 | 0.0% | 0 |

`Market I/U/O` means `IN_SCOPE / UNCERTAIN / OUT_OF_SCOPE` among usable
OpportunityClusters; Allegro has no usable cluster evidence to classify.

All 18 latest valid source observations were `SUCCESS` with complete identity
inventories. The database does not persist actual per-run network detail-request
counts, so successful detail observations are not mislabeled as network cost.

EY and Johnson & Johnson are high-volume sources with low marginal
diversification because together they supply 66.9% of routed clusters. This is
not evidence that they have no useful jobs and does not authorize removal.
Allegro's 42 active identities have no usable detailed content in this snapshot;
it contributes no role or routed-cluster evidence and needs a separate source-
quality diagnosis if retained.

## Role-family coverage

The classifier is a neutral, multi-label diagnostic. Title evidence is treated
as high-confidence role evidence. Description-only classification requires two
independent patterns and remains medium-confidence adjacency evidence. Counts
can overlap across families.

| Role family | Clusters | Routed | Employers | In scope | Uncertain | Out of scope | Title-supported | Description-only | Largest contributor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Business analytics | 61 | 50 | 7 | 5 | 45 | 11 | 24 | 37 | EY 37 |
| Data analytics | 166 | 142 | 10 | 7 | 135 | 24 | 14 | 152 | EY 107 |
| Decision intelligence/support | 14 | 8 | 3 | 0 | 8 | 6 | 0 | 14 | J&J/EY 5 each |
| Business/revenue operations | 31 | 23 | 7 | 5 | 18 | 8 | 13 | 18 | EY 11 |
| AI/digital transformation | 39 | 35 | 7 | 1 | 34 | 4 | 20 | 19 | EY 29 |
| Product/strategy | 74 | 49 | 9 | 1 | 48 | 25 | 65 | 9 | EY 20 |
| Commercial/pricing/retention | 33 | 32 | 6 | 2 | 30 | 1 | 30 | 3 | EY 26 |
| Data science/ML engineering | 60 | 51 | 9 | 2 | 49 | 9 | 26 | 34 | EY 35 |
| Software engineering | 102 | 88 | 13 | 26 | 62 | 14 | 87 | 15 | Pure Storage 28 |
| Cloud/infrastructure/security | 238 | 211 | 13 | 24 | 187 | 27 | 42 | 196 | EY 140 |
| Finance/accounting/tax | 614 | 577 | 11 | 10 | 567 | 37 | 578 | 36 | EY 518 |
| Sales/account management | 160 | 126 | 10 | 3 | 123 | 34 | 160 | 0 | Schneider 44 |
| Customer support/service | 62 | 56 | 8 | 1 | 55 | 6 | 15 | 47 | Schneider 17 |
| HR/people | 29 | 24 | 7 | 6 | 18 | 5 | 26 | 3 | EY 11 |
| Legal | 11 | 7 | 5 | 1 | 6 | 4 | 10 | 1 | J&J 5 |
| Clinical/medical | 86 | 61 | 4 | 0 | 61 | 25 | 76 | 10 | J&J 73 |
| Supply chain/warehouse/field service | 184 | 136 | 6 | 0 | 136 | 48 | 159 | 25 | Schneider 102 |
| Other/ambiguous | 2,142 | 1,849 | 16 | 67 | 1,782 | 293 | 0 | 0 | EY 1,010 |

### Analytics diagnosis

The broad target-family union is 10.0% of all current clusters and 9.5% of
routed clusters. This should not be read as 388 suitable jobs. More than half
of the union is description-only evidence, and 76.5% is market `UNCERTAIN`.

The current source portfolio does surface some alternate titles such as product,
commercial, operations, strategy, performance, and insights roles. It does not
support the claim that the gap is merely a keyword problem:

- high-confidence title coverage is only 164 unique clusters;
- explicit decision-intelligence/support title coverage is zero;
- target-family effective employer breadth is 2.84;
- the largest employer supplies 55.9% of target-family clusters;
- only 18 target-family clusters have confirmed in-scope market evidence.

Employer expansion should therefore target both role density and better Czech/
European market evidence. Classification improvements alone cannot diversify
the underlying market supply.

## Candidate-direction representation

The profile already represents the factual capability side strongly:

| Concept | Level | Confidence |
| --- | --- | --- |
| `business_analytics` | EXPERT | HIGH |
| `decision_support` | EXPERT | HIGH |
| `forecasting` | EXPERT | HIGH |
| `commercial_strategy` | EXPERT | HIGH |
| `business_operations` | EXPERT | HIGH |
| `machine_learning_business_application` | INTERMEDIATE | HIGH |

The legacy semantic preference input also includes very-high analytical problem
solving and decision intelligence, high business operations/transformation, and
very-high AI-enabled work. The post-semantic decision layer already has positive
`business_operations`, strong-positive `ai_enabled_work`, and strong-positive
`transformation_execution` entries.

The explicit human direction is not fully represented in decision-only policy:
`business_analytics` and `decision_support` are absent. A later bounded profile
version should test adding those generic concepts to `decision_preferences`.
That change must be separate from source onboarding and should recompute only
decision effects. This audit did not change the candidate profile, semantic
fingerprint, semantic-v1, or cache.

## Employer discovery method

The longlist contains 30 employers from the existing fingerprinted 50-company
research dataset. It was ranked on five bounded 0–3 dimensions: market access,
target-role density, career-direction quality, diversification, and source
operability. Adapter convenience is only one dimension.

Public career/source evidence was rechecked on 2026-09-11 for selected current
sources, including Mews, Productboard, Keboola, Gen Digital, Rossum, ABB, Eaton,
MSD, Takeda, and Visa. Remaining entries retain `LIKELY_SOURCE` or
`UNVERIFIED_CANDIDATE` status from the fingerprinted research evidence rather
than being silently upgraded.

### Wave A — configuration-first preflight

| Employer | Portfolio reason | Expected integration |
| --- | --- | --- |
| Keboola | Data platform; Prague; analytics/transformation adjacency | Generic HTML, config only |
| Mews | Current Czech analytics, strategy/operations, fintech and AI-builder roles | Greenhouse, config only |
| Productboard | Prague product/AI environment and structured first-party inventory | Generic HTML, config only |
| Commerzbank | Adds banking/financial-operations diversity | AlmaCareer, config only; source reconfirmation required |
| Erste Group | Adds CEE banking, data and transformation breadth | SuccessFactors, config only; source reconfirmation required |
| ABB | Adds industrial/digitalization diversity and a confirmed Alma portal | AlmaCareer, config only |
| KPMG | Adds Prague analytics/transformation consulting supply | AlmaCareer, config only; source reconfirmation required |
| MSD | Adds Prague pharma/digital diversity and a confirmed Alma portal | AlmaCareer, config only |
| Zentiva | Adds Prague pharma/business breadth | Workday, config only; tenant reconfirmation required |

Wave A contains nine employers. Each still needs a zero-detail source-contract
preflight before production configuration. “Config only” is an expectation from
existing adapter evidence, not proof of current tenant compatibility.

### Wave B — high-value source work

| Employer | Portfolio reason | Expected integration |
| --- | --- | --- |
| Gen Digital | Prague cybersecurity, product growth and automated decisioning | New Ashby adapter |
| Mastercard | Payments, analytics and Prague presence | Small Phenom-family extension to verify |
| Visa | Payments/data/analytics role density | New SmartRecruiters adapter |
| Rossum | Prague AI-native product and decision systems | New Ashby adapter |
| Accenture | Transformation scale and execution-oriented roles | New adapter/source contract |
| Barclays | Prague banking/data/operations breadth | New first-party adapter |
| Microsoft | Prague enterprise technology/data/AI breadth | New first-party adapter |
| Sanofi | Pharma digital/data transformation diversity | Small source-family extension to verify |
| Takeda | Existing Workday leverage and data/digital transformation evidence | Config only; market-role yield must be proven |
| AstraZeneca | Prague pharma/data/digital breadth | New TalentBrew adapter |

### Watchlist

BCG, Deloitte, Eaton, McKinsey, Novartis, Raiffeisen Bank International,
Resistant AI, Bosch, Oracle, PwC, and Bayer remain a watchlist. Reasons include
lower expected Prague target-role density, uncertain market access, source work,
or insufficient first-party vacancy evidence. Resistant AI remains explicitly
unverified because its first-party page previously exposed only unsupported
LinkedIn vacancy links.

## Expected effect and burden

Wave A deliberately combines Prague technology/data employers with banking,
pharma, consulting and industrial sources. It should improve employer and
business-model breadth and create more chances to observe analyst,
decision-support, operations and transformation roles. Exact future role counts
or concentration reductions are not projected because these employers have not
been ingested.

Operationally, AlmaCareer and global Workday/SuccessFactors sources may add
large inventories and detail workload. The zero-detail preflight must measure
inventory size, listing geography, completeness, source contract, and projected
network detail requests before any production onboarding. New Ashby and
SmartRecruiters work should be justified by higher expected useful-market yield,
not implemented simply because the APIs appear convenient.

## Durable intake policy proposal

The source portfolio should optimize marginal useful market coverage, not raw
vacancy count.

For each employer addition or periodic review, record:

1. concentration at complete inventory, usable detail, and routed cluster
   boundaries;
2. unique candidate-relevant cluster yield, not duplicated posting count;
3. target-role-family employer breadth and market-status quality;
4. source completeness, projected network burden, and maintenance history;
5. marginal sector/business-model diversity.

Add an employer when public, operable source evidence plausibly closes an
observed market or role gap. Retire or deprioritize only after repeated
negligible unique useful yield or unacceptable source cost is reviewed. Never
remove an employer automatically, and never let a filtered retrieval request
replace complete identity inventory for lifecycle.

## Decision gates

1. **Portfolio expansion justified:** Yes. Routed top-1 share is 57.3%, HHI is
   3,617, and effective breadth is 2.77 employers.
2. **Analytics coverage weak or hidden:** Both, but not merely hidden. Alternate
   titles add coverage, while decision-support title evidence, confirmed
   in-scope supply, and employer breadth remain weak.
3. **Primary cause:** Employer selection plus role visibility and market-evidence
   quality. Candidate capability representation is not the cause.
4. **Wave A:** The nine configuration-first employers listed above.
5. **High-volume/low-marginal-value evidence:** EY and J&J dominate supply and
   diversification; Allegro supplies identities but no usable detail. No source
   removal is authorized.
6. **Profile update needed:** A bounded future decision-preference version for
   `business_analytics` and `decision_support` is justified. No capability or
   semantic-v1 change is needed.
7. **Intake policy:** Measure marginal useful coverage, concentration, market
   evidence, and source cost through explicit portfolio review gates.
8. **Smallest next packet:** Zero-detail source-contract preflight for Wave A.
   It should validate tenant/config compatibility, complete inventory behavior,
   listing-level geography, and projected detail burden without adding employers
   to production configuration or changing lifecycle.

## Evidence and privacy

The repository-safe aggregate is
`output/source_portfolio_audit/source-portfolio-audit-20260911-v2/aggregate_summary.json`.
It contains aggregate counts, public employer/source evidence, configuration and
database hashes, limitations, and conclusions. Per-cluster titles and matched
signals remain in the Git-ignored private `audit.json`; its SHA-256 is preserved
in the aggregate. No human notes or semantic payloads are included.

## Limitations

- This is a snapshot of the 2026-09-05 operational state, audited on
  2026-09-11; it is not a fresh source refresh.
- Role classification is multi-label evidence, not exclusive occupation coding
  or candidate suitability.
- Description-only matches can represent adjacency rather than the primary job
  family.
- Source status and ATS tenancy can change. `LIKELY_SOURCE` entries require
  bounded verification.
- No candidate employer was ingested, so portfolio benefits remain directional.
- Semantic cache coverage is diagnostic only and did not influence role/source
  selection.
