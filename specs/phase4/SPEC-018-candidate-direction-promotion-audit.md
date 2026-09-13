# SPEC-018 — Candidate Direction Promotion Audit

Status: `IMPLEMENTED_LOCALLY_AWAITING_REVIEW`

## Purpose

Audit whether explicit human career-direction evidence accumulated during Phase 4 justifies a new versioned candidate decision-preference representation.

This packet is about **decision direction**, not capability inflation, semantic tuning, or autonomous preference learning.

The candidate has explicitly clarified that business/data/decision-analytics is a viable career direction when it is business-facing and connected to AI/transformation, and the completed 60-item human review exposed additional repeated distinctions between attractive manageable stretch, implausible requalification, unwanted role families, and low-future-value work.

The audit must determine which of those observations are already represented, which are missing, and which are too contextual or unstable to promote.

## Governing model

Keep these concepts separate:

```text
CAPABILITY
what the candidate can plausibly do now

DIRECTION / PREFERENCE
what kind of work is attractive now

STRETCH
how far an opportunity sits beyond current capability

CONVICTION
belief about future value of a type of work

HARD ELIGIBILITY
whether the opportunity is practically possible
```

A preference must not fabricate capability.
A capability gap must not automatically imply aversion.
A conviction about future automation must not silently become a hard exclusion.
A single human rejection must not automatically become a durable preference.

## Existing candidate evidence

The current candidate profile already represents strong capability evidence for:

- `business_analytics` — EXPERT / HIGH;
- `decision_support` — EXPERT / HIGH;
- `forecasting` — EXPERT / HIGH;
- `business_operations` — EXPERT / HIGH;
- `commercial_strategy` — EXPERT / HIGH;
- `transformation` — ADVANCED / HIGH;
- `ai_strategy` / `ai_adoption` — INTERMEDIATE;
- developing SQL/Python/technical depth.

It also already expresses role-characteristic interest in analytical problem solving, decision intelligence, AI-enabled work, strategy, business operations, transformation, autonomy, cross-functional work, and continuous learning.

The separately fingerprinted Phase 4 decision preferences currently include strong positive AI-enabled work, transformation execution, implementation ownership; positive business operations, product development, continuous learning; and several negative concepts.

Therefore SPEC-018 must not assume that a newly stated direction is missing merely because a specific `decision_preferences` entry is absent.

## Human direction to audit

At minimum audit the following explicit human evidence from the completed Phase 4 work and accepted project direction:

### Positive / attractive directions

1. Business/data/decision analytics is a viable career direction when business-facing and connected to broader AI/transformation work.
2. Extensive past value came from turning messy data into clear insights and informed business decisions.
3. AI transformation roles are highly attractive even when they represent a manageable stretch.
4. AI-assisted software development is a plausible future direction; conventional software-engineering identity is less directly aligned.
5. Product/implementation ownership can be attractive where it creates real business outcomes.
6. Pharma/healthcare and robotics are not intrinsically unattractive; individual roles may fail because of qualification or market constraints.

### Negative / avoidance evidence

1. B2B account management / account executive work has repeatedly been rejected and the candidate explicitly does not want to return to account management.
2. Technical/customer support is not an intended career direction.
3. Generic testing/QA is not an intended career direction and carries a stated automation/future-value concern.
4. Mundane administrative/back-office work with high perceived automation exposure is unattractive.
5. Pure advisory work without implementation ownership is already represented negatively and should remain distinct from transformation consulting with implementation responsibility.

### Stretch evidence

Observed WORTH cases in the frozen 60-item experiment were all opportunities where desired direction was strong but qualification fit was uncertain enough that deeper reasoning had decision value.

Observed NOT_WORTH cases included both:

- attractive domains with an obviously excessive specialized capability gap;
- unattractive role families where capability might otherwise be sufficient.

The audit must preserve that distinction.

## Source-of-truth boundary

Do not infer new durable preferences solely from assistant summaries.

Use only durable repository evidence and explicit human judgments/accepted directions already represented in project artifacts available to the implementation environment. If private human notes are available locally, they may be analyzed read-only but must remain private and must not be copied into repository-safe artifacts.

If a proposed preference cannot be grounded in explicit human evidence, classify it as `INSUFFICIENT_EVIDENCE`.

## Audit output contract

For every candidate concept considered, produce one of:

