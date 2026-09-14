# SPEC-019 Stretch Evidence Boundary Audit

Status: `IMPLEMENTED_LOCALLY_AWAITING_REVIEW`

Experiment: `EXP-STRETCH-EVIDENCE-001`

Run: `spec019-stretch-evidence-20260913-v3`

## Result

The audit supports a separate, deterministic stretch-evidence object, but not a
runtime rejection or semantic-compute gate. The bounded rules protected all
three frozen human-WORTH opportunities and produced no preference-only or
market-only false `EXCESSIVE_STRETCH` classifications. Coverage remains narrow:
83.7% of the current corpus is `UNRESOLVED`, and mandatory-degree evidence
accounts for most current-corpus excessive classifications.

Recommendation: `REVIEW_FOR_LATER_RUNTIME_EXPERIMENT`.

## A. Evidence inspected

- Frozen 60-item semantic compute-worthiness sample and its append-only current
  judgments.
- Candidate profile version 4 capability, experience, career, leadership, and
  education evidence.
- Current local Phase 2 active/detail state, Phase 4 opportunity clusters,
  candidate routing, preference diagnostics, seniority diagnostics, and
  compatible semantic-cache availability.
- Frozen SPEC-012 aggregate economics and its observed Luna cost basis.

The detailed joins to titles, cluster identities, and human evidence remain in
the ignored private audit. The repository-safe aggregate contains counts,
fingerprints, gates, limitations, and conclusions only.

## B. Stretch contract and fingerprints

The audit implements four classes:

```text
CURRENT_FIT
MANAGEABLE_STRETCH
EXCESSIVE_STRETCH
UNRESOLVED
```

Each `StretchRequirementAssessment` records a requirement category and concept,
bounded vacancy evidence and source field, `CORE / PREFERRED / CONTEXTUAL`
strength, candidate evidence, `SUPPORTED / PARTIAL / UNSUPPORTED / UNKNOWN`
support, gap severity, and a controlled reason. `StretchAssessment` records the
final class, decisive and unresolved concepts, and rules/input/assessment
fingerprints.

Frozen identities for this run:

```text
audit config                 6f76f792da855cce9421d36ce598ff7727b2a03ea6597e9420389d4874bcd0fa
stretch rules                c9388aa47a4422b37a83217e692bd281318be8e028469709744304bfa66b848f
candidate capability input   38f07b5ebf7ed5a8912e9c1f3deff9e3477f1a8e7e9ddbff1f6c6ab08bc16f35
semantic profile             6579b21e2bc22fef927ca17bdf6083b7e9a099bd5810b49528f589c83793819b
market policy                86c00d7cfb8b40b02c141b955ce482575464396a3097065fd435e64d11411bdb
decision preferences         394342b487cc3b7b36f6f8a2cd38a5ea2f6c747af73f9f5f409b7fcb3ca359f5
```

Job locations, work mode, employer identity, market policy, and decision
preferences are absent from stretch input identity. Candidate direction cannot
upgrade capability evidence.

## C. Controlled rule set

The predeclared policy uses title-scoped profession/function rules for a small
set of observable families: software and ML engineering, security architecture,
cloud/networking, medical/clinical, legal, accounting/control, warehouse,
account management, business operations, project/program management, AI
transformation, and AI technical depth.

Candidate support is evaluated from explicit capability levels, adjacent
capabilities, configured domain depth, or bounded numeric experience facts.
Omitted capability stays `UNKNOWN`; explicit `NONE` is `UNSUPPORTED`.

Two additional rules are deliberately narrow:

- explicit mandatory degree evidence plus an explicitly absent degree may form
  a decisive core gap; preferred degrees never do;
- elevated role evidence or an explicit five-plus-year requirement becomes
  decisive only when the matching professional capability is explicitly known
  at no more than `DEVELOPING`. Seniority wording alone never suffices.

No description-wide profession inference, fuzzy taxonomy mapping, model output,
market fact, or preference evidence changes stretch class.

## D. Frozen human-sample adjudication

The private adjudication view separates the 60 judgments using their frozen
controlled reasons and human notes:

| Category | Count |
|---|---:|
| Stretch-related rejection | 33 |
| Market-only rejection | 11 |
| Preference-only/other rejection | 8 |
| Unavailable/insufficient evidence | 5 |
| WORTH with qualification uncertainty | 3 |

This classification is evaluation evidence. It does not rewrite the frozen
human label or turn every stretch-related rejection into ground-truth excessive
stretch.

## E. Frozen-sample results

| Stretch class | Count |
|---|---:|
| `CURRENT_FIT` | 7 |
| `MANAGEABLE_STRETCH` | 24 |
| `EXCESSIVE_STRETCH` | 9 |
| `UNRESOLVED` | 20 |

## F. Protection and detection metrics

- WORTH protected from excessive stretch: **3/3 (100%)**.
- Human-evident excessive cases detected: **9/23 (39.1% coverage)**.
- Excessive predictions supported by the conservative private adjudication:
  **9/9 (100% directional precision)**.
