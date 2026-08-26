from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import pvariance
from typing import Any

import yaml

from opportunity_radar.deterministic_baseline import deterministic_baseline
from opportunity_radar.eligibility import evaluate_eligibility
from opportunity_radar.experimental_semantic import ExperimentalSemanticAssessor, ModelTier, OpenAIResponsesTransport, estimated_cost
from opportunity_radar.benchmark_runner import benchmark_summary, evaluate_benchmark
from opportunity_radar.phase3_benchmark import load_benchmark
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy


@dataclass(frozen=True)
class ExperimentConfig:
    version: int
    provider: str
    endpoint: str
    api_key_env: str
    connect_timeout: float
    read_timeout: float
    repetitions: int
    top_n: int
    ambiguous_min: int
    ambiguous_max: int
    models: dict[str, ModelTier]


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    raw = yaml.safe_load(Path(path).read_text())
    models = {tier: ModelTier(tier=tier, **value) for tier, value in raw["models"].items()}
    if set(models) != {"economical", "stronger"}:
        raise ValueError("experiment requires economical and stronger model tiers")
    return ExperimentConfig(raw["experiment_version"], raw["provider"], raw["endpoint"], raw["api_key_env"], raw["connect_timeout_seconds"], raw["read_timeout_seconds"], raw["repetitions"], raw["top_n"], raw["ambiguous_triage_min"], raw["ambiguous_triage_max"], models)


def _rank_pass(actual: str, expected: dict[str, Any]) -> bool:
    job_only = expected.get("job_description_only", {})
    if job_only.get("strict_rank_assertion", True):
        return actual == expected["rank_tier"]
    order = {"LOW": 0, "REVIEW": 1, "HIGH": 2, "TOP": 3}
    return order[actual] >= order[job_only["expected_minimum_tier"]]


def stability_metrics(runs: list[list[dict[str, Any]]]) -> dict[str, Any]:
    if len(runs) < 2:
        return {"status": "NOT_RUN", "repetitions": len(runs)}
    by_case: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        for case in run: by_case.setdefault(case["benchmark_id"], []).append(case)
    variances = {}
    tier_changes = recommendation_changes = 0
    concept_consistency = []
    for case_id, values in by_case.items():
        for dimension in values[0]["dimensions"]:
            scores = [x["dimensions"][dimension] for x in values if x["dimensions"][dimension] is not None]
            variances[f"{case_id}:{dimension}"] = pvariance(scores) if len(scores) > 1 else 0.0
        tier_changes += len({x["rank_tier"] for x in values}) > 1
        recommendation_changes += len({x["recommendation"] for x in values}) > 1
        for field in ("strengths", "gaps", "risks"):
            sets = [set(x[field]) for x in values]; union = set().union(*sets); intersection = set.intersection(*sets) if sets else set()
            concept_consistency.append(1.0 if not union else len(intersection) / len(union))
    return {"status": "COMPLETED", "repetitions": len(runs), "mean_dimension_variance": sum(variances.values()) / len(variances), "tier_change_cases": tier_changes, "recommendation_change_cases": recommendation_changes, "mean_concept_consistency": sum(concept_consistency) / len(concept_consistency)}


