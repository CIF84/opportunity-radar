from __future__ import annotations

import inspect
import json
from pathlib import Path

from opportunity_radar.decision_preferences import (
    load_preference_effect_policy,
    load_preference_matching_rules,
)
from opportunity_radar.decision_recomposition import recompose_cached_decision
from opportunity_radar.eligibility import evaluate_eligibility
from opportunity_radar.market_status import evaluate_current_candidate_market, load_market_normalization_rules
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import SemanticJobInput
from opportunity_radar.semantic import FakeSemanticAssessor
from opportunity_radar.features import extract_features
from opportunity_radar.semantic_allocation_audit import (
    _stage_retained,
    classify_presemantic_evidence,
    load_allocation_audit_config,
)
from opportunity_radar.seniority_guard import load_seniority_guard_rules


ROOT = Path(__file__).resolve().parents[1]


def _context():
    taxonomy = load_taxonomy(ROOT / "config/taxonomy.yaml")
    profile = load_candidate_profile(ROOT / "config/candidate.yaml", taxonomy)
    config = load_allocation_audit_config(ROOT / "experiments/semantic_compute_allocation_v1.yaml")
    preference_policy = load_preference_effect_policy(ROOT / "config/preference_effect_policy.yaml")
    preference_rules = load_preference_matching_rules(taxonomy, ROOT / "config/preference_matching_rules.yaml")
    seniority = load_seniority_guard_rules(ROOT / "config/seniority_guard_rules.yaml")
    return taxonomy, profile, config, preference_policy, preference_rules, seniority


def _triage(job):
    taxonomy, profile, config, policy, rules, seniority = _context()
    return classify_presemantic_evidence(
        job, profile, taxonomy, config, policy, rules, seniority,
    )


def test_config_is_small_valid_and_taxonomy_backed():
    config = load_allocation_audit_config(ROOT / "experiments/semantic_compute_allocation_v1.yaml")
    assert config.experiment_id == "EXP-SEMANTIC-ALLOCATION-001"
    assert len(config.role_patterns) == 5
    assert "ai_enabled_work" in config.positive_concepts


def test_cache_status_cannot_enter_presemantic_classifier():
    assert "cache" not in inspect.signature(classify_presemantic_evidence).parameters
    assert "semantic" not in inspect.signature(classify_presemantic_evidence).parameters


def test_positive_evidence_overrides_obvious_role_family():
    result = _triage(SemanticJobInput(
        "Example", "Software Engineer, AI Transformation",
        "Lead artificial intelligence transformation and business analytics.",
        (), "unspecified", None, None,
    ))
    assert result.state == "SEMANTIC_PRIORITY"
    assert result.obvious_role_families == ("hands_on_software_engineering",)
    assert "POSITIVE_OVERRIDES_OBVIOUS_ROLE_FAMILY" in result.reasons
    assert result.positive_title_concepts


def test_obvious_role_without_positive_evidence_is_deferred():
    result = _triage(SemanticJobInput(
        "Example", "Warehouse Material Handler",
        "Move packages and operate material-handling equipment.",
        (), "onsite", None, None,
    ))
    assert result.state == "SEMANTIC_DEFER"


def test_unknown_plausibility_remains_optional_not_rejected():
    result = _triage(SemanticJobInput(
        "Example", "Program Lead",
        "Coordinate a complex global program with partners across regions, maintain plans, "
        "prepare status materials, organize recurring governance, resolve dependencies, and "
        "support leaders with clear documentation. The role works with several teams and "
        "requires careful communication, organization, judgment, and follow-through while "
        "the detailed functional scope remains broad rather than tied to a specialist family.",
        (), "unspecified", None, None,
    ))
    assert result.state == "SEMANTIC_OPTIONAL"


def test_sparse_evidence_escalates_toward_semantics():
    result = _triage(SemanticJobInput(
        "Example", "Unusual Opportunity", "Details available later.",
        (), "unspecified", None, None,
    ))
    assert result.state == "SEMANTIC_PRIORITY"


def test_hit_to_miss_does_not_change_funnel_eligibility():
    _, _, config, *_ = _context()
    base = {
        "audit_identity": "same", "normal_candidate": True,
        "presemantic_triage": {
            "state": "SEMANTIC_OPTIONAL",
            "positive_concepts": [],
            "sparse_description": False,
        },
    }
    for stage in (
        "F0_CURRENT_ROUTED", "F1_DETERMINISTIC_COMPATIBLE",
        "F2_CONSERVATIVE_ROLE_DEFER", "F3_TITLE_PRIORITY_ONLY_SCENARIO",
        "F4_ANY_LEXICAL_POSITIVE_SCENARIO", "F5_PRIORITY_WITH_EXPLORATION",
    ):
        hit = dict(base, semantic_cache_status="COMPATIBLE_SEMANTIC_CACHE_HIT")
        miss = dict(base, semantic_cache_status="SEMANTIC_CACHE_MISS")
        assert _stage_retained(hit, stage, config) == _stage_retained(miss, stage, config)


def test_cached_semantics_recompose_without_changing_identity():
    taxonomy, profile, _, policy, rules, seniority = _context()
    job = SemanticJobInput(
        "Example", "Business Analytics Lead",
        "Lead business analytics, decision support and transformation.",
        ({"raw": "Prague, Czechia", "city": "Prague", "country": "Czechia", "region": None},),
        "hybrid", None, None,
    )
    semantic = FakeSemanticAssessor(taxonomy).assess(
        job, profile.semantic_input(), extract_features(job, taxonomy),
    )
    semantic_payload = {
        "dimensions": {
            key: {
                "score": value.score, "confidence": value.confidence,
                "reason": value.reason, "job_evidence": list(value.job_evidence),
                "candidate_evidence": list(value.candidate_evidence),
            }
            for key, value in semantic.dimensions.items()
        },
        "strengths": [item.__dict__ for item in semantic.strengths],
        "gaps": [item.__dict__ for item in semantic.gaps],
        "risks": [item.__dict__ for item in semantic.risks],
    }
    before = json.dumps(semantic_payload, sort_keys=True)
    identity = {"semantic_assessment_id": 42, "content_fingerprint": "abc"}
    result = recompose_cached_decision(
        job, profile, semantic_payload, identity,
        evaluate_current_candidate_market(job, profile, load_market_normalization_rules(ROOT / "config/market_status_rules.yaml")),
        evaluate_eligibility(job, profile), policy, rules, seniority,
    )
    assert result.semantic_identity == identity
    assert json.dumps(semantic_payload, sort_keys=True) == before
    assert result.recommendation is not None


def test_private_allocation_outputs_are_ignored_but_aggregate_is_trackable():
    import subprocess

    private = subprocess.run(
        ["git", "check-ignore", "-q", "output/semantic_compute_allocation/example/audit.json"],
        cwd=ROOT,
    )
    aggregate = subprocess.run(
        ["git", "check-ignore", "-q", "output/semantic_compute_allocation/example/aggregate_summary.json"],
        cwd=ROOT,
    )
    assert private.returncode == 0
    assert aggregate.returncode == 1
