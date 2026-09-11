# Wave A zero-detail source-contract preflight

## Status

Completed locally on 2026-09-11 as `wave-a-preflight-20260911-v4` under
`EXP-WAVE-A-PREFLIGHT-001`. This is source-onboarding evidence, not production
onboarding. `config/companies.yaml`, operational SQLite, Phase 2 state, candidate
configuration, and semantic state were unchanged.

The run made 36 bounded public listing/configuration requests, zero detail-page
calls, and zero semantic calls. All nine inventory attempts completed.

## Decision

The first configuration-only onboarding experiment should contain:

- Keboola
- Commerzbank
- KPMG

Mews is the highest-value secondary candidate, but its current first-party
`/api/careers` feed requires one bounded reusable nested-feed extension. Erste
Group needs a listing-geography investigation. Zentiva needs a generic Workday
identity/listing-evidence correction before onboarding. Productboard, ABB, and
MSD should not be onboarded from this snapshot because their current marginal
target-role yield is too low.

## Normalized scorecard

| Employer | Public source / adapter | Inventory | Listing evidence (title / URL / location / date) | Retrieval-scope signal | Title-supported target signal | Projected network details | Requests | Verdict |
|---|---|---:|---:|---|---|---:|---:|---|
| Keboola | first-party HTML / Generic HTML | 3 | 3 / 3 / 3 / 0 | 3 in scope | decision intelligence/support: 1 | 3 | 1 | `GO_CONFIGURATION_ONLY` |
| Mews | first-party nested JSON feed | 28 | 28 / 28 / 28 / 28 | 11 in scope; 17 foreign | operations: 1; product: 4 | 11 | 1 | `GO_BOUNDED_ADAPTER_FIX` |
| Productboard | first-party HTML / Generic HTML | 8 | 8 / 8 / 8 / 0 | 6 in scope; 2 foreign | none in the frozen/extended title lens | 6 | 1 | `NO_GO_LOW_MARGINAL_VALUE` |
| Commerzbank | Alma Career | 24 | 24 / 24 / 24 / 24 | 24 Czech | product: 2 | 24 | 10 | `GO_CONFIGURATION_ONLY` |
| Erste Group | SuccessFactors HTML | 55 | 55 / 55 / 0 / 0 | 55 unknown | business analytics: 1; product: 1 | 55 | 2 | `CONDITIONAL_SOURCE_INVESTIGATION` |
| ABB | Alma Career | 56 | 56 / 56 / 56 / 56 | 56 Czech | none in the title lens | 56 | 7 | `NO_GO_LOW_MARGINAL_VALUE` |
| KPMG | Alma Career | 29 | 29 / 29 / 29 / 29 | 29 Czech | business analytics: 1; transformation: 1 | 29 | 10 | `GO_CONFIGURATION_ONLY` |
| MSD | Alma Career | 0 | 0 / 0 / 0 / 0 | confirmed empty | none | 0 | 2 | `NO_GO_LOW_MARGINAL_VALUE` |
| Zentiva | Workday | 40 | 40 / 40 / 0 / 0 | 40 unknown | business analytics: 1; product: 1 | 40 | 2 | `GO_BOUNDED_ADAPTER_FIX` |

Work mode and employment type were absent across these listing surfaces. Mews
also exposed department and update evidence for all 28 listings. The projections
apply the existing conservative retrieval-scope policy: unknown geography is
retained, and the result is not a final candidate-eligibility decision.

## Source-contract findings

### Configuration-ready

Keboola and Productboard both work through declarative Generic HTML selectors;
the difference is marginal role yield, not technical reachability. Commerzbank
and KPMG use the existing Alma listing contract and produce stable identities,
structured Czech locations, titles, URLs, dates, and complete pagination.

### Bounded reusable fixes

Mews no longer exposes the Greenhouse board described by the older research
fingerprint. Its current first-party endpoint returns nine department groups,
each with an explicit `jobCount` and nested jobs containing ID, title, URL,
location, locations, and update time. All group counts and 28 unique identities
validated. A declarative nested-item/group-count extension is preferable to
company-specific code.

ABB and MSD expose a newer inline Alma widget configuration that the current
adapter does not discover, while their shared listing GraphQL contract remains
compatible. This is a generic discovery gap, but neither source earns an
onboarding fix from current role yield: ABB has 56 mostly industrial/engineering
listings and no title-supported target family; MSD explicitly reports zero.

Zentiva's Workday response proves complete pagination and 40 unique canonical
URLs, but the field currently interpreted by the adapter as `external_job_id`
contains listing location text for this tenant: only 12 distinct values across
40 postings. Listing geography is therefore both available in the raw source
and mapped to the wrong concept. Production onboarding must wait for a generic
Workday identity/listing-evidence correction with cross-tenant regression tests.

### Investigation required

Erste's SuccessFactors listing completed in two requests with 55 unique IDs and
URLs, but its rows expose no listing-level location. All 55 therefore remain
geography unknown and would require detail retrieval. A bounded source-contract
investigation should determine whether an existing filter/API can supply
location without weakening complete inventory; URL slugs must not be treated as
geography by assumption.

## Diversification and operating value

- Keboola adds a Czech-native data/analytics platform, albeit with only three
  current vacancies.
- Mews adds Czech-founded hospitality SaaS/product breadth and the strongest
  current target-role count in Wave A.
- Commerzbank adds another Prague banking source with mature listing evidence.
- KPMG adds transformation/professional-services breadth with two explicit
  target-title signals.
- Erste adds Central-European banking breadth but currently has costly unknown
  geography.
- ABB adds industrial technology but little current target-role yield.
- MSD and Zentiva add pharma breadth; only Zentiva has current target-title
  evidence, and its listing identity contract is not safe yet.
- Productboard adds product SaaS breadth but its current inventory is dominated
  by deep engineering roles.

## Evidence and limitations

The frozen source-portfolio classifier remains unchanged. This preflight uses a
versioned title-only extension for `financial intelligence`, mixed Czech/English
`business analytik`, transformation titles, and `digital strategy`. It does not
inspect descriptions and is not candidate suitability scoring.

Current vacancies and public contracts are volatile. A zero current target count
does not mean an employer can never become valuable; it means the present
snapshot does not justify its operating cost. `GO_*` verdicts authorize only a
separate bounded onboarding packet and do not modify production configuration.

The canonical repository-safe receipt is
`output/wave_a_source_preflight/wave-a-preflight-20260911-v4/aggregate_summary.json`.
The detailed per-listing artifact remains private/local by `.gitignore` policy;
its SHA-256 is preserved in the aggregate receipt.

## Next packet

Create one bounded production-onboarding experiment for the three
configuration-only sources: Keboola, Commerzbank, and KPMG. Keep Mews as the
first separately reviewed generic adapter-extension candidate. Do not combine
the Mews or Zentiva fixes with configuration-only onboarding, and do not change
existing source/lifecycle contracts to force a source through.
