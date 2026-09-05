from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from opportunity_radar.live_validation import _clustered_assessed_pool
from opportunity_radar.market_routing import compose_market_routing
from opportunity_radar.market_status import (
    CurrentCandidateMarketStatus,
    evaluate_current_candidate_market,
    load_market_normalization_rules,
)
from opportunity_radar.models import JobLocation, JobReference, NormalizedJob, WorkMode
from opportunity_radar.phase3_config import digest, load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import (
    CORE_DIMENSIONS,
    DimensionScore,
    EligibilityStatus,
    Recommendation,
    SemanticAssessment,
    SemanticJobInput,
)
from opportunity_radar.phase3_pipeline import assess_opportunity
from opportunity_radar.phase3_repository import Phase3Repository
from opportunity_radar.semantic import SEMANTIC_CONTRACT_VERSION
from opportunity_radar.seniority_guard import (
    SeniorityGuardReason,
    apply_seniority_guard,
    evaluate_seniority_guard,
    load_seniority_guard_rules,
)
from opportunity_radar.state_models import DetailObservation, SourceOutcome
from opportunity_radar.state_repository import SCHEMA_VERSION, StateRepository


ROOT = Path(__file__).parents[1]
TAXONOMY = load_taxonomy(ROOT / "config/taxonomy.yaml")
PRIMARY = load_candidate_profile(ROOT / "config/candidate.yaml", TAXONOMY)
PORTABILITY = load_candidate_profile(
    ROOT / "config/candidate_portability_test.yaml", TAXONOMY,
)
RULES = load_seniority_guard_rules(ROOT / "config/seniority_guard_rules.yaml")
MARKET_RULES = load_market_normalization_rules(ROOT / "config/market_status_rules.yaml")


def _job(title: str | None, description: str = "") -> SemanticJobInput:
    return SemanticJobInput(
        "Example", title, description,
        ({"raw": "Prague, Czechia", "city": "Prague", "region": None, "country": "Czechia"},),
        "hybrid",
    )


@pytest.mark.parametrize(
    ("job", "reason"),
    [
        (_job("Junior Project Manager"), SeniorityGuardReason.EXPLICIT_JUNIOR_ROLE),
        (_job("Graduate Programme Analyst"), SeniorityGuardReason.EXPLICIT_GRADUATE_ROLE),
        (_job("Entry Level Analyst"), SeniorityGuardReason.EXPLICIT_JUNIOR_ROLE),
        (_job("Analyst", "Recent graduates are encouraged to apply."), SeniorityGuardReason.EXPLICIT_GRADUATE_ROLE),
    ],
)
def test_explicit_evidence_activates_configured_guard(job, reason):
    result = evaluate_seniority_guard(job, PRIMARY, RULES)
    assert result.active is True
    assert result.terminal_cap is Recommendation.LOW_PRIORITY
    assert result.reason_code is reason
    assert result.evidence[0].matched_text


@pytest.mark.parametrize(
    "job",
    [
        _job("Business Analyst"),
        _job("Assistant Director"),
        _job("Associate Consultant"),
        _job("Project Manager", "Salary is EUR 30,000."),
        _job("Project Manager", "Requires 0-2 years of experience."),
        _job(None, ""),
    ],
)
def test_ambiguous_or_indirect_evidence_does_not_activate(job):
    result = evaluate_seniority_guard(job, PRIMARY, RULES)
    assert result.active is False
    assert result.reason_code is SeniorityGuardReason.NO_EXPLICIT_DOWNLEVEL_EVIDENCE
    assert result.terminal_cap is None


def test_semantic_seniority_score_cannot_activate_deterministic_guard():
    job = _job("Project Manager", "Coordinate projects across the business.")
    semantic_diagnostic = DimensionScore(1, "HIGH", "Materially below candidate level")
    result = evaluate_seniority_guard(job, PRIMARY, RULES)
    assert semantic_diagnostic.score == 1
    assert result.active is False


def test_explicit_structured_seniority_is_supported_without_semantic_inference():
    job = replace(_job("Software Engineer"), supplemental_evidence={"seniority": "entry_level"})
    result = evaluate_seniority_guard(job, PRIMARY, RULES)
    assert result.active is True
    assert result.reason_code is SeniorityGuardReason.EXPLICIT_JUNIOR_ROLE
    assert result.evidence[0].source_field == "supplemental_evidence.seniority"