- `ALREADY_REPRESENTED_SUFFICIENTLY`
- `PROMOTE_STRONG_POSITIVE`
- `PROMOTE_POSITIVE`
- `PROMOTE_NEGATIVE`
- `KEEP_CONTEXTUAL_ONLY`
- `KEEP_AS_CONVICTION_ONLY`
- `INSUFFICIENT_EVIDENCE`
- `REJECT_CAPABILITY_CONFUSION`

For each decision record:

- canonical concept ID or proposed concept ID;
- evidence category;
- existing representation if any;
- proposed source type (`PREFERENCE` or `CONVICTION`) if promotion is recommended;
- proposed stance;
- concise rationale;
- whether matching taxonomy/rules already support the concept;
- whether adding the concept would require a matching-rule/taxonomy extension;
- fingerprint/cache implications.

## Business analytics / decision support decision

Explicitly answer whether these should be added to versioned `decision_preferences`:

- `business_analytics`
- `decision_support` or a canonical `decision_intelligence` concept

Do not double-count semantically equivalent concepts merely because both profile capabilities and role-characteristic preferences exist.

The question is not whether the candidate possesses these capabilities — that is already established. The question is whether the Phase 4 decision layer should explicitly reward opportunities containing them after semantic/base scoring.

If promotion is recommended, justify whether `POSITIVE` or `STRONG_POSITIVE` is appropriate under the frozen effect policy.

## AI transformation decision

Audit whether the current combination of:

- `ai_enabled_work` STRONG_POSITIVE;
- `transformation_execution` STRONG_POSITIVE;
- `implementation_ownership` STRONG_POSITIVE;

already represents the repeatedly observed attraction to AI transformation roles.

Prefer avoiding redundant concepts if the existing representation is sufficient.

## Account-management decision

Audit repeated explicit human rejection of account-management/account-executive work.

Distinguish at least:

- account management / account executive ownership;
- general commercial strategy;
- sales/revenue operations;
- customer-retention strategy;
- business development;
- customer-service operations.

Do not accidentally penalize the candidate's valuable historical commercial/retention capabilities merely because returning to account-management execution is unattractive.

If a new negative concept is justified, it must be narrowly defined and taxonomy-backed.

## Automation/future-value convictions

The candidate repeatedly expressed concern about roles perceived as highly automatable or structurally threatened by AI, including some testing, mundane operational administration, and conventional software work.

Do **not** convert this into a broad `automation_risk` negative preference without evidence that such a concept can be matched reliably and without suppressing attractive AI-assisted or transformation work.

Audit whether any of these should remain contextual human reasoning, become a narrow `CONVICTION`, or be deferred entirely.

Sentiment is allowed to change over time. Any promoted conviction/preference must remain versioned and reversible.

## Stretch-envelope architecture

Do not implement stretch scoring in SPEC-018.

Instead produce a bounded architecture note defining the future distinction:

```text
CURRENT FIT
candidate clearly meets core role requirements

MANAGEABLE STRETCH
important capability gaps exist, but transferable experience and desired trajectory make deeper assessment valuable

EXCESSIVE STRETCH
core profession/seniority/domain requires substantial requalification before candidacy is realistic
```

The note must identify what evidence would be needed to classify stretch without using preference as a proxy for capability.

Do not introduce a new runtime recommendation or score in this packet.

## Counterfactual replay

Before promoting any preference change, run a deterministic zero-semantic-call counterfactual over:

1. the frozen 60-item semantic compute-worthiness sample where evidence permits;
2. the current compatible cached semantic population;
3. any frozen Phase 4 retrospective evidence required by existing decision-preference invariants.

For proposed preference changes report:

- number of opportunities receiving each new effect;
- score/rank/recommendation changes;
- whether any known human WORTH/APPLY evidence is demoted;
- whether known explicit aversions move in the intended direction;
- overlap/double-counting with existing preference concepts;
- effect clipping frequency;
- semantic reassessments required: must be zero.

Do not tune effect weights. The existing frozen mapping remains:

```text
STRONG_POSITIVE +0.4
POSITIVE        +0.2
NEUTRAL          0.0
NEGATIVE        -0.3
aggregate bound [-1.0, +1.0]
```

## Promotion rule

This packet may implement a new candidate preference version only if the audit shows all of the following:

1. explicit repeated human evidence;
2. concept is not already represented sufficiently;
3. concept can be matched narrowly enough to avoid obvious collateral effects;
4. counterfactual replay reveals no material contradiction with known positive evidence;
5. semantic-profile and Phase 3 scoring fingerprints remain unchanged;
6. only decision-preference/effective-decision-policy/full-profile fingerprints change;
7. zero semantic reassessments are required.