- Preference-only false excessive: **0**.
- Market-only false excessive: **0**.
- Current-fit predictions not contradicted by available human capability
  evidence: **7/7**.
- Unresolved rate: **33.3%** on the frozen sample.

Coverage and precision are reported separately. The low coverage is expected
from the `UNKNOWN != UNSUPPORTED` invariant and is preferable to fabricating
candidate deficiencies.

## G. Current-corpus distribution

The read-only corpus replay saw 3,935 active usable-detail clusters, of which
3,400 were current normal-shortlist candidates.

| Stretch class | All clusters | Routed clusters |
|---|---:|---:|
| `CURRENT_FIT` | 191 | 148 |
| `MANAGEABLE_STRETCH` | 281 | 254 |
| `EXCESSIVE_STRETCH` | 171 | 155 |
| `UNRESOLVED` | 3,292 | 2,843 |

Only 663 clusters had at least one recognized core requirement. The decisive
reason distribution was:

- mandatory credential absent: 144;
- elevated professional depth above an explicitly developing capability: 21;
- explicit required professional years above an explicitly developing
  capability: 7.

The employer-level class distribution and boundary overlaps are retained in the
sanitized aggregate. Most credential cases originate in employers whose
descriptions use standardized degree language; this concentration is a reason
to validate credentials separately before any runtime use.

## H. Evidence-coverage limitations

- Omitted candidate capabilities cannot be treated as absence. Many
  human-obvious professional mismatches therefore remain unresolved.
- Role extraction is intentionally title-scoped and misses functions expressed
  only in prose.
- A generic mandatory-degree phrase does not establish how an employer will
  treat long equivalent experience in practice; the rule records stated
  evidence, not hiring certainty.
- The human sample has only three WORTH labels and is neither random nor large.
- Current-corpus results describe one local state snapshot, not the market.

## I. Compute-allocation counterfactuals

Frozen 60-item sample:

| Hypothetical boundary | Calls | Reduction | WORTH recall | Projected cost |
|---|---:|---:|---:|---:|
| `MANAGEABLE + UNRESOLVED` only | 44 | 26.7% | 100% | $0.11656920 |
| All except `EXCESSIVE` | 51 | 15.0% | 100% | $0.13511430 |
| All except `EXCESSIVE` plus 10% deterministic exploration | 52 | 13.3% | 100% | $0.13776360 |

Current 3,400-cluster routed corpus:

| Hypothetical boundary | Candidates | Reduction | Projected cost |
|---|---:|---:|---:|
| `MANAGEABLE + UNRESOLVED` only | 3,097 | 8.9% | $8.20488210 |
| All except `EXCESSIVE` | 3,245 | 4.6% | $8.59697850 |

Costs use the frozen SPEC-012 projected per-call basis of $0.00264930. These are
diagnostics, not a promoted budget or compute policy. Compared with the earlier
PRIORITY triage (3/3 WORTH recall at 15% precision), stretch adds interpretable
negative evidence but does not yet deliver a large current-corpus reduction.

## J. Boundary interactions

Market status, decision-preference effects, seniority guard, and semantic-cache
availability are reported only as overlap diagnostics. None is an input to
stretch classification. Market-incompatible roles may be current fit;
unattractive account roles may be current fit; and attractive AI roles may be
manageable stretch.

## K. Privacy, persistence, and invariants

- SQLite and human-judgment hashes were identical before and after the audit.
- Semantic calls, live-source calls, SQLite writes, lifecycle changes, cluster
  changes, recommendation changes, and semantic-cache writes: **0**.
- No schema migration or persisted runtime stretch state was introduced.
- The detailed audit is private/local and ignored; only the sanitized aggregate
  is eligible for Git.

## L. Architecture conclusion

A separate auditable stretch object is feasible. The four-class contract and
requirement evidence preserve the key conceptual boundaries. The rule set is
not ready to reject, cap, rank, or suppress semantic assessment in normal
operation because current-corpus coverage is low and credential-driven
excessive classifications lack direct human validation at scale.

## M. Later runtime experiment

A later **shadow-only** runtime experiment is justified, but direct runtime
promotion is not. The next experiment should freeze a bounded sample from the
new `EXCESSIVE_STRETCH` and `UNRESOLVED` populations, over-sample mandatory-
credential decisions, and measure false-excessive risk before evaluating any
combined rejection boundary.

## N. Validation

All eight SPEC-019 safety gates passed in the immutable run. Full repository
test results are reported at handoff after the implementation test suite.

## O. Files

Implementation is in `stretch_evidence.py`; rules and experiment identity are
in `experiments/stretch_evidence_boundary_v1.yaml`; the repository-safe run
receipt is under `output/stretch_evidence_boundary/`. Private detailed evidence
remains in the parallel ignored `audit.json`.

## P. Recommended next packet

Define a bounded, frozen, blind human validation of the stretch boundary. It
should be diagnostic and shadow-only, include all three frozen WORTH controls,
sample explicit credential and professional-depth decisions, preserve an
unresolved control stratum, and predeclare a zero-false-excessive gate before
considering runtime promotion.

## Q. Recommended commit message

```text
Audit stretch evidence boundaries
```
