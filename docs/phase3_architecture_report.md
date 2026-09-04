# Phase 3 Relevance Architecture Report

> Historical gate report. Its external-semantic next step was completed by the
> semantic ROI and Live Decision Validation experiments. Use `docs/STATUS.md`
> for current direction.

## Scope and result

Phase 3 is implemented as a candidate-specific interpretation layer after the
validated market-state boundary. It answers which active jobs deserve
attention through conservative eligibility, explainable evidence extraction,
rank-only triage, six semantic dimensions, deterministic composite arithmetic,
and a small recommendation set.

No adapter, `NormalizedJob`, job identity, lifecycle, or Phase 2 observation
contract was changed. No external model, UI, notification, scheduling, scoring
probability, or Learning Intelligence subsystem was introduced.

## Implemented flow

```text
Active Phase 2 job / BenchmarkJobFixture
                  ↓
          SemanticJobInput
                  ↓
 CandidateProfile → Eligibility
                  ↓
     Neutral deterministic features
                  ↓
         Rank-only triage
                  ↓
 Provider-independent semantic contract
                  ↓
 Deterministic fake semantic assessor
                  ↓
 Six dimensions + strengths/gaps/risks
                  ↓
 Deterministic composite + recommendation
                  ↓
 Versioned SQLite assessment history/cache
```

The semantic assessor receives neither hard constraints nor scoring weights.
Job descriptions are treated solely as untrusted evidence text. Eligibility,
identity, lifecycle, persistence, cache policy, arithmetic, and recommendation
derivation remain application responsibilities.

## Benchmark result

The frozen seven-case benchmark was evaluated with the initial candidate.

| Case | Eligibility | RADAR | Produced tier | Expected tier | Rank assertion |
|---|---:|---:|---|---|---|
| Siemens Data/AI | ELIGIBLE | 8.38 | TOP | TOP | pass |
| Resistant AI Global CSM Lead | ELIGIBLE | 8.62 | TOP | TOP | pass |
| DuckDuckGo Head User Insights | ELIGIBLE | 8.62 | TOP | HIGH | disagreement |
| Ambiente AI Transformation | ELIGIBLE | 9.38 | TOP | REVIEW / job-only ≥ HIGH | pass (non-strict) |
| BCG Associate | ELIGIBLE | 7.75 | HIGH | REVIEW | disagreement |
| Microsoft Software Engineering control | ELIGIBLE | 4.50 | LOW | LOW | pass |
| REVEL ML Research control | ELIGIBLE | 3.75 | LOW | LOW | pass |

Aggregate diagnostic results:

- eligibility agreement: 100%;
- APPLY-job triage recall: 100% (triage excluded no benchmark job);
- strict/non-strict rank assertions: 5/7 (71.4%);
- required-strength recall: 100%;
- expected-risk recall: 100%;
- expected-gap recall: 53.6%;
- qualitative dimension agreement within one scale point: 97.6%.

Ambiente's final human `REVIEW` uses interview evidence unavailable to the
job-description-only assessor. The implementation correctly honors the
benchmark's non-strict job-only minimum and does not manufacture that evidence.

## Explained disagreements

The deterministic fake assessor over-ranks DuckDuckGo and BCG. This is useful
evidence that keyword/concept rules validate orchestration but are not a
sufficient semantic interpretation method.

Expected-gap recall is deliberately lower because several benchmark gaps refer
to candidate capabilities omitted from the profile. The authoritative profile
semantics say omission is `UNKNOWN`, not `NONE`; production code therefore does
not convert those omissions into confirmed gaps. It can record specialist or
competitiveness risk while leaving the capability gap unconfirmed. No benchmark
annotation or candidate rating was silently changed.

## Candidate portability

The same loader, eligibility rules, feature extraction, assessor contract,
scoring code, and recommendation code ran unchanged for the software/ML
portability profile. Rankings changed materially:

- REVEL ML Research: 3.75 / LOW for the initial candidate, 8.00 / TOP for the
  software/ML candidate;
- Microsoft Software Engineering: 4.50 / LOW for the initial candidate, 6.00 /
  REVIEW for the software/ML candidate;
- Siemens Data/AI: 8.38 / TOP for the initial candidate, 4.00 / LOW for the
  software/ML candidate.

The historical benchmark's expected judgments belong to the initial candidate,
so they are not treated as assertions for the portability candidate.

## Persistence and semantic reuse

SQLite schema version 2 adds only:

- `candidate_profiles`;
- `semantic_assessments`;
- `opportunity_assessments`.

Semantic reuse is keyed by job instance, material content fingerprint,
semantic-profile fingerprint, semantic contract version, and assessor identity
and version. Weight-only changes reuse semantic output and create a recomputed
opportunity assessment. Candidate semantic changes and material job changes
invalidate reuse. Historical assessments are retained.

## Architecture corrections discovered

1. The semantic assessor input needed a dedicated `SemanticCandidateInput` so
   hard constraints and arithmetic weights could not leak into semantic work.
2. Benchmark gap annotations and omitted-capability semantics can conflict.
   `UNKNOWN != NONE` remains authoritative; the harness reports the mismatch.
3. Historical human decisions may include evidence unavailable in vacancy text.
   Such assertions need explicit non-strict/job-only handling, as Ambiente does.
4. The fake assessor is an architecture instrument, not evidence that
   dictionary matching is an adequate production semantic scorer.

## Recommendation

**CONDITIONAL GO** for the Phase 3 architecture.

The deterministic boundaries, candidate portability, composite reproducibility,
SQLite separation, caching, eligibility safety, and triage recall are validated.
The remaining condition is a provider-independent external semantic-assessor
experiment against the frozen benchmark. Provider/model choice and credentials
are intentionally not embedded in this implementation.
