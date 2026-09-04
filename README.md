# Opportunity Radar

Opportunity Radar is an evidence-first system for monitoring public employer
vacancies, maintaining reliable lifecycle state, and identifying which active
opportunities deserve a candidate's attention and why.

The initial operating context is Prague, Czechia, plus remote roles accessible
from Czechia. Candidate-specific facts and preferences are configuration, not
application code.

## Current phase

Phases 1–3 are implemented and validated at their respective architecture
boundaries. The first Live Decision Validation completed 30/30 reviews with a
directional `NO_GO`: recall was strong, while candidate-market routing,
multi-posting opportunity identity, and unrepresented preferences reduced
precision.

Phase 4 product behavior is **not implemented**. The current gate and frozen
decisions are recorded in [docs/STATUS.md](docs/STATUS.md).

## Repository map

- [SPEC.md](SPEC.md) — normative phase specification. Later explicit
  architecture decisions supersede conflicting exploratory text.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — current implemented layers,
  boundaries, invariants, and audited-but-unimplemented concepts.
- [docs/STATUS.md](docs/STATUS.md) — authoritative project handoff: current
  phase, evidence, failures, frozen items, and next gate.
- [docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md) — evidence, learning,
  experiment, authority, AI, and data-governance rules.
- [docs/decisions.yaml](docs/decisions.yaml) — material decision register.
- [experiments/registry.yaml](experiments/registry.yaml) — index of major
  experiments and their canonical artifacts.
- `config/` — runtime company, market, candidate, taxonomy, and semantic
  experiment configuration.
- `benchmarks/` — frozen Phase 3 benchmark definitions and job fixtures.
- `src/opportunity_radar/` — implementation.
- `tests/` — deterministic offline tests and separately marked live tests.
- `output/opportunity_radar.sqlite3` — current local operational state. See the
  evidence ownership policy before moving or publishing it.

Historical phase reports remain in `docs/`. They describe the gate at the time
they were written; `docs/STATUS.md` is the current handoff authority.

## Architecture at a glance

```text
OBSERVE
  -> RETRIEVAL SCOPE
  -> STORE STATE
  -> INTERPRET
  -> DECIDE
  -> HUMAN VALIDATE
  -> ACT (not implemented)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before changing a boundary.

## Setup and offline tests

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest -q
```

Live source tests are excluded by default:

```bash
.venv/bin/pytest -m live -o addopts='' -q
```

## Common commands

Phase 1 ingestion feasibility path:

```bash
.venv/bin/opportunity-radar --max-jobs 2
```

Phase 2 persistent refresh:

```bash
.venv/bin/opportunity-radar-state --company pure_storage --max-jobs 2
```

`--max-jobs` limits details after complete inventory and retrieval-scope
selection; it never limits lifecycle inventory. The default detail refresh
interval is 168 hours and can be overridden with `--detail-refresh-hours`.

Zero-detail retrieval-scope measurement:

```bash
.venv/bin/opportunity-radar-scope-measure
```

Offline Phase 3 benchmark:

```bash
.venv/bin/opportunity-radar-phase3 --output output/phase3_benchmark.json
```

Semantic ROI harness (offline unless explicitly opted into external calls):

```bash
.venv/bin/opportunity-radar-semantic-roi
```

Live Decision Validation preflight is read-only:

```bash
.venv/bin/opportunity-radar-live-validation preflight
.venv/bin/opportunity-radar-live-validation report batch-20260826T210045Z-6492b09a
```

Explicit judgment identities are preferred:

```bash
.venv/bin/opportunity-radar-live-validation record <batch_id> --review-number <n> APPLY --agree
.venv/bin/opportunity-radar-live-validation record <batch_id> --job-instance-id <id> APPLY --agree
```

The legacy positional identifier is retained for compatibility but fails when
an integer could refer to different review and job-instance identities.

Project health, derived read-only from repository evidence:

```bash
.venv/bin/opportunity-radar-status --json
.venv/bin/opportunity-radar-status --markdown
```

## Persistent evidence

- Operational observations, lifecycle, events, candidate snapshots, and
  assessments: `output/opportunity_radar.sqlite3`.
- Major experiment artifacts: paths indexed by `experiments/registry.yaml`.
- Live-validation batch manifests: `output/live_validation/<batch_id>/`.
- Human judgments: local append-only
  `data/live_validation/judgments.jsonl`; this contains personal profiling data
  and is intentionally excluded from Git until repository privacy and durable
  private backup policy are explicitly decided.
- The aggregate final validation report is repository evidence and contains no
  raw judgment notes.

Generated outputs are not automatically authoritative. Consult
[docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md) for evidence classes and
ownership.
