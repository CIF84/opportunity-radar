# SPEC-003 — High-confidence Opportunity Clustering and Preferred Variant

## Status

`IMPLEMENTED_AWAITING_APPROVAL`

## Purpose

Implement the next bounded Phase 4 slice: candidate-independent, high-confidence `OpportunityCluster` construction plus deterministic candidate-dependent preferred-variant selection.

This packet follows the accepted Phase 4 specification and the implemented market-routing boundary. Before implementation, read the repository control plane, especially:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING_MODEL.md`
- `docs/decisions.yaml`
- Phase 4 in `SPEC.md`
- prior Phase 4 work packets

Preserve all frozen Phase 1–3 invariants and the implemented Slice 1–3 behavior.

## Objective

Stop treating multiple location/source variants of one human opportunity as multiple independent shortlist opportunities.

Required conceptual separation:

```text
JobInstance
  = source posting identity and independent lifecycle

OpportunityCluster
  = high-confidence grouping of postings representing one human opportunity

PreferredVariant
  = candidate-dependent choice of the best currently viable member

ApplicationIntent
  = later human decision; not implemented here
```

Never merge or rewrite `JobInstance` identities to solve opportunity identity.

## Scope

Implement:

1. a pure/deterministic high-confidence clustering layer;
2. auditable cluster evidence and deterministic cluster fingerprints;
3. candidate-dependent preferred-variant selection using existing market assessments and eligibility evidence;
4. cluster-aware normal ranking/sample preparation only where required to ensure one human opportunity appears once;
5. regression coverage for the known Kiwi and WPP duplicates;
6. immutable/run-manifest evidence sufficient for later retrospective replay.

Prefer no SQLite migration. If a migration appears necessary, stop and report why rather than introducing one silently.

## Non-goals

Do NOT implement:

- fuzzy/probabilistic general entity resolution;
- embedding/vector similarity;
- model-based clustering;
- cross-employer clustering;
- automatic application intent;
- manual cluster overrides unless needed only as an explicit test fixture mechanism;
- decision preferences;
- seniority guard changes;
- semantic-v2;
- scoring-weight changes;
- Phase 2 identity/lifecycle changes;
- UI;
- external actions;
- external semantic calls.

## OpportunityCluster contract

Use repository naming conventions, but conceptually expose:

```text
OpportunityCluster
- cluster_id
- company_id
- canonical_role_identity
- member_job_instance_ids
- cluster_fingerprint
- clustering_method
- clustering_evidence
```

Properties:

- candidate-independent membership;
- employer-scoped;
- deterministic;
- reproducible from the same member evidence;
- auditable;
- independent from member lifecycle;
- independent from semantic assessment identity.

A cluster may contain one member. Singleton clusters are valid and simplify downstream handling.

## High-confidence membership rule

Do not cluster on title alone.

Require same employer plus at least two strong independent signals supporting shared human opportunity identity.

Strong signals may include:

- exact normalized title;
- explicit shared source requisition/campaign/variant identity when available;
- highly equivalent core responsibilities and requirements using deterministic normalized evidence;
- source URL structure explicitly indicating location variants;
- differences primarily limited to geography, compensation, legal/local boilerplate, or other declared variant fields.

Use existing normalized/persisted evidence where possible.

Do not inspect opaque adapter metadata unless it is already a governed normalized source of variant identity.

If deterministic evidence is ambiguous, leave jobs separate.

False split is preferable to false merge for this first implementation.

## Description evidence

The Phase 4 audit observed:

- Kiwi variants with description similarity approximately 0.89–0.98;
- WPP NY/Chicago variants with approximately 99.87% similarity.

Do NOT turn these observations into a broad fuzzy threshold engine.

If description equivalence is used, implement a bounded deterministic `core_description_signature` or similarly explainable normalization that removes only clearly declared variant/local boilerplate. Do not use embeddings or probabilistic similarity.

If the existing preserved evidence cannot safely produce such a signature for Kiwi without overfitting, use other strong signals and document the limitation.

## Required regression cases

### Kiwi Senior Business Analyst — Inventory

Known reviewed variants:

- Bratislava
- Brno
- Barcelona
- Prague

Expected:

- one `OpportunityCluster` when preserved evidence supports the high-confidence rule;
- all four underlying `JobInstance` records remain independent;
- Prague/Czech variant becomes preferred under the current candidate policy;
- shortlist/application-attention representation counts the cluster once.

If the preserved evidence proves that one named member is not actually equivalent, report the evidence rather than forcing the expected historical annotation.

### WPP Growth Consulting

Known reviewed variants:

- New York
- Chicago

Expected:

- one cluster when current preserved evidence supports equivalence;
- both underlying JobInstances remain independent;
- because both are currently `OUT_OF_SCOPE` for the candidate, the cluster must not enter the normal shortlist merely because it exists.

### False-merge controls

Required:

- same employer + same title + materially different core responsibilities → separate clusters;
- same employer + similar standardized boilerplate but different role identity → separate clusters;
- different employer + identical title → always separate clusters.

## Cluster identity and fingerprint

Cluster identity must be deterministic and stable for the same high-confidence membership set and clustering contract.

Prefer an identity derived from:

- company identity;
- clustering contract/version;
- sorted stable member/source identity evidence or canonical role identity.

Do not include candidate policy in cluster membership identity.

Cluster fingerprint should change when membership/evidence materially changes.

Do not invalidate member semantic assessments when cluster membership changes.

## Lifecycle semantics

Member lifecycle remains authoritative and independent.

Required behavior:

- closing one member does not close sibling members;
- a cluster remains actionable while at least one viable member is active;
- a closed member may remain part of historical cluster evidence but cannot be selected as the current preferred active variant;
- clustering must never emit Phase 2 lifecycle events;
- clustering must never rewrite `current_fingerprint`, `latest_observation_id`, or detail reuse evidence.

## Preferred variant

Preferred-variant selection is candidate-dependent and deterministic.

Inputs should include:

- active cluster members;
- `CurrentCandidateMarketAssessment`;
- hard eligibility where applicable;
- current candidate market-access policy;
- evidence completeness/currentness;
- deterministic tie-break fields.

Priority:

1. viable `IN_SCOPE` members;
2. viable `UNCERTAIN` members;
3. `OUT_OF_SCOPE` members only as non-actionable evidence when no viable member exists.

Within `IN_SCOPE`, prefer the candidate's explicitly compatible location/arrangement. For the current candidate, the Prague Kiwi variant must beat Bratislava/Barcelona and should beat a less preferred/less certain variant.

Do not invent a universal preference between Prague onsite/hybrid and confirmed Czech-compatible remote if candidate policy does not define one.

Use evidence completeness/currentness and deterministic stable tie-breaks after policy-relevant distinctions.

Return structured `variant_ranking_reason` / evidence rather than an opaque choice.

## Routing/ranking integration

The normal candidate shortlist should operate on one opportunity-level representative rather than all members.

Required behavior:

- one cluster contributes at most one normal shortlist row;
- the row uses the preferred viable member's existing semantic assessment/composite as its member-level fit evidence;
- existing semantic assessments are reused unchanged;
- if preferred member changes to another member that already has a compatible cached semantic assessment, use it;
- do not synthesize/average semantic scores across members in this slice;
- if a newly preferred member lacks required semantic assessment, preserve the existing semantic-processing policy rather than calling a model in offline tests;
- an all-`OUT_OF_SCOPE` cluster is absent from the normal shortlist;
- an `UNCERTAIN` preferred member retains the implemented maximum `REVIEW` cap.

Do not change scoring weights or semantic-v1.

## Semantic-call and cache guarantees

Offline implementation and validation must make zero external semantic calls.

Tests must prove:

- cluster creation does not invalidate member semantic caches;
- preferred-variant changes do not rewrite semantic assessments;
- cluster fingerprint is outside semantic cache identity;
- known cached assessments remain reusable;
- clustering/ranking can be replayed from persisted evidence without model calls where compatible assessments already exist.

## Persistence

For this experiment, prefer computed cluster objects plus immutable run/replay manifest evidence.

Do not add operational SQLite cluster tables unless the current Phase 4 spec proves they are required now.

If manifests are extended, preserve:

- cluster ID/fingerprint;
- member IDs;
- clustering method/evidence;
- preferred member;
- variant-selection reasons;
- market status per member;
- reused semantic assessment IDs where applicable.

Historical validation v1 evidence remains immutable.

## Validation-unit implications

Do not rewrite official v1 metrics in this slice.

Add deterministic helpers/tests sufficient for later Phase 4 retrospective replay to distinguish:

- posting count;
- opportunity-cluster count;
- preferred variant;
- human application intent (future/historical annotation only).

Known Kiwi four-posting group should count as one opportunity for new cluster-aware derived metrics.

## Tests

Add focused tests for at least:

### Membership

- Kiwi known variants cluster when evidence supports it;
- WPP known variants cluster when evidence supports it;
- same title/different duties does not cluster;
- cross-employer identical titles do not cluster;
- singleton cluster is valid;
- ordering of input members does not change cluster identity.

### Preferred variant

- Prague Kiwi member wins under current candidate policy;
- `IN_SCOPE` beats `UNCERTAIN`;
- `UNCERTAIN` beats `OUT_OF_SCOPE` as current representative;
- closed member cannot be current preferred variant;
- deterministic tie-break is stable.

### Lifecycle/cache

- closing one member does not close siblings;
- clustering creates no Phase 2 events;
- member semantic assessment IDs remain unchanged;
- cluster-policy/member-order changes cause zero semantic reassessments;
- SQLite schema remains v3.

### Routing

- clustered Kiwi appears once in normal shortlist;
- all-out-of-scope WPP cluster appears zero times;
- uncertain preferred member remains capped at REVIEW;
- unclustered/singleton opportunities preserve existing routed behavior.

## Documentation

Update only what is needed to preserve current truth after implementation:

- `docs/STATUS.md`;
- `docs/ARCHITECTURE.md`;
- relevant Phase 4 implementation markers in `SPEC.md`;
- this work packet's status/result notes if the repository convention uses them.

Do not claim preference-aware decision behavior exists.

## Validation

Run:

```bash
.venv/bin/pytest -q
git diff --check
```

No live source calls.
No external semantic calls.
No commit until human approval.

## Deliverable

Return:

A. files changed
B. cluster contract
C. high-confidence membership rule actually implemented
D. Kiwi/WPP regression evidence and results
E. false-merge controls
F. preferred-variant policy/results
G. shortlist integration behavior
H. lifecycle/cache guarantees
I. persistence/manifest decision
J. full offline validation result
K. ambiguities/evidence limitations
L. recommended next work packet
M. recommended commit message

Do not commit or push until explicit approval.

## Implementation result

Implemented in the current worktree with no SQLite migration and no external
semantic calls. The clustering rule requires same employer, exact normalized
title, exact bounded core-description signature, compatible explicit role
metadata, and an observable location/work-arrangement or localized-copy
variant. Preferred selection applies current market status, explicit candidate
policy compatibility, evidence/detail currentness, and a stable identity
tie-break. New immutable validation batches record cluster/member/preferred
evidence; historical v1 artifacts remain unchanged.

Repository-only replay over the 406 compatible assessed active postings found
394 clusters and 315 normal-shortlist clusters. The four preserved Kiwi
Inventory postings form one cluster with the Prague member preferred; the two
WPP Growth Consulting postings form one all-`OUT_OF_SCOPE` cluster and remain
absent from the normal shortlist. Validation completed with 163 offline tests
passing and 18 live tests deselected; `git diff --check` passed. Promotion
remains a separate human decision.
