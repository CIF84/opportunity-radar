from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from opportunity_radar.decision_preferences import (
    assess_decision_preferences,
    load_preference_effect_policy,
    load_preference_matching_rules,
)
from opportunity_radar.live_validation import _clustered_assessed_pool
from opportunity_radar.market_status import load_market_normalization_rules
from opportunity_radar.models import JobLocation, JobReference, NormalizedJob, WorkMode
from opportunity_radar.phase3_config import (
    Phase3ConfigurationError,
    digest,
    load_candidate_profile,
    load_taxonomy,
)
from opportunity_radar.phase3_models import (
    CORE_DIMENSIONS,
    DecisionPreference,
    DecisionPreferences,
    DimensionScore,
    SemanticAssessment,
    SemanticJobInput,
)
from opportunity_radar.phase3_pipeline import assess_opportunity
from opportunity_radar.phase3_repository import Phase3Repository
from opportunity_radar.semantic import SEMANTIC_CONTRACT_VERSION
from opportunity_radar.state_models import DetailObservation, SourceOutcome
from opportunity_radar.state_repository import SCHEMA_VERSION, StateRepository


ROOT = Path(__file__).parents[1]
TAXONOMY = load_taxonomy(ROOT / "config/taxonomy.yaml")
PROFILE = load_candidate_profile(ROOT / "config/candidate.yaml", TAXONOMY)
POLICY = load_preference_effect_policy(ROOT / "config/preference_effect_policy.yaml")
RULES = load_preference_matching_rules(
    TAXONOMY, ROOT / "config/preference_matching_rules.yaml",
)
MARKET_RULES = load_market_normalization_rules(ROOT / "config/market_status_rules.yaml")


def _profile_with(*items: tuple[str, str, str]):
    decision = DecisionPreferences(
        1, 99,
        tuple(DecisionPreference(concept, source, stance) for concept, source, stance in items),
    )
    return replace(
        PROFILE,
        decision_preferences=decision,
        decision_preference_fingerprint=digest(decision.payload()),
        full_profile_fingerprint=digest((PROFILE.full_profile_fingerprint, decision.payload())),
    )


def _job(text: str, title: str = "Role") -> SemanticJobInput:
    return SemanticJobInput(
        "Example", title, text,
        ({"raw": "Prague, Czechia", "city": "Prague", "region": None, "country": "Czechia"},),
        "hybrid",
    )


def _assess(profile, text, *, semantic=None, score=7.0, title="Role"):
    return assess_decision_preferences(
        _job(text, title), semantic, profile, score, POLICY, RULES,
    )


def test_profiles_share_generic_decision_preference_schema_and_resolve_taxonomy():
    other = load_candidate_profile(ROOT / "config/candidate_portability_test.yaml", TAXONOMY)
    assert PROFILE.version == other.version == 3
    assert set(PROFILE.decision_preferences.payload()) == set(other.decision_preferences.payload())
    for profile in (PROFILE, other):
        for item in profile.decision_preferences.entries:
            TAXONOMY.require(item.concept_id)


def test_decision_preference_change_preserves_frozen_phase3_fingerprints(tmp_path):
    raw = yaml.safe_load((ROOT / "config/candidate.yaml").read_text(encoding="utf-8"))
    raw["profile"]["version"] += 1
    raw["decision_preferences"]["preference_version"] += 1
    raw["decision_preferences"]["entries"][0]["stance"] = "POSITIVE"
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    changed = load_candidate_profile(path, TAXONOMY)

    assert changed.full_profile_fingerprint != PROFILE.full_profile_fingerprint
    assert changed.decision_preference_fingerprint != PROFILE.decision_preference_fingerprint
    assert changed.semantic_profile_fingerprint == PROFILE.semantic_profile_fingerprint == "6579b21e2bc22fef927ca17bdf6083b7e9a099bd5810b49528f589c83793819b"
    assert changed.scoring_preference_fingerprint == PROFILE.scoring_preference_fingerprint == "9237433984fb06f964248b199a08a6bd3ed9ddf0a0f0b341c13a0cb278db0e8a"
    assert changed.market_access_policy_fingerprint == PROFILE.market_access_policy_fingerprint
    assert changed.semantic_payload() == PROFILE.semantic_payload()