def test_portability_profile_disables_same_generic_guard():
    enabled = evaluate_seniority_guard(_job("Junior Engineer"), PRIMARY, RULES)
    disabled = evaluate_seniority_guard(_job("Junior Engineer"), PORTABILITY, RULES)
    assert enabled.active is True
    assert disabled.active is False
    assert disabled.reason_code is SeniorityGuardReason.POLICY_DISABLED
    assert disabled.evidence[0].level == "JUNIOR"


@pytest.mark.parametrize(
    ("before", "after", "applied"),
    [
        (Recommendation.APPLY, Recommendation.LOW_PRIORITY, True),
        (Recommendation.REVIEW, Recommendation.LOW_PRIORITY, True),
        (Recommendation.LOW_PRIORITY, Recommendation.LOW_PRIORITY, False),
        (Recommendation.INELIGIBLE, Recommendation.INELIGIBLE, False),
    ],
)
def test_active_guard_applies_most_restrictive_terminal_cap(before, after, applied):
    assessment = evaluate_seniority_guard(_job("Junior Analyst"), PRIMARY, RULES)
    decision = apply_seniority_guard(before, assessment)
    assert decision.recommendation is after
    assert decision.cap_applied is applied


def test_market_uncertain_then_junior_guard_results_in_low_priority():
    market = compose_market_routing(
        CurrentCandidateMarketStatus.UNCERTAIN,
        EligibilityStatus.ELIGIBLE,
        Recommendation.APPLY,
    )
    guard = evaluate_seniority_guard(_job("Junior Analyst"), PRIMARY, RULES)
    final = apply_seniority_guard(market.recommendation, guard)
    assert market.recommendation is Recommendation.REVIEW
    assert final.recommendation is Recommendation.LOW_PRIORITY


def test_market_out_of_scope_remains_excluded_before_guard():
    market = compose_market_routing(
        CurrentCandidateMarketStatus.OUT_OF_SCOPE,
        EligibilityStatus.ELIGIBLE,
        Recommendation.APPLY,
    )
    guard = evaluate_seniority_guard(_job("Junior Analyst"), PRIMARY, RULES)
    final = apply_seniority_guard(market.recommendation, guard)
    assert market.include_in_normal_shortlist is False
    assert market.recommendation is None
    assert final.recommendation is None


def test_guard_only_policy_change_preserves_other_candidate_identities(tmp_path):
    raw = yaml.safe_load((ROOT / "config/candidate.yaml").read_text(encoding="utf-8"))
    raw["profile"]["version"] += 1
    raw["market_access_policy"]["seniority_guard"]["explicit_levels"] = []
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    changed = load_candidate_profile(path, TAXONOMY)
    assert changed.market_access_policy_fingerprint != PRIMARY.market_access_policy_fingerprint
    assert changed.semantic_profile_fingerprint == PRIMARY.semantic_profile_fingerprint
    assert changed.scoring_preference_fingerprint == PRIMARY.scoring_preference_fingerprint
    assert changed.decision_preference_fingerprint == PRIMARY.decision_preference_fingerprint


class _HighAssessor:
    assessor_id = "external-structured"
    assessor_version = "1:gpt-5.6-luna"

    def __init__(self):
        self.calls = 0

    def assess(self, job, candidate, features):
        self.calls += 1
        dimensions = {
            name: DimensionScore(4, "HIGH", "fixture") for name in CORE_DIMENSIONS
        }
        return SemanticAssessment(
            dimensions, (), (), (), self.assessor_id, self.assessor_version,
            SEMANTIC_CONTRACT_VERSION,
        )