If these conditions are not met, stop at an audit recommendation and do not edit the candidate preference version.

## Candidate portability

Any schema/taxonomy/matching change must remain generic across candidate profiles.

Do not add `if roman_christov` logic or encode employer-specific/candidate-specific behavior into shared matching code.

The portability candidate must continue to load under the same schema. Its preference values need not mirror the primary candidate.

## Privacy

Human notes and per-opportunity private evidence remain local/ignored.

Repository-safe artifacts may contain:

- aggregate concept decisions;
- counts;
- fingerprints;
- generic architecture conclusions;
- sanitized counterfactual metrics;
- accepted preference concept IDs and stances.

Do not publish raw human notes, vacancy titles/URLs tied to judgments, or private candidate evidence beyond what is already intentionally committed in generic candidate configuration.

## Protected invariants

Do not change:

- semantic-v1 model/prompt/reasoning/contract;
- Phase 3 scoring weights;
- market-access policy or market-status rules;
- source configuration;
- clustering semantics;
- seniority guard;
- historical judgments;
- SPEC-008 protocol;
- semantic cache records;
- Phase 1/2 lifecycle/identity contracts.

No external semantic or live-source calls are authorized.

## Documentation

Update as appropriate:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `README.md`
- `docs/decisions.yaml`
- `experiments/registry.yaml`
- SPEC-018 implementation status

Clearly distinguish promoted candidate state from audit-only future architecture.

## Tests

Add regression coverage proving at least:

- candidate schema remains generic;
- semantic-profile fingerprint unchanged;
- Phase 3 scoring-preference fingerprint unchanged;
- market-policy fingerprint unchanged;
- preference changes alter only intended decision-policy/full-profile identities;
- zero semantic calls/reassessments;
- no lifecycle/source/clustering changes;
- no duplicate preference contribution through synonyms/related concepts;
- narrow account-management matching does not penalize sales operations, commercial strategy, or customer-retention strategy unless evidence explicitly matches the promoted concept;
- business analytics/decision-support matching does not double-count equivalent evidence;
- portability profile remains valid;
- counterfactual replay is deterministic;
- repository-safe output excludes private human notes.

Run full offline suite and `git diff --check`.

## Stop conditions

Stop for human decision rather than improvising if:

- canonical concept boundaries are ambiguous;
- a proposed concept requires broad fuzzy matching;
- counterfactual replay demotes known positive human evidence unexpectedly;
- promotion would require changing semantic-v1 or scoring weights;
- private human evidence cannot be accessed sufficiently to support a claimed repeated preference;
- multiple plausible preference representations have materially different behavior.

## Implementation result

Run `spec018-candidate-direction-20260913-v1` completed the approved audit with
zero external calls and zero SQLite writes. All ten promotion gates passed for
one narrow change: candidate profile version 4 / decision-preference version 2
adds `account_management_execution` as a negative preference, matched only from
explicit account-management/account-executive title evidence.

The frozen 60-item sample contained four title matches, all human-labeled
`NOT_WORTH_DEEP_ASSESSMENT`; no WORTH evidence was demoted. One of 20 current
compatible cached opportunities changed score, none changed recommendation,
and three relative ranks changed. The frozen 30-posting retrospective had zero
matches and no score, recommendation, cluster, or human-APPLY change. Semantic
reassessments were zero.

Business/decision analytics, AI transformation, AI-assisted development, and
implementation ownership remain represented by existing capability, semantic
preference, goal, and decision-preference evidence. Broader technical-support,
QA/testing, automation-risk, and stretch policies were not promoted.

The implementation remains uncommitted pending normal promotion review. See
`docs/candidate_direction_promotion_audit.md` and the sanitized aggregate receipt
indexed by `experiments/registry.yaml`.

## Deliverable

Return a structured report containing:

A. evidence sources inspected;
B. current candidate representation;
C. concept-by-concept audit table;
D. business analytics / decision-support verdict;
E. AI-transformation redundancy verdict;
F. account-management verdict;
G. automation/future-value conviction verdict;
H. stretch-envelope architecture note;
I. counterfactual replay results;
J. fingerprint/cache implications;
K. promoted changes, if gates permit;
L. rejected/deferred changes;
M. portability/privacy/invariant checks;
N. tests and validation;
O. files changed;
P. recommended next packet;
Q. recommended commit message.

No commit or push until normal review approval.
