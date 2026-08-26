from __future__ import annotations

from opportunity_radar.deterministic_baseline import deterministic_baseline
import requests

from opportunity_radar.experimental_semantic import CallUsage, ExperimentalSemanticAssessor, ModelCallError, ModelResponse, OpenAIResponsesTransport, assessment_schema, estimated_cost
from opportunity_radar.features import extract_features
from opportunity_radar.phase3_benchmark import load_benchmark
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.roi_experiment import load_experiment_config, run_offline_experiment, stability_metrics


def resources():
    taxonomy = load_taxonomy("config/taxonomy.yaml")
    candidate = load_candidate_profile("config/candidate.yaml", taxonomy)
    cases = load_benchmark("benchmarks/phase3_benchmark.yaml", taxonomy)
    return taxonomy, candidate, cases


def test_deterministic_baseline_is_pre_semantic_and_orders_all_cases():
    taxonomy, candidate, cases = resources()
    results = [deterministic_baseline(case.fixture.job, candidate, taxonomy) for case in cases]
    assert all(result.score is not None for result in results)
    assert all(result.tier in {"TOP", "HIGH", "REVIEW", "LOW"} for result in results)
    assert all(isinstance(result.evidence_sufficient, bool) for result in results)


def test_model_config_and_cost_accounting():
    config = load_experiment_config("config/semantic_experiment.yaml")
    cheap, strong = config.models["economical"], config.models["stronger"]
    assert estimated_cost(cheap, 6000, 1000, 700) < estimated_cost(strong, 6000, 1000, 700)
    assert estimated_cost(cheap, 0, 0, 0) == 0
    assert config.connect_timeout == 15
    assert config.read_timeout == 300
    assert cheap.reasoning_effort == "low" and strong.reasoning_effort == "medium"


class FakeTransport:
    def complete(self, model, instructions, payload, schema):
        dimension = {"score": 3, "confidence": "MEDIUM", "reason": "Fixture", "job_evidence": [], "candidate_evidence": []}
        concept = {"concept_id": "business_analytics", "statement": "Fixture", "importance": "HIGH", "confidence": "MEDIUM", "job_evidence": [], "candidate_evidence": []}
        risk = {**concept, "concept_id": "technical_intensity"}
        usage = CallUsage(model.model, 100, 10, 20, 5, .1, True, 0, estimated_cost(model, 100, 10, 20))
        return ModelResponse({"dimensions": {key: dict(dimension) for key in schema["properties"]["dimensions"]["required"]}, "strengths": [concept], "gaps": [], "risks": [risk]}, usage)


def test_external_assessor_preserves_contract_with_injected_transport():
    taxonomy, candidate, cases = resources(); model = load_experiment_config("config/semantic_experiment.yaml").models["economical"]
    assessor = ExperimentalSemanticAssessor(taxonomy, model, FakeTransport())
    job = cases[0].fixture.job
    result = assessor.assess(job, candidate.semantic_input(), extract_features(job, taxonomy))
    assert set(result.dimensions) == set(assessment_schema(taxonomy)["properties"]["dimensions"]["required"])
    assert len(assessor.calls) == 1 and assessor.calls[0].success


def test_stability_metrics_detect_changes():
    base = {"benchmark_id": "x", "dimensions": {"functional_alignment": 3}, "rank_tier": "REVIEW", "recommendation": "REVIEW", "strengths": ["business_analytics"], "gaps": [], "risks": []}
    changed = {**base, "dimensions": {"functional_alignment": 5}, "rank_tier": "TOP", "recommendation": "APPLY", "strengths": []}
    metrics = stability_metrics([[base], [changed]])
    assert metrics["mean_dimension_variance"] == 1.0
    assert metrics["tier_change_cases"] == 1
    assert metrics["mean_concept_consistency"] < 1


def test_offline_roi_harness_blocks_calls_without_credential(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_offline_experiment()
    assert result["execution_status"] == "OFFLINE_COMPLETE_EXTERNAL_BLOCKED"
    assert result["semantic_models"]["economical"]["actual_calls"] == 0
    assert result["semantic_models"]["stronger"]["actual_cost_usd"] == 0
    assert set(result["selective_strategies"]) == {"SEMANTIC_NONE", "SEMANTIC_ALL", "SEMANTIC_TOP_N", "SEMANTIC_AMBIGUOUS"}


def test_transport_reports_read_timeout_without_external_call(monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "not-a-real-key")
    seen = {}
    def timeout(*args, **kwargs):
        seen["timeout"] = kwargs["timeout"]
        raise requests.ReadTimeout("fixture timeout")
    monkeypatch.setattr("opportunity_radar.experimental_semantic.requests.post", timeout)
    model = load_experiment_config("config/semantic_experiment.yaml").models["economical"]
    transport = OpenAIResponsesTransport("https://invalid.example", "TEST_API_KEY", 15, 300, max_retries=0)
    try:
        transport.complete(model, "fixture", {}, {"type": "object"})
        assert False, "expected timeout"
    except ModelCallError as exc:
        assert "ReadTimeout" in exc.usage.error
        assert exc.usage.success is False
    assert seen["timeout"] == (15, 300)
