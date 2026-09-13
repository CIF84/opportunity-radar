from __future__ import annotations

from pathlib import Path

from opportunity_radar.candidate_direction_audit import (
    _baseline_profile,
    _baseline_rules,
    _promotion_gate_results,
    build_sanitized_summary,
    load_candidate_direction_audit_config,
)
from opportunity_radar.decision_preferences import load_preference_matching_rules
from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy


ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / "experiments/candidate_direction_promotion_v1.yaml"


def _profiles_and_rules():
    config = load_candidate_direction_audit_config(CONFIG_PATH)
    taxonomy = load_taxonomy(ROOT / "config/taxonomy.yaml")
    promoted = load_candidate_profile(ROOT / "config/candidate.yaml", taxonomy)
    baseline = _baseline_profile(promoted, config)
    rules = load_preference_matching_rules(
        taxonomy, ROOT / "config/preference_matching_rules.yaml",
    )
    return config, baseline, promoted, rules


def test_candidate_direction_config_and_profile_identity_boundaries():
    config, baseline, promoted, _ = _profiles_and_rules()
    portability = load_candidate_profile(
        ROOT / "config/candidate_portability_test.yaml",
        load_taxonomy(ROOT / "config/taxonomy.yaml"),
    )

    assert config.experiment_id == "EXP-CANDIDATE-DIRECTION-001"
    assert baseline.version == 3
    assert promoted.version == 4
    assert portability.profile_id == "portability_test_engineer"
    assert baseline.semantic_profile_fingerprint == promoted.semantic_profile_fingerprint
    assert baseline.scoring_preference_fingerprint == promoted.scoring_preference_fingerprint
    assert baseline.market_access_policy_fingerprint == promoted.market_access_policy_fingerprint
    assert baseline.decision_preference_fingerprint != promoted.decision_preference_fingerprint
    assert baseline.full_profile_fingerprint != promoted.full_profile_fingerprint
    assert {item.concept_id for item in promoted.decision_preferences.entries} - {
        item.concept_id for item in baseline.decision_preferences.entries
    } == {"account_management_execution"}
    promoted_ids = {item.concept_id for item in promoted.decision_preferences.entries}
    assert "business_analytics" not in promoted_ids
    assert "decision_intelligence" not in promoted_ids


def test_baseline_matching_rules_exclude_only_promoted_concepts():
    config, _, _, promoted_rules = _profiles_and_rules()
    baseline = _baseline_rules(promoted_rules, config)
    assert promoted_rules.version == 2
    assert baseline.version == 1
    assert set(promoted_rules.concepts) - set(baseline.concepts) == {
        "account_management_execution"
    }


def test_promotion_gate_evaluation_is_deterministic_and_zero_call():
    config, baseline, promoted, rules = _profiles_and_rules()
    worthiness = {"known_worth_demotions": 0}
    cached = {"semantic_reassessments": 0}
    retrospective = {
        "known_human_apply_demotions": 0,
        "semantic_reassessments": 0,
        "cluster_membership_changed": False,
    }
    first = _promotion_gate_results(
        config, baseline, promoted, worthiness, cached, retrospective, rules,
    )
    second = _promotion_gate_results(
        config, baseline, promoted, worthiness, cached, retrospective, rules,
    )
    assert first == second
    assert all(item["status"] == "PASS" for item in first)


def test_repository_safe_summary_excludes_private_rows_and_notes():
    result = {
        "experiment_id": "EXP-CANDIDATE-DIRECTION-001",
        "run_id": "fixture",
        "created_at": "2026-09-13T00:00:00+00:00",
        "experiment_type": "CANDIDATE_DIRECTION_PROMOTION_AUDIT",
        "concept_audit": [{
            "concept_id": "account_management_execution",
            "verdict": "PROMOTE_NEGATIVE",
        }],
        "counterfactual": {"frozen_worthiness_sample": {"sample_size": 60}},
        "fingerprints": {"baseline": {}, "promoted": {}},
        "promotion_gates": [{"gate": "fixture", "status": "PASS"}],
        "promotion_decision": "PROMOTE_VERSIONED_ACCOUNT_MANAGEMENT_AVERSION",
        "stretch_envelope": {"runtime_implemented": False},
        "integrity": {"semantic_calls": 0},
        "limitations": [],
        "private_detail": [{"note": "must never be copied"}],
    }
    summary = build_sanitized_summary(result, "a" * 64)
    rendered = str(summary)
    assert "must never be copied" not in rendered
    assert "private_detail" not in summary
    assert summary["privacy"]["private_detailed_artifact_sha256"] == "a" * 64
