# SPEC-018 Candidate Direction Promotion Audit

Status: `IMPLEMENTED_LOCALLY_AWAITING_REVIEW`

Experiment: `EXP-CANDIDATE-DIRECTION-001`
Run: `spec018-candidate-direction-20260913-v1`

## Result

The audit supports one bounded candidate preference promotion:

```text
account_management_execution  PREFERENCE  NEGATIVE
```

Candidate profile version 4 and decision-preference version 2 implement that
single addition. The matcher is deliberately title-only: it recognizes explicit
account-manager, account-management, and account-executive role ownership while
leaving sales/revenue operations, commercial strategy, customer-retention
strategy, and business development neutral unless the title itself establishes
account-management execution.

All ten promotion gates passed. No semantic or live-source calls were made and
the operational SQLite database remained byte-identical.

## Evidence inspected

- the accepted SPEC-018 direction statement;
- candidate profile, taxonomy, preference rules, and frozen effect policy;
- the frozen 60-item semantic compute-worthiness manifest and complete private
  append-only judgments;
- the current compatible cached-semantic population;
- the frozen 30-posting Phase 4 retrospective evidence;
- existing market, clustering, seniority, lifecycle, and cache contracts.

Raw human notes, vacancy titles/URLs tied to judgments, cluster identities, and
per-opportunity effects remain private/local.

## Current representation

The profile already carries strong capability facts for business analytics,
decision support, forecasting, business operations, commercial strategy, and
transformation. Semantic-v1 also receives VERY_HIGH analytical-problem-solving
and decision-intelligence preferences plus strategic goals for AI-enabled work
and decision quality.

The Phase 4 decision layer already applies strong positive effects for AI-enabled
work, transformation execution, and implementation ownership, along with
bounded positive/negative preferences. Capability and direction remain separate.

## Concept audit

| Concept | Verdict | Result |
|---|---|---|
| `business_analytics` | `ALREADY_REPRESENTED_SUFFICIENTLY` | Another post-semantic effect would double count existing capability, semantic preference, and goal evidence. |
| `decision_intelligence` | `ALREADY_REPRESENTED_SUFFICIENTLY` | Already a VERY_HIGH semantic role-characteristic preference and strategic direction. |
| `ai_enabled_work` | `ALREADY_REPRESENTED_SUFFICIENTLY` | Existing AI, transformation, and implementation effects capture the repeated attraction. |
| `ai_assisted_development` | `ALREADY_REPRESENTED_SUFFICIENTLY` | Existing capability and AI-enabled direction preserve the bounded trajectory without rewarding conventional software identity. |
| `implementation_ownership` | `ALREADY_REPRESENTED_SUFFICIENTLY` | Already strong positive. |
| `account_management_execution` | `PROMOTE_NEGATIVE` | Repeated explicit aversion, absent from current policy, and safely title-matchable. |
| `customer_service_operations` | `ALREADY_REPRESENTED_SUFFICIENTLY` | Already negative. |
| `technical_support` | `INSUFFICIENT_EVIDENCE` | Explicit but not repeated enough in the frozen sample for promotion. |
| `software_testing_qa` | `KEEP_CONTEXTUAL_ONLY` | Current evidence combines role aversion and future-value belief in one case. |
| `mundane_administrative_automation_exposure` | `KEEP_AS_CONVICTION_ONLY` | Repeated concern exists, but no narrow reliable matcher yet exists. |
| `advisory_without_implementation_ownership` | `ALREADY_REPRESENTED_SUFFICIENTLY` | Existing negative plus implementation-ownership override preserves the trade-off. |
| `healthcare` | `KEEP_CONTEXTUAL_ONLY` | Rejections concern qualification, not a general domain aversion. |
| `robotics` | `KEEP_CONTEXTUAL_ONLY` | Evidence supports openness, not a stable positive effect. |

## Required decisions

### Business analytics and decision support

