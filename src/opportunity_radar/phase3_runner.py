from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_radar.benchmark_runner import benchmark_summary, evaluate_benchmark
from opportunity_radar.phase3_benchmark import load_benchmark
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.semantic import DeterministicSemanticAssessor


def run_benchmark(candidate_path: str, taxonomy_path: str, benchmark_path: str) -> dict:
    taxonomy = load_taxonomy(taxonomy_path)
    candidate = load_candidate_profile(candidate_path, taxonomy)
    cases = load_benchmark(benchmark_path, taxonomy)
    assessor = DeterministicSemanticAssessor(taxonomy)
    return benchmark_summary(evaluate_benchmark(cases, candidate, taxonomy, assessor), cases)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the offline Phase 3 benchmark")
    parser.add_argument("--candidate", default="config/candidate.yaml")
    parser.add_argument("--taxonomy", default="config/taxonomy.yaml")
    parser.add_argument("--benchmark", default="benchmarks/phase3_benchmark.yaml")
    parser.add_argument("--output", default="output/phase3_benchmark.json")
    args = parser.parse_args()
    result = run_benchmark(args.candidate, args.taxonomy, args.benchmark)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
