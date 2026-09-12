# SPEC-016 — Declarative Nested-Feed Extension and Mews Onboarding Experiment

Status: `APPROVED_FOR_IMPLEMENTATION`

## Purpose

Implement the smallest reusable ingestion capability needed to support the current Mews first-party careers feed, then run a bounded production onboarding experiment for Mews and measure its marginal useful-market contribution.

This packet is not a Mews-specific scraper exercise. The architectural question is whether a generic declarative nested-feed flattening capability is worth adding because it unlocks a materially useful source without weakening adapter invariants.

## Evidence basis

SPEC-014 found:

- Mews current source: first-party `/api/careers` feed;
- 28 current listings;
- 11 listing-level `IN_SCOPE`, 17 foreign;
- target-title signals included operations and product roles;
- old Greenhouse research fingerprint is stale;
- source was not configuration-only because the feed shape requires reusable nested flattening.

SPEC-015 then onboarded Keboola, Commerzbank, and KPMG successfully, but the combined result was only `MODEST_COVERAGE_IMPROVEMENT`:

- 56 jobs added;
- 51 newly routed clusters;
- effective routed employer breadth improved only from 2.765 to 2.849;
- target-family clusters increased 388 → 391;
- target-family `IN_SCOPE` supply did not increase;
- no semantic calls were made.

Mews is therefore the next source-investment candidate because the expected engineering cost is bounded and its preflight suggested higher in-scope density than the prior three-source wave.

## Governing questions

1. Can the existing JSON-feed adapter family be extended generically to flatten nested first-party payloads using declarative configuration rather than employer-specific code?
2. Does Mews satisfy complete-inventory and normalized-detail invariants after that extension?
3. Does Mews produce enough marginal useful market coverage to justify the added reusable adapter complexity?

## Protected boundaries

Do not change:

- candidate profile or decision preferences;
- market-access policy or market-status rules;
- Luna / reasoning / semantic contract;
- semantic prompts, scoring weights, thresholds, or existing assessments;
- clustering semantics;
- seniority guard;
- Phase 1/2 lifecycle and identity rules;
- Erste or Zentiva source contracts;
- any Wave B or Watchlist employer;
- historical experiments or judgments.

No semantic calls are authorized.

## Adapter design constraint

Prefer a reusable declarative extension of the existing JSON-feed ingestion machinery.

The configuration contract may add concepts such as:

- nested item paths;
- list flattening / child collection traversal;
- parent-context field inheritance;
- declarative field extraction from flattened records;
- deterministic identity projection.

Exact field names are implementation choices, but the capability must be source-generic and testable using synthetic fixtures independent of Mews.

Do not add `if company_id == "mews"` or equivalent employer-specific branches to shared adapter code.

If the actual feed cannot be represented faithfully with a bounded generic extension, stop and report rather than escalating into a bespoke adapter without approval.

## Source-contract reconstruction

Before implementation, inspect the current Mews first-party feed and document:

- root payload shape;
- where vacancy records actually live;
- nesting depth;
- whether parent objects carry location/team metadata needed by children;
- unique job identifier source;
- canonical URL source;
- title;
- location;
- employment/work-mode evidence if present;
- department/team evidence if present;
- posting/update timestamps if present;
- whether description/detail content is embedded or requires a separate request;
- pagination / completeness semantics;
- duplicate/locale variants if any.

Preserve only public source-contract facts in repository-safe evidence.

## Required generic capability

The extension must support at minimum the concrete nesting needed for Mews while remaining generic.

Required properties:

1. Deterministic flattening.
2. Stable order independent of irrelevant object-key ordering.
3. Fail-closed behavior for malformed configured paths.
4. No silent record duplication.
5. Parent-context inheritance only when explicitly configured.
6. Existing flat JSON-feed configurations remain behaviorally unchanged.
7. Existing pagination semantics remain unchanged unless this feed genuinely requires a separately generalized mechanism.
8. Generic field mapping continues to drive `ListingFacts` / normalized record construction.
9. Adapter remains persistence-agnostic.

## Offline fixtures and tests

Add synthetic fixtures covering:

- one-level nested records;
- nested records with parent-context inheritance;
- multiple parent groups;
- missing child collection;
- malformed child collection;
- duplicate child IDs;
- flat-feed backwards compatibility;
- stable deterministic ordering/fingerprinting;
- configured path failure visibility.

Add a bounded Mews fixture derived from public source shape without copying unnecessary full vacancy text.

## Pre-onboarding zero-detail verification

After implementing the generic extension, rerun a zero-detail Mews inventory validation before changing production configuration.

Require:

- complete inventory;
- deterministic rerun equality;
- no duplicate external identities;
- expected listing count explainable against the public source;
- valid titles and URLs;
- listing geography evidence sufficient to reproduce the SPEC-014 11-in-scope / 17-foreign result or clearly explain a legitimate source change;
- zero detail calls;
- zero Phase 2 writes.

If these fail, do not onboard Mews.

## Production onboarding

If the zero-detail gate passes, add Mews declaratively to production `config/companies.yaml` using the generalized nested-feed contract.

Run Mews only through the normal production ingestion/state architecture.

Requirements:

