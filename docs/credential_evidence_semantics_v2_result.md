# SPEC-021 Credential Evidence Semantics — Completed Result

SPEC-021 completed the frozen planned review set at 36/36. The experiment used
immutable captured evidence, made no live-source or semantic-model calls, wrote
nothing to operational SQLite, and changed no runtime policy.

The sample deliberately oversampled seven evidence classes. Its proportions
describe the human-validation set and **must not** be interpreted as market or
SPEC-019-population prevalence.

## Human judgments

Question A:

| Interpretation | Count |
|---|---:|
| `HARD_CREDENTIAL` | 22 |
| `DEGREE_OR_EQUIVALENT_EXPERIENCE` | 11 |
| `PREFERRED_CREDENTIAL` | 3 |
| Other/ambiguous/invalid | 0 |

Question B:

| Experiential substitution | Count |
|---|---:|
| `EXPERIENCE_STRONGLY_SUBSTITUTES` | 1 |
| `EXPERIENCE_PARTIALLY_SUBSTITUTES` | 5 |
| `NO_CREDIBLE_EXPERIENTIAL_SUBSTITUTE` | 23 |
| `CREDENTIAL_CONSTITUTIVE_OR_NON_SUBSTITUTABLE` | 7 |
| `NEED_MORE_INFORMATION` | 0 |

Independent gaps appeared in 34/36 reviews: 11 domain, 11 technical, ten
professional-function, two regulatory/licence, one language, and one other
capability gap. This is the most important representation finding: a credential
judgment and the candidate's independent capability fit are separate evidence.

Twenty distinct combinations of Question A, Question B, and controlled gap set
were observed. All seven frozen sampling classes were reviewed, but sampling
classes were not treated as expected labels. For example, deterministic
`PREFERRED_OR_IDEAL` and `AMBIGUOUS` strata both contained human hard-credential
interpretations once the bounded qualification context was considered.

## Architecture comparison

### A — degree inside stretch

This matches the current diagnostic SPEC-019 shape. It is cheap, but it conflates
credential wording, experiential substitution, and capability distance. The
verified SPEC-019 corpus contains 144 excessive-stretch cases driven by degree
evidence, including 131 normal-candidate cases.

### B — credential compatibility separate from capability stretch

This best matches the human evidence. Capability fit and credential compatibility
remain separate objects and meet only in application-competitiveness or decision
reasoning. In a diagnostic replay, all 144 degree-driven cases move out of
credential-only capability stretch and into a separate compatibility boundary.
That is a representation result, not a claim that all 144 become suitable.

### C — constitutive credentials only as hard

This is the narrowest plausible future deterministic hard boundary. On the
verified 144-case corpus, the existing lexical evidence gives a lower bound of
one high-confidence constitutive case and an upper candidate bound of 23 when all
professional-licence concepts are included. Consequently, 121–143 cases remain
generic credential-compatibility evidence. This range is deliberately
conservative; it is not a promoted rule.

The diagnostic conclusion is to prefer Architecture B as the representation
boundary and retain Architecture C only as a candidate for a separately specified,
conservatively validated hard rule. SPEC-021 promotes neither.

## Compatibility with SPEC-020

SPEC-020's eight interpretable hard-wording cases observed six plausible
experience substitutes and two decisive degree gaps. SPEC-021 agrees with the
two durable qualitative observations:

- formal credential semantics and practical substitution are distinct;
- independent capability/domain gaps must not be attributed to the degree.

The experiments must not be pooled. SPEC-020 was incomplete,
source-decay-confounded, hard-wording-only, and employer-concentrated; its ratios
remain exploratory rather than population estimates.

## Compute-allocation implications

For the 144-case replay, 13 cases were already out of normal market scope. If
every remaining credential case required semantic reasoning, Architecture B has
an upper bound of 131 calls (about $0.347 at the frozen $0.0026493 call basis).
Architecture C yields a bounded range of 108–130 calls (about $0.286–$0.344).

These are ceilings, not recommended budgets. Deterministic evidence parsing and
independent capability checks should reduce semantic work. No calls were made in
this analysis, and semantic-v1 remains frozen.

## Evidence boundary

The repository-safe result is
`output/credential_evidence_validation/spec021-credential-evidence-preparation-20260916-v2/aggregate_result.json`.
Vacancy identities, exact human notes, append-only judgments, the manifest, and
the detailed report remain private/local and Git-ignored.