@pytest.mark.parametrize(("field", "value", "message"), [
    ("stance", "STRONG_NEGATIVE", "invalid decision preference stance"),
    ("source_type", "PERSONALITY", "invalid decision preference source type"),
])
def test_decision_preference_controlled_values(field, value, message, tmp_path):
    raw = yaml.safe_load((ROOT / "config/candidate.yaml").read_text(encoding="utf-8"))
    raw["decision_preferences"]["entries"][0][field] = value
    path = tmp_path / "candidate.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(Phase3ConfigurationError, match=message):
        load_candidate_profile(path, TAXONOMY)


def test_effect_mapping_omission_and_score_bounds():
    profile = _profile_with(
        ("ai_enabled_work", "PREFERENCE", "STRONG_POSITIVE"),
        ("business_operations", "PREFERENCE", "POSITIVE"),
        ("orthopaedics", "PREFERENCE", "NEGATIVE"),
        ("continuous_learning", "PREFERENCE", "NEUTRAL"),
    )
    result = _assess(
        profile,
        "AI business operations in orthopaedics with continuous learning.",
        score=9.9,
    )
    assert [item.numeric_effect for item in result.matched_effects] == [0.4, 0.2, -0.3, 0.0]
    assert result.raw_total_effect == result.bounded_total_effect == 0.3
    assert result.base_composite_score == 9.9
    assert result.decision_adjusted_score == 10.0
    assert _assess(profile, "Unrelated legal role.").bounded_total_effect == 0


def test_effects_clip_and_one_concept_never_double_counts_synonyms():
    positive = _profile_with(
        ("ai_enabled_work", "PREFERENCE", "STRONG_POSITIVE"),
        ("transformation_execution", "PREFERENCE", "STRONG_POSITIVE"),
        ("implementation_ownership", "PREFERENCE", "STRONG_POSITIVE"),
    )
    result = _assess(
        positive,
        "AI, artificial intelligence and automation transformation. Lead implementation end-to-end delivery.",
    )
    assert len(result.matched_effects) == 3
    assert result.raw_total_effect == 1.2
    assert result.bounded_total_effect == 1.0

    negative = _profile_with(
        ("orthopaedics", "PREFERENCE", "NEGATIVE"),
        ("customer_service_operations", "PREFERENCE", "NEGATIVE"),
        ("legacy_agency_sector", "CONVICTION", "NEGATIVE"),
        ("social_influencer_operations", "PREFERENCE", "NEGATIVE"),
    )
    result = _assess(
        negative,
        "Orthopaedics customer service operations at an advertising agency supporting influencer marketing.",
        score=0.2,
    )
    assert result.raw_total_effect == -1.2
    assert result.bounded_total_effect == -1.0
    assert result.decision_adjusted_score == 0.0


def test_regression_tradeoffs_are_narrow_and_not_hidden_vetoes():
    wpp = _profile_with(
        ("legacy_agency_sector", "CONVICTION", "NEGATIVE"),
        ("ai_enabled_work", "PREFERENCE", "STRONG_POSITIVE"),
        ("implementation_ownership", "PREFERENCE", "STRONG_POSITIVE"),
    )
    result = _assess(
        wpp,
        "Automation and AI at an advertising agency. Lead implementation across the company.",
    )
    assert result.bounded_total_effect == 0.5
    assert all(item.stance != "INELIGIBLE" for item in result.matched_effects)

    advisory = _profile_with(
        ("advisory_without_implementation_ownership", "PREFERENCE", "NEGATIVE"),
        ("implementation_ownership", "PREFERENCE", "STRONG_POSITIVE"),
    )
    assert _assess(advisory, "Provide strategic advisory consulting.").bounded_total_effect == -0.3
    assert _assess(advisory, "Consulting role. Lead implementation and delivery.").bounded_total_effect == 0.4

    narrow = _profile_with(
        ("orthopaedics", "PREFERENCE", "NEGATIVE"),
        ("customer_service_operations", "PREFERENCE", "NEGATIVE"),
        ("business_operations", "PREFERENCE", "POSITIVE"),
    )
    assert _assess(narrow, "Biology technology role in healthcare.").bounded_total_effect == 0
    assert _assess(narrow, "Orthopaedics portfolio role.").bounded_total_effect == -0.3
    assert _assess(narrow, "Customer service operations.").bounded_total_effect == -0.3
    assert _assess(narrow, "Commercial business operations.").bounded_total_effect == 0.2


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