def _run_external(result: dict[str, Any], config: ExperimentConfig, taxonomy, candidate, cases, smoke: bool = False) -> None:
    transport = OpenAIResponsesTransport(config.endpoint, config.api_key_env, config.connect_timeout, config.read_timeout)
    selected_models = {"economical": config.models["economical"]} if smoke else config.models
    selected_cases = [next(case for case in cases if case.benchmark_id == "siemens_data_ai")] if smoke else cases
    repetitions = 1 if smoke else config.repetitions
    total_calls = len(selected_models) * repetitions * len(selected_cases)
    call_number = 0
    for tier, model in selected_models.items():
        repeated_runs = []; usages = []; failures = 0
        first_quality = None
        for repetition_index in range(repetitions):
            assessor = ExperimentalSemanticAssessor(taxonomy, model, transport)
            def progress(event, case, case_result, error):
                nonlocal call_number
                effort = model.reasoning_effort if model.reasoning_effort is not None else "provider_default(not explicitly set)"
                if event == "start":
                    call_number += 1
                    transport.request_label = f"[{call_number}/{total_calls}] model={model.model} benchmark={case.benchmark_id} repetition={repetition_index + 1}"
                    print(f"[{call_number}/{total_calls}] START model={model.model} benchmark={case.benchmark_id} repetition={repetition_index + 1} reasoning_effort={effort} connect_timeout={config.connect_timeout}s read_timeout={config.read_timeout}s", flush=True)
                    return
                usage = assessor.calls[-1] if assessor.calls else None
                if event == "finish":
                    print(f"[{call_number}/{total_calls}] SUCCESS elapsed={usage.latency_seconds:.2f}s http_api_success=true input_tokens={usage.input_tokens} output_tokens={usage.output_tokens} estimated_cost_usd={usage.estimated_cost_usd:.8f} tier={case_result.rank_tier}", flush=True)
                else:
                    elapsed = f"{usage.latency_seconds:.2f}" if usage else "unknown"
                    detail = usage.error if usage and usage.error else f"{type(error).__name__}: {error}"
                    print(f"[{call_number}/{total_calls}] ERROR elapsed={elapsed}s http_api_success=false model={model.model} benchmark={case.benchmark_id} error={detail}", flush=True)
            try:
                evaluated = evaluate_benchmark(selected_cases, candidate, taxonomy, assessor, progress=progress)
                if first_quality is None: first_quality = benchmark_summary(evaluated, selected_cases)
                raw_run = []
                for case_result, semantic in zip(evaluated, assessor.outputs):
                    raw_run.append({"benchmark_id": case_result.benchmark_id, "dimensions": {k:v.score for k,v in semantic.dimensions.items()}, "rank_tier": case_result.rank_tier, "recommendation": case_result.recommendation, "strengths": [x.concept_id for x in semantic.strengths], "gaps": [x.concept_id for x in semantic.gaps], "risks": [x.concept_id for x in semantic.risks]})
                repeated_runs.append(raw_run); usages.extend(assessor.calls)
            except Exception as exc:
                failures += 1
                repeated_runs.append([{"error": f"{type(exc).__name__}: {exc}"}])
                usages.extend(assessor.calls)
        successful_calls = [x for x in usages if x.success]
        total_attempted = len(usages)
        result["semantic_models"][tier] = {"status": "COMPLETED" if first_quality else "FAILED", "model": model.model, "required_environment_variable": config.api_key_env, "quality": first_quality, "structured_output_validity": len(successful_calls) / total_attempted if total_attempted else None, "actual_calls": len(successful_calls), "actual_tokens": {"input": sum(x.input_tokens for x in successful_calls), "cached_input": sum(x.cached_input_tokens for x in successful_calls), "output": sum(x.output_tokens for x in successful_calls), "reasoning": sum(x.reasoning_tokens for x in successful_calls)}, "actual_cost_usd": round(sum(x.estimated_cost_usd for x in successful_calls), 8), "failure_rate": sum(not x.success for x in usages) / total_attempted if total_attempted else None, "latency_seconds": {"mean": sum(x.latency_seconds for x in successful_calls) / len(successful_calls) if successful_calls else None}, "stability": stability_metrics([x for x in repeated_runs if x and "error" not in x[0]]), "raw_repeated_outputs": repeated_runs, "usage_records": [asdict(x) for x in usages]}
    if smoke:
        return
    baseline = {x["benchmark_id"]: x for x in result["deterministic_baseline"]["cases"]}
    for strategy in result["selective_strategies"].values():
        selected = set(strategy["selected_ids"]); strategy["simulated_quality_by_model"] = {}
        for tier, model_result in result["semantic_models"].items():
            quality = model_result.get("quality")
            if not quality:
                strategy["simulated_quality_by_model"][tier] = None; continue
            semantic = {x["benchmark_id"]: x for x in quality["cases"]}
            hybrid = []
            for case_id, base in baseline.items():
                source = semantic[case_id] if case_id in selected else base
                hybrid.append({"benchmark_id": case_id, "rank_tier": source["rank_tier"], "rank_pass": source["rank_pass"], "human_decision": base["human_decision"]})
            applies = [x for x in hybrid if x["human_decision"] == "APPLY"]; controls = [x for x in hybrid if x["human_decision"] == "DONT_APPLY"]
            per_call = model_result["actual_cost_usd"] / model_result["actual_calls"] if model_result["actual_calls"] else 0
            strategy["simulated_quality_by_model"][tier] = {"rank_tier_agreement": sum(x["rank_pass"] for x in hybrid) / len(hybrid), "apply_job_recall": sum(x["rank_tier"] != "LOW" for x in applies) / len(applies), "control_job_handling": sum(x["rank_tier"] == "LOW" for x in controls) / len(controls), "estimated_actual_cost_usd": round(per_call * len(selected), 8)}


