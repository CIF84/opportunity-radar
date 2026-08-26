# Phase 3 Semantic ROI Experiment

## Completed result

The bounded experiment completed 28 external calls: two repetitions across
seven frozen benchmark cases for both `gpt-5.6-luna` and `gpt-5.6-terra`.
`output/semantic_roi_experiment.json` is the machine-readable source of truth.

Directional conclusion: **SEMANTIC_SELECTIVE**.

Luna improved APPLY recall and broad tier agreement over the deterministic
baseline at negligible personal-scale cost. Terra did not improve the tested
decision metrics and cost approximately ten times more. The seven-case sample
is too small for production calibration or statistical claims.

## Deterministic baseline

- eligibility agreement: 100%;
- broad tier agreement: 42.9%;
- APPLY-job recall: 75%;
- negative-control handling: 100%;
- false negative: Siemens Data/AI.

## Luna

- calls: 14/14 successful;
- structured-output validity: 100%;
- input tokens: 72,660, including 55,034 cached;
- output tokens: 24,832;
- reasoning tokens: 1,555;
- actual cost: **$0.03442428**;
- mean latency: 20.56 seconds;
- broad tier agreement: 57.1%;
- APPLY-job recall: 100%;
- required-strength recall: 89.3%;
- expected-gap recall: 71.4%;
- expected-risk recall: 42.9%;
- qualitative dimension agreement within one point: 97.6%.

Across repetitions, mean dimension variance was 0.0833. One case changed tier,
one changed recommendation, and mean strengths/gaps/risks set consistency was
47.5%. Structured output and call reliability were strong; concept-list
stability was materially weaker.

Luna handled both negative controls correctly and recovered the deterministic
Siemens false negative into the attention set, although Siemens remained HIGH
rather than the benchmark TOP tier. Strict/non-strict rank disagreements also
remained for Resistant AI and BCG. Ambiente passed its non-strict job-only
assertion; its final human REVIEW depends on interview evidence unavailable to
the model.

## Terra

- calls: 14/14 successful;
- structured-output validity: 100%;
- input tokens: 72,660, including 48,669 cached;
- output tokens: 21,927;
- reasoning tokens: 1,832;
- actual cost: **$0.32083980**;
- mean latency: 17.18 seconds;
- broad tier agreement: 42.9%;
- APPLY-job recall: 100% in the raw benchmark summary, but the first-run
  strategy simulation retained only 75% due to unstable case outcomes;
- required-strength recall: 71.0%;
- expected-gap recall: 60.7%;
- expected-risk recall: 42.9%;
- qualitative dimension agreement within one point: 97.6%.

Across repetitions, mean dimension variance was 0.0893. Three cases changed
tier, two changed recommendation, and mean concept consistency was 48.6%.
Terra offered no measured decision-quality advantage over Luna in this sample.

## Benchmark case summary

| Case | Luna | Terra | Expected |
|---|---|---|---|
| Siemens Data/AI | HIGH / APPLY | HIGH / APPLY | TOP / APPLY |
| Resistant AI CSM Lead | HIGH / APPLY | REVIEW / REVIEW | TOP / APPLY |
| DuckDuckGo User Insights | HIGH / APPLY | LOW / LOW_PRIORITY | HIGH / APPLY |
| Ambiente Transformation | TOP / APPLY | HIGH / APPLY | job-only at least HIGH; final human REVIEW |
| BCG Associate | HIGH / APPLY | HIGH / APPLY | REVIEW / APPLY |
| Microsoft engineering control | LOW / LOW_PRIORITY | LOW / LOW_PRIORITY | LOW / DONT_APPLY |
| REVEL ML research control | LOW / LOW_PRIORITY | LOW / LOW_PRIORITY | LOW / DONT_APPLY |

## Actual Luna cost basis

The first seven Luna assessments cost $0.01854510, or **$0.00264930 per new
assessment**. The repeated seven calls cost $0.01587918, or $0.00226845 each,
with substantially more provider prompt caching.

An unchanged Opportunity Radar semantic cache hit makes no API call and has
zero marginal model cost. A materially changed vacancy should provisionally be
budgeted at approximately $0.00265 for reassessment.

## Strategy simulation

| Strategy | Luna calls | Rank agreement | APPLY recall | Control handling | Estimated cost |
|---|---:|---:|---:|---:|---:|
| SEMANTIC_NONE | 0 | 42.9% | 75% | 100% | $0 |
| SEMANTIC_ALL | 7 | 57.1% | 100% | 100% | $0.01721 |
| SEMANTIC_TOP_N | 3 | 57.1% | 100% | 100% | $0.00738 |
| SEMANTIC_AMBIGUOUS | 5 | 57.1% | 100% | 100% | $0.01229 |

Selective Luna processing produced the same measured benchmark decision
quality as SEMANTIC_ALL. However, the next Live Decision Validation experiment
deliberately assesses every eligible new or materially changed vacancy so that
selection policies do not hide real-world false negatives.

## Limitations and next gate

- Seven historical jobs are directional evidence, not a representative market
  sample.
- Results are sensitive to stochastic assessment variation.
- Concept extraction consistency needs real-world inspection.
- Benchmark expectations, prompts, and scoring weights were not tuned during
  this run.

The next gate is human review of a stratified batch of current live vacancies
using Luna, with unchanged semantic caching and separate human judgments.
