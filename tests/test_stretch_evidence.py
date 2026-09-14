from __future__ import annotations

import inspect
import subprocess
from dataclasses import replace
from pathlib import Path

from opportunity_radar.phase3_config import load_candidate_profile, load_taxonomy
from opportunity_radar.phase3_models import DecisionPreferences, SemanticJobInput
from opportunity_radar.stretch_evidence import (
    RequirementStrength,
    StretchClass,
    SupportState,
    assess_stretch,
    build_sanitized_summary,
    load_stretch_audit_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "experiments/stretch_evidence_boundary_v1.yaml"
AGGREGATE_PATH = ROOT / "output/stretch_evidence_boundary/spec019-stretch-evidence-20260913-v3/aggregate_summary.json"


def _context():
    config = load_stretch_audit_config(CONFIG_PATH)
    taxonomy = load_taxonomy(ROOT / "config/taxonomy.yaml")
    profile = load_candidate_profile(ROOT / "config/candidate.yaml", taxonomy)
    return config, profile


def _job(title: str | None, description: str = "") -> SemanticJobInput:
    return SemanticJobInput(
        "Example", title, description, (), "unspecified", None, None,
    )


def test_stretch_config_is_bounded_taxonomy_validated_and_unpromoted():
    config, _ = _context()
    assert config.experiment_id == "EXP-STRETCH-EVIDENCE-001"
    assert config.policy.version == "stretch-evidence-v1"
    assert len(config.policy.role_requirements) == 13
    assert config.raw["privacy"]["detailed_artifact"] == "PRIVATE_LOCAL"
    assert "preference" not in inspect.signature(assess_stretch).parameters
    assert "market" not in inspect.signature(assess_stretch).parameters


def test_preference_and_market_policy_cannot_change_stretch_class_or_fingerprint():
    config, profile = _context()
    job = _job("Senior Project Manager - Enterprise AI", "Lead a strategic AI program.")
    baseline = assess_stretch(job, profile, config.policy)
    changed_preferences = replace(
        profile,
        decision_preferences=DecisionPreferences(
            schema_version=1, preference_version=999, entries=(),
        ),
        decision_preference_fingerprint="changed",
    )
    changed_market = replace(
        changed_preferences,
        market_access_policy=replace(
            profile.market_access_policy,
            work_access={"czechia": "INCOMPATIBLE"},
        ),
        market_access_policy_fingerprint="changed",
    )
    after = assess_stretch(job, changed_market, config.policy)
    assert after.stretch_class == baseline.stretch_class
    assert after.input_fingerprint == baseline.input_fingerprint
    assert after.assessment_fingerprint == baseline.assessment_fingerprint


def test_explicit_none_profession_mismatch_can_be_excessive_but_omission_is_unknown():
    config, profile = _context()
    rule = next(item for item in config.policy.role_requirements if item.concept_id == "software_engineering")
    removed = set(rule.direct_capabilities) | set(rule.adjacent_capabilities)
    unknown_profile = replace(
        profile,
        capabilities=tuple(
            item for item in profile.capabilities if item["capability_id"] not in removed
        ),
    )
    unknown = assess_stretch(_job("Software Engineer"), unknown_profile, config.policy)
    explicit_none_profile = replace(
        unknown_profile,
        capabilities=unknown_profile.capabilities + ({
            "capability_id": "software_engineering",
            "level": "NONE",
            "confidence": "HIGH",
        },),
    )
    unsupported = assess_stretch(
        _job("Software Engineer"), explicit_none_profile, config.policy,
    )
    assert unknown.stretch_class is StretchClass.UNRESOLVED
    assert unknown.requirements[0].support_state is SupportState.UNKNOWN
    assert unsupported.stretch_class is StretchClass.EXCESSIVE_STRETCH
    assert unsupported.requirements[0].reason_code == "EXPLICIT_CAPABILITY_NONE"


def test_title_seniority_alone_cannot_create_excessive_stretch():
    config, profile = _context()
    result = assess_stretch(
        _job("Senior Business Operations Manager"), profile, config.policy,
    )
    assert result.stretch_class is StretchClass.CURRENT_FIT
    assert not result.decisive_requirement_concepts


def test_mandatory_degree_absence_is_decisive_but_preferred_absence_is_not():
    config, profile = _context()
    mandatory = assess_stretch(
        _job("Lawyer", "A bachelor's degree is required for this position."),
        profile,
        config.policy,
    )
    preferred = assess_stretch(
        _job("Lawyer", "A bachelor's degree is preferred for this position."),
        profile,
        config.policy,
    )
    mandatory_credential = next(x for x in mandatory.requirements if x.concept_id == "bachelors_degree")
    preferred_credential = next(x for x in preferred.requirements if x.concept_id == "bachelors_degree")
    assert mandatory_credential.requirement_strength is RequirementStrength.CORE
    assert mandatory.stretch_class is StretchClass.EXCESSIVE_STRETCH
    assert preferred_credential.requirement_strength is RequirementStrength.PREFERRED
    assert preferred.stretch_class is StretchClass.UNRESOLVED


def test_developing_adjacent_capability_stays_manageable_not_excessive():
    config, profile = _context()
    result = assess_stretch(
        _job("AI Engineer - Security", "Build AI-enabled security capabilities."),
        profile,
        config.policy,
    )
    assert result.stretch_class is StretchClass.MANAGEABLE_STRETCH
    assert not result.decisive_requirement_concepts


def test_missing_vacancy_evidence_is_unresolved_and_replay_is_deterministic():
    config, profile = _context()
    job = _job(None, "Evidence is unavailable.")
    first = assess_stretch(job, profile, config.policy)
    second = assess_stretch(job, profile, config.policy)
    assert first.stretch_class is StretchClass.UNRESOLVED
    assert first.payload() == second.payload()


def test_three_worth_shape_regressions_are_protected_from_excessive_stretch():
    config, profile = _context()
    cases = [
        _job("AI Engineer - Security", "Develop AI security services and work with engineering teams."),
        _job("Senior AI Transformation Consultant", "Lead AI transformation implementations for clients."),
        _job("Senior Project Manager - Enterprise AI", "Lead an enterprise AI transformation program."),
    ]
    assert [assess_stretch(job, profile, config.policy).stretch_class for job in cases] == [
        StretchClass.MANAGEABLE_STRETCH,
        StretchClass.MANAGEABLE_STRETCH,
        StretchClass.MANAGEABLE_STRETCH,
    ]


def test_repository_safe_summary_excludes_private_rows_and_human_notes():
    result = {
        "experiment_id": "EXP-STRETCH-EVIDENCE-001",
        "experiment_type": "STRETCH_EVIDENCE_BOUNDARY_AUDIT",
        "run_id": "fixture",
        "created_at": "2026-09-13T00:00:00+00:00",
        "stretch_contract": {"runtime_promoted": False},
        "frozen_human_sample": {"sample_size": 60},
        "compute_allocation_counterfactuals": {},
        "current_corpus_counterfactuals": {},
        "current_corpus": {"population_metadata": {}, "class_distribution": {}},
        "fingerprints": {},
        "safety_gates": [],
        "integrity": {"semantic_calls": 0},
        "architecture_conclusion": "diagnostic",
        "recommendation": "review",
        "limitations": [],
        "private_detail": [{"human_note": "must remain private"}],
    }
    summary = build_sanitized_summary(result, "a" * 64)
    rendered = str(summary)
    assert "must remain private" not in rendered
    assert "private_detail" not in summary
    assert summary["privacy"]["private_detailed_artifact_sha256"] == "a" * 64


def test_frozen_repository_safe_result_protects_all_three_worth_cases():
    import json

    result = json.loads(AGGREGATE_PATH.read_text(encoding="utf-8"))
    sample = result["frozen_human_sample"]
    assert sample["sample_size"] == 60
    assert sample["worth_count"] == 3
    assert sample["worth_excessive_count"] == 0
    assert sample["worth_protection_recall"] == 1.0
    assert all(item["status"] == "PASS" for item in result["safety_gates"])
    assert result["stretch_contract"]["runtime_promoted"] is False
    assert result["integrity"]["semantic_calls"] == 0
    assert result["integrity"]["semantic_cache_writes"] == 0
    assert result["integrity"]["live_source_calls"] == 0
    assert result["integrity"]["sqlite_writes"] == 0
    assert result["integrity"]["lifecycle_changes"] == 0
    assert result["integrity"]["cluster_changes"] == 0
    assert result["integrity"]["recommendation_changes"] == 0


def test_private_stretch_output_is_ignored_but_aggregate_is_trackable():
    private = subprocess.run(
        ["git", "check-ignore", "-q", "output/stretch_evidence_boundary/example/audit.json"],
        cwd=ROOT,
    )
    aggregate = subprocess.run(
        ["git", "check-ignore", "-q", "output/stretch_evidence_boundary/example/aggregate_summary.json"],
        cwd=ROOT,
    )
    assert private.returncode == 0
    assert aggregate.returncode == 1