def run_offline_experiment(config_path="config/semantic_experiment.yaml", run_external: bool = False, smoke_external: bool = False) -> dict[str, Any]:
    config = load_experiment_config(config_path)
    taxonomy = load_taxonomy("config/taxonomy.yaml")
    candidate = load_candidate_profile("config/candidate.yaml", taxonomy)
    cases = load_benchmark("benchmarks/phase3_benchmark.yaml", taxonomy)
    baseline_cases = []
    for case in cases:
        eligibility = evaluate_eligibility(case.fixture.job, candidate).status.value
        result = deterministic_baseline(case.fixture.job, candidate, taxonomy)
        expected = case.expected
        baseline_cases.append({"benchmark_id": case.benchmark_id, "eligibility": eligibility, "eligibility_pass": eligibility in expected["eligibility"]["allowed"], "score": result.score, "rank_tier": result.tier, "rank_pass": _rank_pass(result.tier, expected), "triage_score": result.triage_score, "evidence_sufficient": result.evidence_sufficient, "reasons": result.reasons, "human_decision": expected["human_decision"]})
    apply_cases = [x for x in baseline_cases if x["human_decision"] == "APPLY"]
    controls = [x for x in baseline_cases if x["human_decision"] == "DONT_APPLY"]
    baseline_quality = {"eligibility_agreement": sum(x["eligibility_pass"] for x in baseline_cases) / len(baseline_cases), "rank_tier_agreement": sum(x["rank_pass"] for x in baseline_cases) / len(baseline_cases), "apply_job_recall": sum(x["rank_tier"] != "LOW" for x in apply_cases) / len(apply_cases), "control_job_handling": sum(x["rank_tier"] == "LOW" for x in controls) / len(controls), "false_negative_ids": [x["benchmark_id"] for x in apply_cases if x["rank_tier"] == "LOW"], "insufficient_evidence_ids": [x["benchmark_id"] for x in baseline_cases if not x["evidence_sufficient"]], "pairwise_ordering": {"status": "NOT_DEFINED_IN_BENCHMARK"}, "cases": baseline_cases}
    credential = bool(os.environ.get(config.api_key_env))
    model_results = {}
    projections = {}
    for tier, model in config.models.items():
        per_job = estimated_cost(model, model.estimated_input_tokens_per_job, 0, model.estimated_output_tokens_per_job)
        projections[tier] = {"assumption": "configured token estimate; not actual usage", "estimated_cost_per_job_usd": per_job, "estimated_benchmark_run_usd": round(per_job * len(cases), 6), "monthly": {str(n): round(per_job * n, 4) for n in (100, 500, 1000, 5000)}, "cached_opportunity_radar_assessment_cost_usd": 0.0, "material_change_reassessment_cost_usd": per_job}
        model_results[tier] = {"status": "READY_NOT_RUN" if credential else "BLOCKED_MISSING_CREDENTIAL", "model": model.model, "required_environment_variable": config.api_key_env, "quality": None, "actual_calls": 0, "actual_tokens": {"input": 0, "cached_input": 0, "output": 0, "reasoning": 0}, "actual_cost_usd": 0.0, "failure_rate": None, "latency_seconds": None, "stability": stability_metrics([])}
    ordered = sorted(baseline_cases, key=lambda x: x["triage_score"], reverse=True)
    selections = {
        "SEMANTIC_NONE": [],
        "SEMANTIC_ALL": [x["benchmark_id"] for x in baseline_cases if x["eligibility"] != "INELIGIBLE"],
        "SEMANTIC_TOP_N": [x["benchmark_id"] for x in ordered[:config.top_n]],
        "SEMANTIC_AMBIGUOUS": [x["benchmark_id"] for x in baseline_cases if (not x["evidence_sufficient"] or x["rank_tier"] == "REVIEW" or config.ambiguous_min <= x["triage_score"] <= config.ambiguous_max or (x["triage_score"] >= 80 and x["rank_tier"] == "LOW"))],
    }
    strategies = {}
    all_calls = len(selections["SEMANTIC_ALL"])
    for name, ids in selections.items():
        calls = len(ids)
        strategies[name] = {"selected_ids": ids, "semantic_calls": calls, "decision_quality": baseline_quality if name == "SEMANTIC_NONE" else None, "quality_status": "BASELINE" if name == "SEMANTIC_NONE" else "REQUIRES_EXTERNAL_RESULTS", "cost_reduction_vs_all": 1.0 - calls / all_calls if all_calls else 0.0, "estimated_cost_usd": {tier: round(projections[tier]["estimated_cost_per_job_usd"] * calls, 6) for tier in config.models}}
    result = {"experiment_version": config.version, "execution_status": "OFFLINE_COMPLETE_EXTERNAL_BLOCKED" if not credential else "OFFLINE_COMPLETE_EXTERNAL_READY", "credential_available": credential, "external_diagnostics": {"connect_timeout_seconds": config.connect_timeout, "read_timeout_seconds": config.read_timeout, "reasoning_effort": {tier: (model.reasoning_effort if model.reasoning_effort is not None else "provider_default_not_explicit") for tier, model in config.models.items()}}, "deterministic_baseline": baseline_quality, "semantic_models": model_results, "cost_projections": projections, "selective_strategies": strategies, "experimental_limits": ["Seven cases are directional evidence, not statistically significant.", "No prompt, weight, or benchmark expectation was tuned.", "Semantic quality and stability remain unknown until bounded external runs execute."]}
    if run_external or smoke_external:
        if not credential: raise RuntimeError(f"external experiment requested but {config.api_key_env} is not set")
        _run_external(result, config, taxonomy, candidate, cases, smoke=smoke_external)
        result["execution_status"] = "EXTERNAL_SMOKE_COMPLETED" if smoke_external else "EXTERNAL_COMPLETED"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 semantic ROI experiment")
    parser.add_argument("--config", default="config/semantic_experiment.yaml")
    parser.add_argument("--output", default="output/semantic_roi_experiment.json")
    parser.add_argument("--run-external", action="store_true")
    parser.add_argument("--smoke-external", action="store_true")
    args = parser.parse_args()
    if args.run_external and args.smoke_external:
        parser.error("--run-external and --smoke-external are mutually exclusive")
    result = run_offline_experiment(args.config, args.run_external, args.smoke_external)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True); Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"execution_status": result["execution_status"], "deterministic_baseline": {k:v for k,v in result["deterministic_baseline"].items() if k != "cases"}}, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
