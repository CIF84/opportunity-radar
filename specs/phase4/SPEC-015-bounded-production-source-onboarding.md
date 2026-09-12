# SPEC-015 — Bounded Production Source Onboarding and Coverage Delta

Status: `IMPLEMENTED_LOCALLY_AWAITING_REVIEW`

## Purpose

Promote only the three configuration-ready winners from the frozen SPEC-014 Wave A source-contract preflight into one bounded production onboarding experiment:

- Keboola
- Commerzbank
- KPMG

This packet is not a general employer-expansion authorization. Its purpose is to test the complete existing ingestion/state pipeline on three deliberately selected sources and measure whether they materially improve the useful opportunity universe.

## Evidence basis

SPEC-013 established that the existing 18-employer portfolio has high raw vacancy volume but very low effective employer breadth at the routed-cluster boundary.

SPEC-014 then evaluated nine Wave A candidates with zero detail calls and recommended exactly three for configuration-only onboarding:

- Keboola: 3 listings, all three in-scope at listing level, one decision-support title signal.
- Commerzbank: 24 Czech listings, two product-title signals.
- KPMG: 29 Czech listings, one analytics and one transformation title signal.

Mews, Erste, and Zentiva remain separate engineering/source-contract questions. Productboard, ABB, and MSD are not authorized for onboarding from the frozen snapshot.

## Governing question

Do these three sources materially improve the market Opportunity Radar can observe, rather than merely increasing configured-employer and posting counts?

The experiment must measure marginal useful market coverage.

## Protected boundaries

Do not change:

- candidate profile or decision preferences;
- market-access policy or market-status rules;
- Luna / reasoning / semantic contract;
- semantic prompt, scoring weights, thresholds, or existing semantic assessments;
- clustering contract;
- seniority guard;
- historical judgments or frozen SPEC-012 evidence;
- SPEC-008 prospective protocol;
- Phase 1/2 identity and lifecycle semantics;
- Mews/Erste/Zentiva source contracts;
- any Wave B or Watchlist employer.

No semantic calls are authorized.

## Production configuration change

Add exactly these three employers to production `config/companies.yaml` using only the source/adapter contracts proven by SPEC-014.

Do not add candidate-specific filtering or employer-specific behavior to shared adapters.

If a source cannot be represented faithfully by existing declarative configuration, stop that employer's onboarding and report the mismatch rather than patching shared architecture opportunistically.

## Pre-change baseline

Before modifying production configuration or state, capture a sanitized baseline receipt containing at least:

- Git commit and dirty-state classification;
- configured employer count;
- operational SQLite hash and schema version;
- latest complete state run identity;
- ACTIVE/CLOSED counts;
- usable detailed ACTIVE count;
- current inventory/usable-detail/routed-cluster employer concentration where reconstructable;
- HHI and effective-employer count at the routed boundary;
- current target-family counts and market-status distribution using the SPEC-013 classifier;
- semantic assessment row count.

Intentionally retained private/local operational artifacts are allowed; unrelated code/config divergence is not.

## Bounded onboarding execution

Run the three newly configured sources through the normal production ingestion/state architecture.

Requirements:

1. Complete inventory must be attempted for all three sources.
2. Lifecycle authority remains complete inventory only.
3. Detail retrieval is allowed for the three new sources because this packet is the first bounded production onboarding experiment.
4. Existing source refreshes should not be performed merely to execute this packet unless the normal runner cannot safely isolate the three new employers. Prefer a bounded configuration/run mechanism that exercises production code without refreshing all 21 employers.
5. Persist new-source Phase 2 evidence through the normal repository/state contracts; do not create a parallel onboarding database model.
6. Do not run semantic assessment for newly ingested jobs.
7. Do not alter existing semantic cache records.
8. Record listing/detail request counts and per-employer elapsed time.
9. Preserve source errors and incomplete evidence rather than fabricating completeness.

If the existing CLI cannot safely execute only the three approved employers without weakening contracts, add the smallest generic bounded-source selection mechanism with regression coverage. It must be reusable and must not change normal all-source behavior.

## Per-source acceptance

For each employer report:

- inventory size;
- inventory completeness;
- listing geography evidence quality;
- selected-for-detail count;
- intentionally skipped count;
- detail successes/failures;
- usable normalized title/description count;
- network request count;
- elapsed time;
- ACTIVE identities created/reused;
- lifecycle anomalies;
- target-family title/description signals;
- candidate market-status distribution after detail;
- clustering results, including any cross-source or same-employer variants;
- source-specific limitations.

A source may be removed from production configuration within this same uncommitted experiment if bounded production evidence shows that the SPEC-014 configuration contract was materially wrong or the source cannot meet existing ingestion invariants. Preserve that as a failed onboarding result rather than forcing promotion.

## Coverage-delta evaluation

After successful bounded ingestion, recompute the source-portfolio audit metrics with the same classifier semantics used by SPEC-013.

Compare before vs after at minimum:

### Employer breadth

