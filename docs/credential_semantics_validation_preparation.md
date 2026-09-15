# SPEC-020 Credential Semantics Validation — Preparation

Preparation `spec020-credential-preparation-20260914-v3` was frozen before human
review and remains historical evidence. SPEC-020 was subsequently terminated at
20/50; see `docs/credential_semantics_validation_termination.md`. The earlier `v1` aggregate remains
immutable evidence that the original cap of five failed closed and required an
explicit human concentration decision.

## Verified source population

The current frozen-compatible operational snapshot reproduces exactly 144
SPEC-019 `EXCESSIVE_STRETCH` opportunities whose decisive evidence includes
`MANDATORY_CREDENTIAL_ABSENT` for `bachelors_degree`.

```text
operational SQLite SHA-256  a07d53002dc22e07ba33946a1dfc172365d182e37133f6221f4ef48e2154ff23
stretch-rules fingerprint   c9388aa47a4422b37a83217e692bd281318be8e028469709744304bfa66b848f
source-population count     144
source-population hash      3040fde1ed38b1cef0648ed889ee9c3146593ee757dcf76f8ce45fba754ef67d
employers                   3
degree-only decisive        144
explicit-years context       28
```

Employer concentration is 116 / 22 / 6 across EY, Johnson & Johnson, and
Schneider Electric. At the requested cap of five, no more than 15 items can be
selected. The smallest cap that permits a 50-item sample is 22, producing a
minimum-cap distribution of 22 / 22 / 6.

The candidate authorized the mathematically minimum cap of 22. The preparation
then froze the requested 50 cases as 22 EY, 22 Johnson & Johnson, and all 6
Schneider Electric cases. It also froze five reserves in each declared major
wording stratum: direct mandatory wording and qualified/substitutable wording.
Selected and reserve identities are unique and disjoint.

## Coverage visible before sampling

The 144-case population spans eight bounded role-family buckets:

```text
TECHNOLOGY_ENGINEERING       32
FINANCE_ACCOUNTING_TAX       35
CONSULTING_TRANSFORMATION    15
OPERATIONS_PROGRAM           12
HEALTHCARE_SCIENCE            3
PEOPLE_HR                     2
COMMERCIAL_CLIENT             1
OTHER_UNCLASSIFIED           44
```

Credential wording buckets are:

```text
MUST_HAVE                     84
MIXED_PREFERRED_CONTEXT       34
EXPLICITLY_REQUIRED           23
EXPLICIT_EQUIVALENT_EXPERIENCE 3
```

These are deterministic sampling descriptors, not human credential labels.
They do not alter or pre-judge the review questions.

## Frozen sample coverage

The sample covers all eight bounded role-family buckets:

```text
COMMERCIAL_CLIENT           1
CONSULTING_TRANSFORMATION   8
FINANCE_ACCOUNTING_TAX      8
HEALTHCARE_SCIENCE          3
OPERATIONS_PROGRAM          7
OTHER_UNCLASSIFIED         13
PEOPLE_HR                   2
TECHNOLOGY_ENGINEERING      8
```

Credential-wording coverage is:

```text
EXPLICITLY_REQUIRED             18
EXPLICIT_EQUIVALENT_EXPERIENCE   3
MIXED_PREFERRED_CONTEXT         15
MUST_HAVE                       14
```

Final reporting must keep the unweighted/stratified sample view separate from
employer-population-weighted estimates over the verified 144 cases. The balanced
sample proportions are not population prevalence. Schneider Electric's six
cases are complete current-employer coverage.

## Implemented blind-review contract

The private packet uses a deterministic blind order. Each review contains:

- employer and role title;
- location/work mode only for orientation;
- exact matched credential wording;
- a bounded qualification excerpt copied without paraphrasing;
- explicit years/professional requirements when present;
- a bounded candidate professional-history and relevant-capability summary;
- source URL and evidence gaps;
- separate Question A and Question B labels.

The renderer rejects leakage of stretch class, triage, semantic cache,
recommendation, or other hidden decision evidence. Selection explicitly excludes
semantic-cache state, recommendation, decision preferences, hidden stretch
payload after source-population qualification, and historical human labels.

Question A uses exactly:

```text
HARD_CREDENTIAL
DEGREE_OR_EQUIVALENT_EXPERIENCE
PREFERRED_CREDENTIAL
GENERIC_OR_NONDECISIVE_CREDENTIAL
AMBIGUOUS_CREDENTIAL
INVALID_OR_STALE_EVIDENCE
```

Question B uses exactly:

```text
DEGREE_GAP_DECISIVE
EXPERIENCE_PLAUSIBLY_SUBSTITUTES
DEGREE_GAP_NOT_DECISIVE
NEED_MORE_INFORMATION
```

Question A classifies source wording. Question B asks whether the missing
bachelor's degree alone makes candidacy unrealistic given the bounded
professional-history evidence. Neither question is an application decision.

## Integrity and privacy

- External semantic calls: 0
- Live-source calls: 0
- SQLite writes: 0
- Human judgments created during preparation: 0
- Human review started during preparation: no
- Operational SQLite hash/mtime: unchanged

Vacancy identities, titles, URLs, qualification excerpts, candidate evidence,
human labels, notes, replacements, and detailed results remain private/local.
The private immutable manifest and blind packet remain excluded from Git. Their
hashes and the deterministic selection identities are preserved in the sanitized
repository-safe receipt:

`output/credential_semantics_validation/spec020-credential-preparation-20260914-v3/aggregate_summary.json`

```text
protocol fingerprint          df80ce827b9091a57255cf52613bb5c159528bb3f721234a26d1a8ecad7243db
selection fingerprint         400c050ba3091012d0707b534f06ac5a6740c4e174d1c1005f61b686f3d19359
blind-order fingerprint       307e85f4ddabc5df51ed0eac258d05320296fd2c1aa30b54e2feac7391a8df78
sample/reserve fingerprint    53c3d76e78cb547c81a1ab5fac5115f6a6ff7c121f7713f6267a2cf1b7d118d6
private manifest SHA-256      1a00feb3a178765a53b711ce9b9958f300f30afdc5906b73aaabdfa0872789da
private blind packet SHA-256  e33536eb0dcf28c3e3ba39ceadd877384f93400bb1a1ef3cdfd12466b997bfb5
```

The selection replayed deterministically, source qualification wording remained
exact, review numbers are exactly 1–50, and the operational SQLite hash and mtime
remained unchanged. Preparation made zero human judgments, external semantic
calls, live-source calls, or SQLite writes. The later append-only human evidence
and terminal decision do not revise this frozen preparation receipt.
