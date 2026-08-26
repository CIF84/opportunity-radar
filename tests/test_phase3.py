from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from opportunity_radar.benchmark_runner import benchmark_summary, evaluate_benchmark
from opportunity_radar.eligibility import evaluate_eligibility
from opportunity_radar.models import JobLocation, JobReference, NormalizedJob, WorkMode
from opportunity_radar.phase3_benchmark import load_active_semantic_jobs, load_benchmark, semantic_job_from_normalized
from opportunity_radar.phase3_config import digest, load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import DimensionScore, EligibilityStatus, SemanticJobInput
from opportunity_radar.phase3_pipeline import assess_opportunity
from opportunity_radar.phase3_repository import Phase3Repository
from opportunity_radar.scoring import calculate_composite
from opportunity_radar.semantic import DeterministicSemanticAssessor
from opportunity_radar.state_models import DetailObservation, SourceOutcome
from opportunity_radar.state_repository import SCHEMA_VERSION, StateRepository


AT = datetime(2026, 8, 25, tzinfo=timezone.utc)


def resources():
    taxonomy = load_taxonomy("config/taxonomy.yaml")
    candidate = load_candidate_profile("config/candidate.yaml", taxonomy)
    return taxonomy, candidate


def semantic_job(description="Build business analytics and AI insights with stakeholders.", locations=({"raw": "Prague, Czechia", "city": "Prague", "country": "Czechia"},)):
    return SemanticJobInput("Acme", "Analytics Lead", description, tuple(locations), "hybrid")


def normalized(description="Build business analytics and AI insights with stakeholders."):
    return NormalizedJob(
        "acme", "Acme", "A", "Analytics Lead", [JobLocation("Prague, Czechia", "Prague", None, "Czechia")],
        WorkMode.HYBRID, "https://acme.example/A", description, None, None, "Full time", "Analytics", "fixture", AT,
    )


def seed_state(repo: StateRepository, job: NormalizedJob, run_id="r1"):
    ref = JobReference(job.company_id, job.external_job_id, job.canonical_url)
    repo.create_run(run_id, AT.isoformat())
    repo.apply_outcome(run_id, SourceOutcome(
        job.company_id, job.company_name, "fixture", "SUCCESS", AT, [ref],
        [DetailObservation(ref, job)], True, True, 1,
    ))
    repo.finish_run(run_id, AT.isoformat(), "COMPLETED")


def test_profiles_taxonomy_and_unknown_none_semantics():
    taxonomy, candidate = resources()
    portability = load_candidate_profile("config/candidate_portability_test.yaml", taxonomy)
    assert set(candidate.scoring_weights) == set(portability.scoring_weights)
    assert candidate.capability("ml_research") is None  # UNKNOWN
    explicit_none = replace(candidate, capabilities=candidate.capabilities + ({"capability_id": "ml_research", "level": "NONE", "confidence": "HIGH"},))
    assert explicit_none.capability("ml_research")["level"] == "NONE"


def test_profile_fingerprints_separate_semantic_and_weights():
    _, candidate = resources()
    changed_weights = dict(candidate.scoring_weights)
    changed_weights["functional_alignment"] = 0.30
    changed_weights["strategic_alignment"] = 0.15
    changed = replace(candidate, scoring_weights=changed_weights, scoring_preference_fingerprint=digest(changed_weights), full_profile_fingerprint=digest((candidate.full_profile_fingerprint, changed_weights)))
    assert changed.semantic_profile_fingerprint == candidate.semantic_profile_fingerprint
    assert changed.scoring_preference_fingerprint != candidate.scoring_preference_fingerprint


def test_explicit_incompatibility_and_missing_evidence():
    _, candidate = resources()
    constrained = replace(candidate, hard_constraints={**candidate.hard_constraints, "mandatory_location_exclusions": ["United States"]})
    incompatible = semantic_job(locations=({"raw": "New York, United States", "country": "United States"},))
    assert evaluate_eligibility(incompatible, constrained).status == EligibilityStatus.INELIGIBLE
    unknown = semantic_job(locations=())
    assert evaluate_eligibility(unknown, candidate).status == EligibilityStatus.UNCERTAIN


def test_unknown_capability_does_not_create_gap_but_explicit_none_does():
    taxonomy, candidate = resources()
    assessor = DeterministicSemanticAssessor(taxonomy)
    job = semantic_job("Strong Python programming is required.")
    omitted = replace(candidate, capabilities=tuple(x for x in candidate.capabilities if x["capability_id"] != "python"))
    none = replace(omitted, capabilities=omitted.capabilities + ({"capability_id": "python", "level": "NONE", "confidence": "HIGH"},))
    omitted_result = assess_opportunity(job, omitted, taxonomy, assessor)
    none_result = assess_opportunity(job, none, taxonomy, assessor)
    assert "python" not in {x.concept_id for x in omitted_result.semantic.gaps}
    assert "python" in {x.concept_id for x in none_result.semantic.gaps}


def test_missing_core_dimension_forces_review():
    taxonomy, candidate = resources()

    class MissingAssessor(DeterministicSemanticAssessor):
        def assess(self, job, candidate, features):
            result = super().assess(job, candidate, features)
            dimensions = dict(result.dimensions)
            dimensions["seniority_alignment"] = DimensionScore(None, "LOW", "No seniority evidence")
            return replace(result, dimensions=dimensions)

    result = assess_opportunity(semantic_job(), candidate, taxonomy, MissingAssessor(taxonomy))
    assert result.composite_score is None
    assert result.recommendation.value == "REVIEW"
    assert result.missing_dimensions == ("seniority_alignment",)


