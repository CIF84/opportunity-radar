# SPEC-020 — Credential Semantics Human Validation

Status: `APPROVED_FOR_IMPLEMENTATION`

## Purpose

Validate the dominant uncertainty exposed by SPEC-019: whether degree/credential evidence is being interpreted as capability stretch when it should instead be distinguished as credential compatibility, substitutability, or ambiguity.

SPEC-019 found 171 current-corpus `EXCESSIVE_STRETCH` results, of which 144 were driven by mandatory-degree evidence. Before stretch can influence runtime compute allocation or rejection, this credential interpretation must be human-validated.

This packet creates a frozen, shadow-only human validation. It does not change runtime stretch classes, candidate capability, hard eligibility, ranking, recommendation, or semantic allocation.

## Governing distinction

Keep these objects separate:

```text
CAPABILITY DISTANCE
Can the candidate plausibly perform the work?

CREDENTIAL COMPATIBILITY
Does the vacancy explicitly require a formal credential the candidate lacks?

CREDENTIAL SUBSTITUTABILITY
Does the vacancy allow equivalent experience or otherwise make the credential non-absolute?

APPLICATION COMPETITIVENESS
How likely is the employer to accept the candidate despite a credential gap?
```

A missing degree is not automatically evidence that the candidate cannot perform the work.

## Frozen evidence basis

Use the SPEC-019 stretch rules and current operational snapshot as the source population, without changing their semantics.

Primary population:

- current opportunities classified `EXCESSIVE_STRETCH` with degree/credential evidence as a decisive reason;
- SPEC-019 reported 144 such current-corpus cases.

The preparation must verify the exact reproducible population against the current frozen-compatible state before sampling. If the count differs because operational state changed, record the difference and preserve a snapshot/fingerprint; do not silently claim the historical 144 still applies.

## Human-validation question

For each sampled vacancy, present the exact bounded qualification evidence needed to answer two separate questions:

### Question A — credential semantics

How should the employer's stated degree/credential requirement be interpreted?

Allowed labels:

- `HARD_CREDENTIAL`
- `DEGREE_OR_EQUIVALENT_EXPERIENCE`
- `PREFERRED_CREDENTIAL`
- `GENERIC_OR_NONDECISIVE_CREDENTIAL`
- `AMBIGUOUS_CREDENTIAL`
- `INVALID_OR_STALE_EVIDENCE`

Definitions:

`HARD_CREDENTIAL`
: The source clearly establishes the credential as mandatory, with no explicit equivalent-experience path and no evidence that the phrase is merely preferred/template context.

`DEGREE_OR_EQUIVALENT_EXPERIENCE`
: The source explicitly allows equivalent/relevant experience, comparable professional history, or another substitute.

`PREFERRED_CREDENTIAL`
: The credential is explicitly preferred/ideal/desirable rather than mandatory.

`GENERIC_OR_NONDECISIVE_CREDENTIAL`
: A degree appears in generic/template/contextual language but the displayed evidence does not establish it as a decisive gate for the role.

`AMBIGUOUS_CREDENTIAL`
: The available evidence is insufficient to classify safely.

`INVALID_OR_STALE_EVIDENCE`
: The vacancy/evidence is unavailable, materially inconsistent, or otherwise unsuitable for judgment.

### Question B — practical candidacy consequence

Given the displayed role requirements and the candidate's relevant professional-history summary, would the absence of a completed bachelor's degree by itself make candidacy unrealistic?

Allowed labels:

- `DEGREE_GAP_DECISIVE`
- `EXPERIENCE_PLAUSIBLY_SUBSTITUTES`
- `DEGREE_GAP_NOT_DECISIVE`
- `NEED_MORE_INFORMATION`

This question is not “would you apply?” and must not expose preference, recommendation, score, or semantic triage.

## Candidate evidence shown to the human

Show only a bounded, stable summary relevant to credential substitution, for example:

- approximately 20 years of technology/business experience;
- senior leadership/executive decision-support history;
- relevant domain/capability evidence for the sampled role where available;
- no completed bachelor's degree;
- current developing technical skills only where relevant.