def test_guard_recompute_reuses_semantics_and_preserves_state_and_cluster(tmp_path):
    state = StateRepository(tmp_path / "state.sqlite3")
    at = datetime(2026, 9, 5, tzinfo=timezone.utc)
    job = NormalizedJob(
        "acme", "Acme", "1", "Junior Project Manager",
        [JobLocation("Prague, Czechia", "Prague", None, "Czechia")],
        WorkMode.HYBRID, "https://example.test/1",
        "Coordinate projects across product and operations teams.",
        None, None, "Full time", "Operations", "fixture", at,
    )
    reference = JobReference("acme", "1", job.canonical_url)
    state.create_run("run-1", at.isoformat())
    state.apply_outcome("run-1", SourceOutcome(
        "acme", "Acme", "fixture", "SUCCESS", at, [reference],
        [DetailObservation(reference, job)], True, True, 1,
    ))
    state.finish_run("run-1", at.isoformat(), "COMPLETED")
    instance = state.rows("job_instances")[0]
    observation = state.rows("job_observations")[0]
    semantic_job = _job(job.title, job.description)
    assessor = _HighAssessor()
    assess_opportunity(
        semantic_job, PRIMARY, TAXONOMY, assessor,
        repository=Phase3Repository(state),
        job_instance_id=instance["job_instance_id"],
        job_observation_id=observation["job_observation_id"],
        content_fingerprint=observation["fingerprint"],
    )
    before = {
        name: [dict(row) for row in state.rows(name)]
        for name in ("semantic_assessments", "events", "job_instances")
    }
    enabled_pool, _ = _clustered_assessed_pool(
        state.path, PRIMARY, assessor.assessor_version, MARKET_RULES, TAXONOMY,
    )
    disabled_policy = replace(
        PRIMARY.market_access_policy,
        seniority_guard={"explicit_levels": [], "terminal_recommendation_cap": "LOW_PRIORITY"},
    )
    disabled = replace(
        PRIMARY,
        market_access_policy=disabled_policy,
        market_access_policy_fingerprint=digest(disabled_policy.payload()),
        full_profile_fingerprint=digest((PRIMARY.full_profile_fingerprint, disabled_policy.payload())),
    )
    disabled_pool, _ = _clustered_assessed_pool(
        state.path, disabled, assessor.assessor_version, MARKET_RULES, TAXONOMY,
    )

    assert assessor.calls == 1
    assert enabled_pool[0]["recommendation_before_seniority_guard"] == "APPLY"
    assert enabled_pool[0]["recommendation"] == "LOW_PRIORITY"
    assert enabled_pool[0]["seniority_guard"]["reason_code"] == "EXPLICIT_JUNIOR_ROLE"
    assert disabled_pool[0]["recommendation"] == "APPLY"
    assert enabled_pool[0]["score"] == disabled_pool[0]["score"]
    assert enabled_pool[0]["semantic_assessment_id"] == disabled_pool[0]["semantic_assessment_id"]
    assert enabled_pool[0]["cluster_fingerprint"] == disabled_pool[0]["cluster_fingerprint"]
    assert enabled_pool[0]["preferred_variant"]["preferred_variant_job_instance_id"] == disabled_pool[0]["preferred_variant"]["preferred_variant_job_instance_id"]
    assert enabled_pool[0]["market_status"] == disabled_pool[0]["market_status"] == "IN_SCOPE"
    for name, rows in before.items():
        assert [dict(row) for row in state.rows(name)] == rows
    assert SCHEMA_VERSION == 3


def test_dbg_cork_preserved_title_is_sufficient_explicit_evidence():
    batch = yaml.safe_load(
        (ROOT / "output/live_validation/batch-20260826T210045Z-6492b09a/batch.json")
        .read_text(encoding="utf-8")
    )
    item = next(item for item in batch["selected_jobs"] if item["review_number"] == 25)
    result = evaluate_seniority_guard(
        SemanticJobInput(
            item["company_name"], item["title"], "", tuple(item["locations"]),
            item["work_mode"],
        ),
        PRIMARY,
        RULES,
    )
    assert item["title"] == "Junior Project Manager"
    assert evaluate_current_candidate_market(
        SemanticJobInput(
            item["company_name"], item["title"], "", tuple(item["locations"]),
            item["work_mode"],
        ),
        PRIMARY,
        MARKET_RULES,
    ).status is CurrentCandidateMarketStatus.UNCERTAIN
    assert result.active is True
    assert result.reason_code is SeniorityGuardReason.EXPLICIT_JUNIOR_ROLE
