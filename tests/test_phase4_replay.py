from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
from pathlib import Path

import pytest

from opportunity_radar.phase4_replay import (
    ABLATION_ORDER,
    ReplayError,
    load_replay_config,
    resolve_human_opportunity_intent,
    run_replay,
)
from opportunity_radar.state_repository import SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/phase4_replay_v1.yaml"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _has_private_replay_evidence() -> bool:
    config = load_replay_config(CONFIG)
    return all((ROOT / path).exists() for path in config.baseline.values() if path.endswith((".json", ".jsonl", ".md", ".sqlite3")))


def test_replay_config_and_human_intent_are_explicit():
    config = load_replay_config(CONFIG)
    status, decision, preferred = resolve_human_opportunity_intent(
        [3, 4, 5, 9], ["APPLY"] * 4, config,
    )
    assert (status, decision, preferred) == ("RESOLVED_ACCEPTED_CLUSTER", "APPLY", 9)
    status, decision, preferred = resolve_human_opportunity_intent(
        [101, 102], ["APPLY", "APPLY"], config,
    )
    assert (status, decision, preferred) == ("HUMAN_CLUSTER_INTENT_UNRESOLVED", None, None)


@pytest.mark.skipif(not _has_private_replay_evidence(), reason="private local judgment evidence is unavailable")
def test_frozen_replay_is_zero_call_deterministic_and_non_mutating(tmp_path, monkeypatch):
    config = load_replay_config(CONFIG)
    protected = [ROOT / config.baseline[key] for key in ("batch_path", "report_path", "review_path", "judgments_path", "database_path")]
    before = {path: _hash(path) for path in protected}

    def forbidden_network(*args, **kwargs):
        raise AssertionError("replay attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    first = run_replay(CONFIG, tmp_path, run_id="test-replay", write_artifact=False)
    second = run_replay(CONFIG, tmp_path, run_id="test-replay", write_artifact=False)

    assert first["metrics"] == second["metrics"]
    assert first["gates"] == second["gates"]
    assert first["metrics"]["posting_level"]["accounted_for"] == 30
    assert first["metrics"]["posting_level"]["cached_semantic_assessments_reused"] == 30
    assert first["zero_call_evidence"] == {
        "external_semantic_calls": 0,
        "live_source_calls": 0,
        "transport_constructed": False,
        "cache_rows_compatible": 30,
    }
    assert first["ablation_order"] == list(ABLATION_ORDER)
    assert [item["stage"] for item in first["ablations"]] == list(ABLATION_ORDER)
    assert {tuple(item["review_numbers"]) for item in first["opportunity_level"] if len(item["review_numbers"]) > 1} == {(3, 4, 5, 9), (11, 12)}
    kiwi = next(item for item in first["opportunity_level"] if item["review_numbers"] == [3, 4, 5, 9])
    assert kiwi["human_decision"] == "APPLY"
    assert kiwi["preferred_review_number"] == 9
    assert {path: _hash(path) for path in protected} == before
    assert first["immutability_check"]["byte_identical"] is True


@pytest.mark.skipif(not _has_private_replay_evidence(), reason="private local judgment evidence is unavailable")
def test_replay_artifacts_are_immutable(tmp_path):
    artifact = run_replay(CONFIG, tmp_path, run_id="immutable-run")
    json_path = tmp_path / "immutable-run/replay.json"
    report_path = tmp_path / "immutable-run/report.md"
    summary_path = tmp_path / "immutable-run/aggregate_summary.json"
    assert json.loads(json_path.read_text())["run_id"] == "immutable-run"
    assert report_path.read_text().startswith("# Phase 4 Frozen Retrospective Replay")
    summary = json.loads(summary_path.read_text())
    assert summary["evidence_class"] == "SANITIZED_AGGREGATE_EXPERIMENT_RESULT"
    assert summary["run_id"] == "immutable-run"
    assert "posting_level" not in summary
    assert "opportunity_level" not in summary
    assert "residual_disagreements" not in summary
    serialized = summary_path.read_text()
    assert "job_instance_id" not in serialized
    assert "review_number" not in serialized
    assert "candidate_evidence" not in serialized
    with pytest.raises(FileExistsError):
        run_replay(CONFIG, tmp_path, run_id="immutable-run")
    assert artifact["artifact_paths"]["private_detailed_json"] == str(json_path)
    assert artifact["artifact_paths"]["tracked_aggregate_summary"] == str(summary_path)


def test_phase4_replay_does_not_change_sqlite_schema():
    database = ROOT / "output/opportunity_radar.sqlite3"
    if not database.exists():
        pytest.skip("local operational database is unavailable")
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 3
    finally:
        connection.close()


def test_replay_configuration_rejects_overlapping_human_groups(tmp_path):
    raw = CONFIG.read_text()
    raw = raw.replace("review_numbers: [11, 12]", "review_numbers: [9, 12]")
    path = tmp_path / "bad.yaml"
    path.write_text(raw)
    with pytest.raises(ReplayError, match="overlap"):
        load_replay_config(path)


def test_repository_tracks_only_sanitized_phase4_replay_evidence():
    ignore = (ROOT / ".gitignore").read_text()
    assert "output/phase4_replay/**/*" in ignore
    assert "!output/phase4_replay/**/aggregate_summary.json" in ignore

    registry = __import__("yaml").safe_load(
        (ROOT / "experiments/registry.yaml").read_text()
    )
    replay = next(
        item for item in registry["experiments"]
        if item["experiment_id"] == "EXP-PHASE4-REPLAY-001"
    )
    assert len(replay["artifacts"]) == 1
    assert replay["artifacts"][0].endswith("/aggregate_summary.json")
    summary = json.loads((ROOT / replay["artifacts"][0]).read_text())
    assert summary["evidence_class"] == "SANITIZED_AGGREGATE_EXPERIMENT_RESULT"
    assert "posting_level" not in summary
    assert "opportunity_level" not in summary