def test_composite_is_exact_and_confidence_not_arithmetic():
    _, candidate = resources()
    dimensions = {key: DimensionScore(4, "LOW", "fixture") for key in candidate.scoring_weights}
    score, coverage, confidence, missing = calculate_composite(dimensions, candidate.scoring_weights)
    assert score == 7.5
    assert coverage == 1.0 and confidence == "LOW" and not missing


class CountingAssessor(DeterministicSemanticAssessor):
    def __init__(self, taxonomy):
        super().__init__(taxonomy)
        self.calls = 0

    def assess(self, job, candidate, features):
        self.calls += 1
        return super().assess(job, candidate, features)


def test_semantic_cache_reuse_and_invalidation(tmp_path):
    taxonomy, candidate = resources()
    state = StateRepository(tmp_path / "state.db")
    seed_state(state, normalized())
    live = load_active_semantic_jobs(state)[0]
    repo, assessor = Phase3Repository(state), CountingAssessor(taxonomy)
    job_id, observation_id, content_fp, job = live
    first = assess_opportunity(job, candidate, taxonomy, assessor, repository=repo, job_instance_id=job_id, job_observation_id=observation_id, content_fingerprint=content_fp)
    same = assess_opportunity(job, candidate, taxonomy, assessor, repository=repo, job_instance_id=job_id, job_observation_id=observation_id, content_fingerprint=content_fp)
    assert assessor.calls == 1 and same.semantic_reused

    weights = dict(candidate.scoring_weights); weights["functional_alignment"] = .30; weights["strategic_alignment"] = .15
    weight_only = replace(candidate, version=2, scoring_weights=weights, scoring_preference_fingerprint=digest(weights), full_profile_fingerprint=digest((candidate.full_profile_fingerprint, weights)))
    rescored = assess_opportunity(job, weight_only, taxonomy, assessor, repository=repo, job_instance_id=job_id, job_observation_id=observation_id, content_fingerprint=content_fp)
    assert assessor.calls == 1 and rescored.semantic_reused

    semantic_change = replace(candidate, version=3, semantic_profile_fingerprint=digest("changed semantic profile"), full_profile_fingerprint=digest("changed full profile"))
    assess_opportunity(job, semantic_change, taxonomy, assessor, repository=repo, job_instance_id=job_id, job_observation_id=observation_id, content_fingerprint=content_fp)
    assert assessor.calls == 2
    changed_job = replace(job, description=job.description + " Materially changed responsibilities.")
    assess_opportunity(changed_job, candidate, taxonomy, assessor, repository=repo, job_instance_id=job_id, job_observation_id=observation_id, content_fingerprint=digest(changed_job.semantic_payload()))
    assert assessor.calls == 3
    assert len(state.rows("semantic_assessments")) == 3


def test_identical_content_on_later_phase2_observation_reuses_semantic(tmp_path):
    taxonomy, candidate = resources(); state = StateRepository(tmp_path / "state.db")
    seed_state(state, normalized(), "r1")
    job_id, observation_id, content_fp, job = load_active_semantic_jobs(state)[0]
    repo, assessor = Phase3Repository(state), CountingAssessor(taxonomy)
    assess_opportunity(job, candidate, taxonomy, assessor, repository=repo, job_instance_id=job_id, job_observation_id=observation_id, content_fingerprint=content_fp)
    seed_state(state, normalized(), "r2")
    job_id, later_observation_id, later_fp, job = load_active_semantic_jobs(state)[0]
    assert later_observation_id != observation_id and later_fp == content_fp
    result = assess_opportunity(job, candidate, taxonomy, assessor, repository=repo, job_instance_id=job_id, job_observation_id=later_observation_id, content_fingerprint=later_fp)
    assert assessor.calls == 1 and result.semantic_reused


def test_phase3_schema_is_minimal_extension(tmp_path):
    state = StateRepository(tmp_path / "state.db")
    with state.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 3
    assert state.rows("candidate_profiles") == []


def test_benchmark_harness_and_apply_triage_recall():
    taxonomy, candidate = resources(); cases = load_benchmark("benchmarks/phase3_benchmark.yaml", taxonomy)
    results = evaluate_benchmark(cases, candidate, taxonomy, DeterministicSemanticAssessor(taxonomy))
    summary = benchmark_summary(results, cases)
    assert len(results) == 7
    assert summary["apply_job_triage_recall"] == 1.0
    assert all(result.eligibility_pass for result in results)


def test_second_candidate_uses_same_pipeline_and_changes_ranking():
    taxonomy, primary = resources()
    second = load_candidate_profile("config/candidate_portability_test.yaml", taxonomy)
    cases = load_benchmark("benchmarks/phase3_benchmark.yaml", taxonomy)
    assessor = DeterministicSemanticAssessor(taxonomy)
    primary_scores = {case.benchmark_id: assess_opportunity(case.fixture.job, primary, taxonomy, assessor).composite_score for case in cases}
    second_scores = {case.benchmark_id: assess_opportunity(case.fixture.job, second, taxonomy, assessor).composite_score for case in cases}
    assert primary_scores != second_scores
    assert second_scores["control_ml_research"] > primary_scores["control_ml_research"]
    assert second_scores["control_software_engineering"] > primary_scores["control_software_engineering"]


def test_live_and_benchmark_paths_share_semantic_input(tmp_path):
    taxonomy, _ = resources()
    fixture = load_benchmark("benchmarks/phase3_benchmark.yaml", taxonomy)[0].fixture
    assert isinstance(fixture.job, SemanticJobInput)
    assert isinstance(semantic_job_from_normalized(normalized()), SemanticJobInput)