Do not show hidden model scores, recommendations, preference effects, or the current stretch classification.

Do not exaggerate candidate evidence to make substitution appear more plausible.

## Blindness

The review packet must not reveal:

- `EXCESSIVE_STRETCH` label;
- stretch reason code beyond the source credential sentence itself;
- triage stratum;
- semantic score;
- recommendation;
- cache status;
- whether a case is expected to prove/disprove the current rule;
- aggregate interim results while review is incomplete.

Review order must be deterministic and frozen.

## Sample design

Target 50 reviewed cases if the verified population supports it.

Use deterministic stratification to avoid a sample dominated by one employer or one wording pattern.

Stratify where evidence permits across:

- employer;
- role-family/profession category;
- credential wording pattern;
- explicit years/seniority context;
- degree-only versus degree-plus-other decisive stretch reasons.

Employer cap target: no more than 5 effective reviewed items per employer. If mathematically infeasible, prove the minimum relaxation required before freezing the sample.

Create at least 5 frozen same-stratum reserves for each major sampling stratum or a documented equivalent reserve strategy.

Historical human judgments from SPEC-012 must not influence selection.

## Qualification excerpt contract

The blind packet should show:

- employer;
- role title;
- location/work mode only if useful for orientation, but not market assessment;
- exact credential/education sentence(s);
- a bounded surrounding qualification excerpt sufficient to interpret mandatory/preferred/equivalent wording;
- relevant explicit years/professional requirements;
- bounded candidate professional-history summary;
- source URL for human verification where still available;
- evidence gaps.

Do not dump full job descriptions unless needed.

Preserve source wording exactly for the qualification evidence; do not paraphrase away modal words such as `must`, `required`, `preferred`, `or equivalent experience`, `ideally`, etc.

## Replacement policy

Use append-only frozen replacement semantics similar to SPEC-012:

- if evidence is materially wrong before judgment, invalidate and replace with the next frozen compatible reserve;
- if a vacancy simply becomes unavailable and the human can still judge the frozen qualification evidence, allow judgment unless the human explicitly says evidence is insufficient;
- never regenerate/resample the experiment after human review starts;
- preserve replacement chain and reason.

## Human record contract

Record Question A and Question B separately with optional controlled reasons and private notes.

Human notes remain private/local.

Support supersession/correction without deleting prior records.

No model may infer a missing human label.

## Evaluation metrics

After all reviews are complete, report at minimum:

### Credential semantics distribution

Counts/rates for:

- hard credential;
- degree-or-equivalent;
- preferred;
- generic/nondecisive;
- ambiguous;
- invalid/stale.

### Current-rule precision

Among cases currently treated as degree-driven excessive stretch, what fraction do humans judge as genuinely hard/decisive credential barriers?

Report at least two views:

1. strict: `HARD_CREDENTIAL` + `DEGREE_GAP_DECISIVE`;
2. broader: any human result supporting credential-based candidacy failure.

### False-excessive risk

How often would the current degree rule classify excessive stretch where:

- equivalent experience is explicitly allowed;
- degree is only preferred;
- credential is generic/nondecisive;
- human judges experience plausibly substitutes or degree gap is not decisive.

### Ambiguity

Report `AMBIGUOUS_CREDENTIAL` and `NEED_MORE_INFORMATION` rates separately. Ambiguity is not a negative result.

### Employer/role-family effects

Report bounded aggregate variation without exposing private vacancy-level judgments in repository-safe evidence.

## Counterfactual semantics

After human review, evaluate candidate alternative rules without changing runtime behavior.

At minimum compare:

1. current SPEC-019 degree rule;
2. hard-only rule;
3. hard-or-no-equivalent rule if evidence supports such a distinction;
4. degree evidence moved outside stretch into a separate credential-compatibility object;
5. conservative unresolved treatment when wording is ambiguous.

For each, report:

- sample precision/coverage;
- frozen WORTH protection where cross-evidence is available;
- current-corpus projected class changes;
- projected effect on excessive-stretch count;
- projected compute-allocation implications.