- configured employer count;
- employers contributing usable ACTIVE detail;
- employers contributing routed clusters;
- top-1 / top-3 / top-5 routed shares;
- routed HHI;
- effective-employer count.

### Opportunity coverage

- ACTIVE jobs;
- usable detailed ACTIVE jobs;
- OpportunityClusters;
- routed clusters;
- `IN_SCOPE / UNCERTAIN / OUT_OF_SCOPE` routed distribution.

### Target career-family coverage

Use the frozen SPEC-013 role-family classifier and report deltas for at least:

- business/data analytics;
- decision support / decision intelligence;
- business operations / strategy & operations;
- AI transformation / digital transformation;
- product / product strategy;
- commercial/revenue/insights adjacency where already represented by the classifier.

Report title-supported and description-only signals separately.

Do not claim semantic fit from lexical family evidence.

## Material-improvement interpretation

The experiment should not use an arbitrary raw-posting target as the success criterion.

Classify the combined onboarding result as one of:

- `MATERIAL_COVERAGE_IMPROVEMENT`
- `MODEST_COVERAGE_IMPROVEMENT`
- `LOW_MARGINAL_VALUE`
- `ONBOARDING_CONTRACT_FAILURE`

The interpretation must consider jointly:

1. employer-diversification improvement;
2. new routed/in-scope opportunity supply;
3. target-role-family breadth;
4. source reliability/completeness;
5. ongoing request/detail burden.

A small source such as Keboola may be high value despite few postings if it contributes unusually relevant/in-scope opportunity supply. A larger source may be low value if it adds mostly irrelevant or unusable evidence.

## Semantic compute boundary

Do not assess new jobs with Luna in this packet.

At completion report:

- how many new current jobs would be eligible for semantic processing;
- how many have no compatible semantic cache by construction;
- a directional projected semantic-call/cost burden using the existing frozen cost estimate only if that calculation already exists and can be reused without changing compute-allocation policy.

This is diagnostic economics, not spending authorization.

## Mews preservation

Mews remains the preferred next adapter-extension candidate from SPEC-014.

Do not implement its nested-feed extension here. The final report should preserve its status and compare the observed marginal value of the three configuration-only sources against the expected value of paying the small Mews engineering cost next.

## Evidence and privacy

Create an immutable experiment packet/receipt under a new production-onboarding experiment identity.

Repository-safe aggregate evidence may include:

- employer names;
- aggregate source counts;
- public source-contract facts;
- before/after concentration metrics;
- aggregate role-family counts;
- fingerprints/hashes;
- limitations and verdicts.

Keep detailed vacancy titles/descriptions/URLs, candidate-derived per-job decisions, and operational database evidence private/local unless already governed as public repository evidence.

Do not commit operational SQLite.

## Documentation

Update as appropriate:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `README.md`
- `experiments/registry.yaml`
- SPEC-015 implementation status

Document actual evidence, not intended outcomes.

Do not silently mark Mews, Erste, Zentiva, Wave B, or Watchlist employers as approved.

## Required tests

Add offline/regression coverage proving at least:

- only the three approved employers are added by this packet;
- production configuration remains generic and parseable;
- bounded-source execution cannot accidentally refresh unselected employers;
- all-source behavior remains unchanged;
- complete inventory still solely controls closure;
- semantic calls remain zero;
- existing semantic assessments are untouched;
- source failure/incompleteness does not produce false closure;
- coverage-delta arithmetic is deterministic;
- HHI/effective-employer calculations are consistent with SPEC-013;
- target-family classifier identity is preserved;
- private evidence is excluded from repository-safe aggregate output.

Run the full offline suite and `git diff --check`.

## Stop conditions

Stop and report before improvising if:

- an approved source requires a new adapter rather than proven configuration reuse;
- bounded execution cannot isolate the three sources safely;
- a source's inventory contract is materially different from SPEC-014;
- production ingestion would require candidate-specific adapter logic;
- a source is incomplete in a way that would make lifecycle inference unsafe;
- unrelated code/config divergence is discovered.

## Deliverable

Return a structured report containing:

A. pre-change baseline;
B. production configuration changes;
C. bounded run identity/commands;
D. per-employer ingestion results;
E. lifecycle/state integrity;
F. before/after employer concentration;
G. before/after opportunity coverage;
H. target-role-family coverage delta;
I. semantic-call/cost diagnostic without calls;
J. combined material-improvement verdict;
K. per-employer keep/remove recommendation;
L. comparison with Mews as next adapter-extension candidate;
M. privacy/evidence boundary;
N. tests and validation;
O. files changed;
P. recommended next packet;
Q. recommended commit message.

No commit or push until normal approval after review.

## Implementation result

State run `1e5f4685-563d-40d5-8463-c364b6d34834` completed 56/56 details for
the three approved sources with zero failures and zero semantic calls. The
combined verdict is `MODEST_COVERAGE_IMPROVEMENT`; see
`docs/production_source_onboarding_report.md`.