Do not add new decision-preference effects. These directions are already
represented in semantic-v1 candidate inputs and capability facts. Adding both
`business_analytics` and `decision_support` would reward substantially equivalent
evidence more than once.

### AI transformation

Do not add an `ai_transformation` synonym. The existing combination of
`ai_enabled_work`, `transformation_execution`, and `implementation_ownership`
already expresses the desired distinction and supports trade-offs.

### Account management

Promote `account_management_execution` as a negative preference. It means owning
or executing an account-manager/account-executive role; it does not mean general
commercial strategy, sales operations, retention strategy, business development,
or merely collaborating with account managers.

### Automation and future value

Do not promote a broad automation-risk preference. The belief is real and may be
retained as contextual conviction evidence, but deterministic matching is not
yet reliable enough to distinguish mundane work from attractive AI-enabled
transformation. No runtime behavior changes here.

## Counterfactual replay

| Population | Size | New matches | Score changes | Recommendation changes | Known positive demotions |
|---|---:|---:|---:|---:|---:|
| Frozen compute-worthiness sample | 60 | 4 | not applicable | not applicable | 0 |
| Compatible cached semantic population | 20 | 1 | 1 | 0 | 0 |
| Frozen Phase 4 retrospective postings | 30 | 0 | 0 | 0 | 0 |

All four matched frozen-sample judgments were `NOT_WORTH_DEEP_ASSESSMENT`.
Three also had unrelated existing preference effects; each concept still
contributed at most once. In the current cached population, one opportunity
received the new effect, three relative ranks changed, and no recommendation
changed. Effect clipping remained zero. The retrospective retained 26
opportunities with unchanged cluster membership.

Semantic reassessments required: **0**.

## Fingerprints and cache

| Identity | Version 3 baseline | Version 4 candidate |
|---|---|---|
| Full profile | `67c459aa…5746e` | `9b220d73…89e9` |
| Decision preferences | `e0146d4d…c6a4` | `394342b4…59f5` |
| Preference matching rules | `ea20c4b3…d9b7` | `be517807…6a4` |
| Semantic profile | `6579b21e…19b` | unchanged |
| Phase 3 scoring preferences | `92374339…e8a` | unchanged |
| Market-access policy | `86c00d7c…bdb` | unchanged |

Only the full-profile and decision-layer identities change. Existing semantic-v1
assessments remain reusable.

## Stretch-envelope architecture note

SPEC-018 does not implement stretch scoring.

- **CURRENT FIT** requires job evidence for core requirements and candidate
  evidence showing they are currently met.
- **MANAGEABLE STRETCH** requires important gaps plus transferable experience
  and an independently desired direction that makes deeper assessment useful.
- **EXCESSIVE STRETCH** requires evidence that the core profession, seniority,
  or specialist domain would demand substantial requalification.

A future classifier would need explicit core job requirements, candidate
capability levels/confidence, transferable experience, profession/seniority
evidence, and candidate direction represented independently of capability.
Preference must never stand in for capability.

## Invariants and privacy

- The portability candidate still loads through the same generic schema.
- Matching is configuration/taxonomy-driven; there is no candidate-identity or
  employer branch in Python.
- Semantic-v1, reasoning, model, scoring weights, market policy, source config,
  clustering, seniority, lifecycle, and historical judgments are unchanged.
- The audit made zero external calls and zero SQLite writes.
- Detailed joins remain ignored; only the sanitized aggregate receipt is
  repository-eligible.

## Limitations

- The 60-item sample is exploratory and contains only three WORTH labels.
- Title-only matching favors precision and may miss account-management work
  hidden behind unrelated titles.
- The current compatible cache population is small and not an unbiased market
  sample.
- No stretch, automation-risk, or deterministic rejection policy is promoted.

## Recommendation

Promote candidate profile version 4 and decision-preference version 2 after
normal review. The next packet should specify the stretch evidence contract and
deterministic rejection boundary before changing semantic allocation. Do not
tune semantic-v1 or add a broad automation-risk matcher.

Recommended commit message: `Promote bounded candidate direction preference`.