Do not promote any alternative rule inside SPEC-020 unless the packet is later explicitly amended after human review. This packet is preparation + human validation + post-review analysis only.

## Architectural question

Explicitly answer whether formal credentials belong primarily in:

- stretch/capability distance;
- hard eligibility;
- application competitiveness;
- a new `CredentialCompatibilityAssessment` object;
- or a combination with clear precedence.

A likely architecture to test is:

```text
CAPABILITY FIT
        ↓
CREDENTIAL COMPATIBILITY
        ↓
APPLICATION COMPETITIVENESS
```

but do not assume that conclusion before the human evidence is collected.

## No-runtime-change boundary

SPEC-020 must not change:

- stretch runtime behavior (none exists yet);
- SPEC-019 rules used as frozen source evidence;
- candidate education/capability facts;
- market policy;
- hard eligibility;
- ranking/recommendations;
- decision preferences;
- semantic-v1;
- semantic cache;
- source configuration;
- clustering/lifecycle state.

No external semantic calls are authorized.

Live source access is permitted only for bounded human-evidence verification when explicitly needed by preparation/replacement, not for refreshing the operational corpus.

## Experiment workflow

Implement a CLI/workflow with phases analogous to the successful human-validation pattern:

- `prepare` — freeze sample, reserves, blind packet, fingerprints;
- `record` — append Question A/B human judgments;
- `replace` — append-only invalid-evidence replacement;
- `report` — progress while blind; final metrics/counterfactuals only after completion.

Before completion, `report` must not reveal hidden stratum/expected-rule performance in a way that could bias remaining judgments.

## Privacy

Private/local and Git-ignored:

- manifest with vacancy identities;
- blind review packet if it contains vacancy-level evidence;
- human labels and notes;
- replacements;
- detailed final report tying judgments to vacancies.

Repository-safe aggregate may contain:

- experiment identity/fingerprints;
- sample design counts;
- aggregate evidence coverage;
- final aggregate label distributions;
- sanitized rule metrics;
- architecture conclusion;
- no vacancy titles, URLs, descriptions, human notes, or candidate-sensitive evidence beyond existing public/generic configuration facts.

## Integrity

Preparation must record hashes/fingerprints for:

- starting Git commit;
- SPEC-019 stretch rule identity;
- candidate profile identity;
- operational SQLite snapshot used for selection;
- selection contract;
- frozen sample/reserve manifest;
- human judgment log as it evolves.

Operational SQLite must remain read-only and byte-identical during preparation/reporting.

## Tests

Add offline coverage proving at least:

- deterministic sample and review order;
- cache/semantic/preference/recommendation state cannot affect selection;
- employer cap/reserve logic;
- exact qualification wording preservation;
- blind packet excludes stretch label and hidden decision evidence;
- controlled labels only;
- append-only record/supersession semantics;
- replacement cannot resample globally;
- report stays blind until completion;
- no semantic calls;
- SQLite read-only;
- repository-safe aggregate excludes private vacancy/judgment evidence;
- counterfactual analysis is deterministic after completion.

Run full offline suite and `git diff --check`.

## Stop conditions

Stop for human decision rather than improvising if:

- the 144-case population cannot be reconstructed reliably;
- qualification text is too truncated/normalized to preserve mandatory/equivalent/preferred semantics;
- sampling requires historical human labels to achieve balance;
- employer concentration makes a 50-case sample impossible without material cap relaxation;
- candidate evidence shown to reviewers cannot be bounded without leaking hidden model judgments;
- preparation would require semantic calls or operational-state mutation.

## Deliverable before human review

Return:

A. verified degree-driven population and snapshot identity;
B. sample/reserve design;
C. employer/role-family/wording-pattern coverage;
D. blind packet evidence fields;
E. exact Question A/B labels and instructions;
F. privacy/integrity proof;
G. zero-call/read-only confirmation;
H. tests/validation;
I. files changed;
J. first 5 blind reviews only after explicit approval to begin review;
K. recommended commit message for preparation.

Do not begin human review until preparation implementation is reviewed and committed.
No commit or push until normal approval after implementation review.
