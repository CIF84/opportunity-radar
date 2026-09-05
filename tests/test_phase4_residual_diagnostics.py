from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
from pathlib import Path

import pytest

from opportunity_radar.phase4_residual_diagnostics import (
    DiagnosticCase,
    classify_diagnostic_case,
    load_residual_diagnostics_config,
    run_residual_diagnostics,
)
from opportunity_radar.state_repository import SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/phase4_residual_diagnostics_v1.yaml"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _has_private_evidence() -> bool:
    config = load_residual_diagnostics_config(CONFIG)
    return all(Path(path).exists() for path in (
        config.parent_detailed_replay_path,
        load_residual_diagnostics_config(CONFIG).parent_aggregate_path,
    ))


def _posting(market: str, preference: list[dict] | None = None) -> dict:
    return {
        "market_assessment": {"status": market},
        "preference_assessment": {"matched_effects": preference or []},
    }


def test_residual_diagnostic_config_is_bounded_and_taxonomy_validated():
    config = load_residual_diagnostics_config(CONFIG)
    assert config.experiment_id == "EXP-PHASE4-RESIDUAL-001"
    assert {item.review_number for item in config.cases} == {10, 13, 17, 18, 23, 27}
    assert len(config.fingerprint) == 64


@pytest.mark.parametrize(
    ("kind", "before", "after", "expected"),
    [
        ("NORMALIZATION_CONTROL", _posting("UNCERTAIN"), _posting("OUT_OF_SCOPE"), "FIXED_DETERMINISTIC_NORMALIZATION"),
        ("PREFERENCE_RESIDUAL", _posting("UNCERTAIN", []), _posting("UNCERTAIN", [{"concept_id": "orthopaedics"}]), "FIXED_GENERIC_PREFERENCE_MATCHING"),
        ("CONSERVATIVE_MARKET_UNCERTAINTY", _posting("UNCERTAIN"), _posting("UNCERTAIN"), "CORRECTLY_UNCERTAIN_MARKET_ACCESS"),
        ("PREFERENCE_RESIDUAL", _posting("UNCERTAIN"), _posting("UNCERTAIN"), "UNREPRESENTED_PREFERENCE_OR_CONVICTION"),
        ("SEMANTIC_CONTROL", _posting("IN_SCOPE"), _posting("IN_SCOPE"), "SEMANTIC_V1_RESIDUAL"),
    ],
)
def test_diagnostic_classification_is_deterministic(kind, before, after, expected):
    case = DiagnosticCase(1, kind, (), None, "TEST")
    assert classify_diagnostic_case(case, before, after) == expected
    assert classify_diagnostic_case(case, before, after) == expected


@pytest.mark.skipif(not _has_private_evidence(), reason="private local replay evidence is unavailable")
def test_corrected_replay_is_zero_call_read_only_and_bounded(tmp_path, monkeypatch):
    config = load_residual_diagnostics_config(CONFIG)
    base = __import__("opportunity_radar.phase4_replay", fromlist=["load_replay_config"]).load_replay_config(config.base_replay_config)
    protected = [
        ROOT / base.baseline[key]
        for key in ("batch_path", "report_path", "review_path", "judgments_path", "database_path")
    ] + [Path(config.parent_aggregate_path), Path(config.parent_detailed_replay_path)]
    before = {path: _hash(path) for path in protected}
    candidate_hash = _hash(ROOT / "config/candidate.yaml")
    preference_hash = _hash(ROOT / "config/preference_effect_policy.yaml")
    matching_hash = _hash(ROOT / "config/preference_matching_rules.yaml")

    def forbidden_network(*args, **kwargs):
        raise AssertionError("corrected replay attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    result = run_residual_diagnostics(CONFIG, tmp_path, run_id="corrected-test", write_artifact=False)

    assert result["experiment_type"] == "POST_HOC_CORRECTED_RETROSPECTIVE"
    assert result["comparison"]["market_status_changes"] == 1
    assert result["comparison"]["decision_changes"] == 1
    assert result["comparison"]["decisions_changed_by_texas_normalization"] == 1
    assert result["comparison"]["decisions_changed_by_preference_matching"] == 0
    assert result["broader_corpus_impact"] == {
        "assessable_active_jobs": 406,
        "market_status_distribution_before": {
            "IN_SCOPE": 56, "OUT_OF_SCOPE": 85, "UNCERTAIN": 265,
        },
        "market_status_distribution_after": {
            "IN_SCOPE": 56, "OUT_OF_SCOPE": 97, "UNCERTAIN": 253,
        },
        "market_status_changes": 12,
        "external_calls": 0,
    }
    assert result["metrics"]["opportunity_level"]["attention_shortlist_apply_recall"] == 1.0
    assert result["zero_call_evidence"]["external_semantic_calls"] == 0
    assert result["zero_call_evidence"]["live_source_calls"] == 0
    assert result["zero_call_evidence"]["cache_rows_compatible"] == 30
    assert result["residual_classification_counts"] == {
        "CORRECTLY_UNCERTAIN_MARKET_ACCESS": 1,
        "FIXED_DETERMINISTIC_NORMALIZATION": 1,
        "SEMANTIC_V1_RESIDUAL": 2,
        "UNREPRESENTED_PREFERENCE_OR_CONVICTION": 2,
    }
    assert result["rule_fingerprint_comparison"]["market_rules"]["changed"] is True
    assert result["rule_fingerprint_comparison"]["preference_matching_rules"]["changed"] is False
    assert all(result["frozen_equivalence"].values())
    assert {path: _hash(path) for path in protected} == before
    assert _hash(ROOT / "config/candidate.yaml") == candidate_hash
    assert _hash(ROOT / "config/preference_effect_policy.yaml") == preference_hash
    assert _hash(ROOT / "config/preference_matching_rules.yaml") == matching_hash
    connection = sqlite3.connect(f"file:{base.baseline['database_path']}?mode=ro", uri=True)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 3
    finally:
        connection.close()


@pytest.mark.skipif(not _has_private_evidence(), reason="private local replay evidence is unavailable")
def test_corrected_artifact_keeps_detailed_evidence_private(tmp_path):
    result = run_residual_diagnostics(CONFIG, tmp_path, run_id="corrected-artifact")
    detailed = tmp_path / "corrected-artifact/replay.json"
    report = tmp_path / "corrected-artifact/report.md"
    summary_path = tmp_path / "corrected-artifact/aggregate_summary.json"
    assert detailed.exists() and report.exists() and summary_path.exists()
    summary = json.loads(summary_path.read_text())
    assert summary["schema_version"] == 2
    assert summary["experiment_type"] == "POST_HOC_CORRECTED_RETROSPECTIVE"
    assert summary["parent_replay"]["run_id"] == "phase4-replay-20260905T110537Z-e916fcc9"
    assert summary["correction_attribution"] == {
        "texas_normalization_decision_changes": 1,
        "preference_matching_decision_changes": 0,
    }
    serialized = summary_path.read_text()
    for private_key in (
        "review_number", "job_instance_id", "candidate_evidence",
        "matched_evidence", "unrepresented_human_factor",
    ):
        assert private_key not in serialized
    assert result["artifact_paths"]["private_detailed_json"] == str(detailed)


def test_corrected_output_policy_is_inherited_from_phase4_replay_ignore_rule():
    ignore = (ROOT / ".gitignore").read_text()
    assert "output/phase4_replay/**/*" in ignore
    assert "!output/phase4_replay/**/aggregate_summary.json" in ignore