- complete inventory attempted;
- details retrieved only as required by the normal source contract;
- Phase 2 persistence through existing repository/state abstractions;
- no refresh of unrelated employers merely for this experiment;
- no semantic assessment;
- no mutation of existing semantic cache;
- lifecycle authority remains complete inventory only;
- preserve and report incomplete/error evidence.

If bounded-source execution from SPEC-015 exists, reuse it rather than inventing another source-isolation mechanism.

## Coverage-delta comparison

Measure Mews against the post-SPEC-015 production baseline.

Report at least:

### Source operation

- inventory count;
- detail selected/skipped;
- detail success/failure;
- request count;
- elapsed time;
- usable normalized details;
- source completeness;
- active identities created/reused;
- lifecycle anomalies.

### Market usefulness

- Mews OpportunityClusters;
- routed clusters;
- `IN_SCOPE / UNCERTAIN / OUT_OF_SCOPE` after detail;
- proportion routed;
- proportion `IN_SCOPE`;
- target-family title-supported and description-only signals;
- business/data analytics;
- decision support/intelligence;
- business/strategy operations;
- AI/digital transformation;
- product/product strategy;
- commercial/revenue/insights adjacency where already represented by frozen SPEC-013 classifier.

### Portfolio diversification

Before vs after:

- configured employers;
- employers contributing usable detail;
- employers contributing routed clusters;
- routed top-1/top-3/top-5 shares;
- routed HHI;
- effective employer breadth.

Use the same concentration and role-family calculations as SPEC-013/015.

## Engineering-value comparison

The final report must explicitly compare:

```text
SPEC-015
configuration-only engineering cost
→ 3 employers
→ 56 jobs
→ 51 routed clusters
→ modest target-family improvement

SPEC-016
small generic adapter-extension cost
→ Mews
→ observed useful-market delta
```

Do not attempt a false precision ROI formula if engineering effort cannot be measured credibly. Qualitatively classify the adapter extension as one of:

- `HIGH_REUSABLE_SOURCE_VALUE`
- `MODERATE_REUSABLE_SOURCE_VALUE`
- `LOW_REUSABLE_SOURCE_VALUE`
- `CONTRACT_NOT_GENERALIZABLE`

Consider both immediate Mews value and whether the capability plausibly unlocks other nested first-party JSON feeds without bespoke code.

## Keep/remove decision

At the end classify Mews production status as:

- `KEEP_CONFIGURED`
- `REMOVE_LOW_VALUE`
- `REMOVE_CONTRACT_FAILURE`

Do not keep a technically functioning source solely because engineering work has already been invested.

## Semantic compute boundary

No Luna calls.

Report only diagnostic semantic burden:

- number of newly routed Mews clusters lacking compatible semantic assessment;
- optional projected cost using the existing frozen per-call estimate if directly reusable.

Do not promote or alter compute-allocation policy.

## Research fingerprint correction

SPEC-014 established that the prior Mews Greenhouse research fingerprint is stale.

Do not silently rewrite historical research evidence. If the project has a current source-discovery registry separate from immutable historical research, record the current first-party `/api/careers` source there with provenance and date. Otherwise document the correction in the experiment/report only.

## Documentation and experiment memory

Create a new experiment identity and repository-safe aggregate receipt.

Update as appropriate:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `README.md`
- `experiments/registry.yaml`
- SPEC-016 status

Keep detailed vacancy evidence and operational SQLite local/private.

## Acceptance criteria

Machine/architecture gates:

- generic nested-feed fixture tests pass;
- all existing flat JSON-feed tests remain unchanged/passing;
- no employer-specific branch exists in shared adapter behavior;
- zero-detail Mews preflight is complete/deterministic;
- bounded production Mews run completes safely if preflight passes;
- unrelated employers are not refreshed;
- zero semantic calls;
- existing semantic assessments unchanged;
- no false closure on incomplete inventory;
- operational state mutations are limited to normal Mews ingestion after approval gate inside the packet;
- full offline suite passes;
- `git diff --check` passes.

Evidence gates:

- actual Mews useful-market contribution is quantified;
- portfolio breadth delta is quantified;
- target-role-family contribution is quantified;
- adapter-extension reusability is assessed honestly;
- keep/remove decision is explicit.

## Stop conditions

Stop before production onboarding if:

- feed cannot be represented generically without employer-specific shared-adapter logic;
- inventory completeness cannot be established;
- stable external identity cannot be established;
- zero-detail observed source shape materially contradicts SPEC-014 and cannot be explained;
- unrelated code/config divergence is discovered.

Stop and report rather than expanding into Wave B, Erste, Zentiva, semantic tuning, or UI work.

## Deliverable

Return a structured report containing:

A. starting repository/state integrity;
B. current Mews source-contract reconstruction;
C. generic nested-feed contract design;
D. files/code changed;
E. synthetic and Mews fixture coverage;
F. zero-detail preflight result;
G. production configuration change if gate passed;
H. bounded production ingestion result;
I. lifecycle/state integrity;
J. Mews market-status distribution;
K. target-role-family contribution;
L. portfolio concentration delta;
M. comparison with SPEC-015 source economics;
N. adapter-extension reusability verdict;
O. Mews keep/remove recommendation;
P. semantic-call/cost diagnostic without calls;
Q. privacy/evidence boundary;
R. validation/tests;
S. recommended next packet;
T. recommended commit message.

No commit or push until normal owner/ChatGPT approval after review.