def test_preference_recompute_reuses_semantics_and_preserves_lifecycle_and_cluster(tmp_path):
    state = StateRepository(tmp_path / "state.sqlite3")
    at = datetime(2026, 9, 5, tzinfo=timezone.utc)
    job = NormalizedJob(
        "acme", "Acme", "1", "Automation Lead",
        [JobLocation("Prague, Czechia", "Prague", None, "Czechia")],
        WorkMode.HYBRID, "https://example.test/1",
        "Lead AI automation implementation and delivery for business operations.",
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
    semantic_job = _job(job.description, job.title)
    assessor = _HighAssessor()
    assess_opportunity(
        semantic_job, PROFILE, TAXONOMY, assessor,
        repository=Phase3Repository(state),
        job_instance_id=instance["job_instance_id"],
        job_observation_id=observation["job_observation_id"],
        content_fingerprint=observation["fingerprint"],
    )
    before = {
        name: [dict(row) for row in state.rows(name)]
        for name in ("semantic_assessments", "events", "job_instances")
    }
    original_pool, _ = _clustered_assessed_pool(
        state.path, PROFILE, assessor.assessor_version, MARKET_RULES, TAXONOMY,
    )
    changed = _profile_with(
        ("ai_enabled_work", "PREFERENCE", "NEGATIVE"),
        ("implementation_ownership", "PREFERENCE", "NEGATIVE"),
        ("business_operations", "PREFERENCE", "NEGATIVE"),
    )
    changed_pool, _ = _clustered_assessed_pool(
        state.path, changed, assessor.assessor_version, MARKET_RULES, TAXONOMY,
    )
    policy_raw = yaml.safe_load(
        (ROOT / "config/preference_effect_policy.yaml").read_text(encoding="utf-8")
    )
    policy_raw["version"] = 2
    policy_raw["stance_to_effect"]["NEGATIVE"] = -0.4
    policy_path = tmp_path / "preference_effect_policy.yaml"
    policy_path.write_text(yaml.safe_dump(policy_raw, sort_keys=False), encoding="utf-8")
    policy_changed_pool, _ = _clustered_assessed_pool(
        state.path, changed, assessor.assessor_version, MARKET_RULES, TAXONOMY,
        policy_path, ROOT / "config/preference_matching_rules.yaml",
    )

    assert assessor.calls == 1
    assert original_pool[0]["semantic_assessment_id"] == changed_pool[0]["semantic_assessment_id"]
    assert original_pool[0]["cluster_fingerprint"] == changed_pool[0]["cluster_fingerprint"]
    assert original_pool[0]["base_composite_score"] == changed_pool[0]["base_composite_score"]
    assert original_pool[0]["score"] != changed_pool[0]["score"]
    assert original_pool[0]["recommendation"] == "APPLY"
    assert changed_pool[0]["recommendation"] == "REVIEW"
    assert changed_pool[0]["score"] != policy_changed_pool[0]["score"]
    assert changed_pool[0]["semantic_assessment_id"] == policy_changed_pool[0]["semantic_assessment_id"]
    assert changed_pool[0]["cluster_fingerprint"] == policy_changed_pool[0]["cluster_fingerprint"]
    assert changed_pool[0]["preference_assessment"]["effect_policy_fingerprint"] != policy_changed_pool[0]["preference_assessment"]["effect_policy_fingerprint"]
    assert changed_pool[0]["preference_assessment"]["decision_preference_fingerprint"] == changed.decision_preference_fingerprint
    for name, rows in before.items():
        assert [dict(row) for row in state.rows(name)] == rows
    assert SCHEMA_VERSION == 3
